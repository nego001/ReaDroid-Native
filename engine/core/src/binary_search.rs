//! Bounded streaming masked-byte search over a caller-owned stable source.
//! No path opening, decoding, execution, mutation, or persistent match cache.
use crate::ReadSession;
use std::{io::{self,Read,Seek},ops::Range};

pub const MAX_PATTERN_BYTES:usize=128;
pub const MAX_PATTERN_TEXT:usize=1024;
pub const MAX_STARTS:u64=16*1024*1024;
pub const MAX_MATCHES:usize=4096;
const CHUNK:usize=64*1024;

#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum PatternError{Empty,TooLong,InvalidToken}
/// Compiled Shift-And masks: one bit per pattern position. Nibble wildcards
/// such as A?, ?F and ?? are supported. Text is never evaluated as code.
pub struct Pattern{len:usize,masks:[u128;256]}
fn nibble(b:u8)->Option<(u8,u8)>{
    match b{
        b'0'..=b'9'=>Some((b-b'0',15)),
        b'a'..=b'f'=>Some((b-b'a'+10,15)),
        b'A'..=b'F'=>Some((b-b'A'+10,15)),
        b'?'=>Some((0,0)),
        _=>None
    }
}
impl Pattern{
    pub fn parse(text:&str)->Result<Self,PatternError>{
        if text.len()>MAX_PATTERN_TEXT{return Err(PatternError::TooLong);}
        let mut p=Self{len:0,masks:[0;256]};
        for token in text.split_ascii_whitespace(){
            if p.len==MAX_PATTERN_BYTES{return Err(PatternError::TooLong);}
            let b=token.as_bytes();
            if b.len()!=2{return Err(PatternError::InvalidToken);}
            let (h,hm)=nibble(b[0]).ok_or(PatternError::InvalidToken)?;
            let (l,lm)=nibble(b[1]).ok_or(PatternError::InvalidToken)?;
            let value=(h<<4)|l;let mask=(hm<<4)|lm;
            for byte in 0..256{
                if (byte as u8)&mask==value{p.masks[byte]|=1u128<<p.len;}
            }
            p.len+=1;
        }
        if p.len==0{return Err(PatternError::Empty);}
        Ok(p)
    }
    pub fn len(&self)->usize{self.len}
    pub fn is_empty(&self)->bool{self.len==0}
}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub struct Limits{pub max_starts:u64,pub max_matches:usize}
#[derive(Debug,PartialEq,Eq)]
pub struct SearchPage{
    pub matches:Vec<u64>,
    /// Exclusive end of candidate starts actually examined, not bytes read.
    pub examined_until:u64,
    pub next_start:Option<u64>,
    /// Actual reserved read bytes, including lookahead and block over-read
    /// when the hit cap is reached. Continuation can reread overlap.
    pub charged_bytes:u64,
}
fn invalid()->io::Error{io::Error::new(io::ErrorKind::InvalidInput,"invalid search range or limit")}
/// Search matches entirely contained within scope, in ascending order,
/// including overlapping matches. Resume with next_start and the identical
/// stable source, scope and pattern. A page is atomic on error/cancellation;
/// read budget reservations already spent are not refunded.
pub fn search<R:Read+Seek>(session:&mut ReadSession<R>,pattern:&Pattern,scope:Range<u64>,start:u64,limits:Limits)->io::Result<SearchPage>{
    if scope.start>scope.end||scope.end>session.len()||start<scope.start||
        limits.max_starts==0||limits.max_starts>MAX_STARTS||
        limits.max_matches==0||limits.max_matches>MAX_MATCHES{return Err(invalid());}
    session.cancellation.check()?;
    let n=pattern.len as u64;
    let end=if scope.end-scope.start<n{scope.start}else{scope.end-(n-1)};
    if start>end{return Err(invalid());}
    let mut out=SearchPage{matches:Vec::with_capacity(limits.max_matches),examined_until:start,next_start:None,charged_bytes:0};
    if start==end{return Ok(out);}
    let stop=start+(end-start).min(limits.max_starts);
    let read_end=stop+(n-1); // <= scope.end
    let initial=session.remaining_budget();
    if read_end-start>initial{return Err(io::Error::new(io::ErrorKind::Other,"search page exceeds read budget"));}
    let mut pos=start;let mut state=0u128;
    let high=1u128<<(pattern.len-1);
    while pos<read_end{
        session.cancellation.check()?;
        let size=(read_end-pos).min(CHUNK as u64) as usize;
        let window=session.read_window(pos,size)?;
        for (i,b) in window.bytes.into_iter().enumerate(){
            if i%1024==0{session.cancellation.check()?;}
            state=((state<<1)|1)&pattern.masks[b as usize];
            let address=pos+i as u64;
            if address-start>=n-1{
                let hit=address-(n-1);
                out.examined_until=hit+1;
                if state&high!=0{
                    out.matches.push(hit);
                    if out.matches.len()==limits.max_matches{
                        out.next_start=(out.examined_until<end).then_some(out.examined_until);
                        out.charged_bytes=initial-session.remaining_budget();
                        session.cancellation.check()?;
                        return Ok(out);
                    }
                }
            }
        }
        pos+=size as u64;
    }
    session.cancellation.check()?;
    out.next_start=(stop<end).then_some(stop);
    out.charged_bytes=initial-session.remaining_budget();
    Ok(out)
}
