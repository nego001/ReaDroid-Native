//! Explicit, bounded text interpretation of a source-relative byte window.
//! No encoding guessing, normalization, BOM stripping, replacement of source
//! bytes or rendering of untrusted text. A split scalar at a window boundary
//! is incomplete within that window, not proof of a malformed whole source.
use crate::ReadSession;
use std::io::{self,Read,Seek};
pub const MAX_TEXT_BYTES:usize=4096;

#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Encoding{Ascii,Utf8,Utf16Le,Utf16Be}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Error{WindowLimit,OffsetOverflow}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Kind{Scalar(char),Invalid,Incomplete}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub struct Unit{pub offset:u64,pub length:u8,pub kind:Kind}
#[derive(Debug,PartialEq,Eq)]
pub struct Decoded{
    pub encoding:Encoding,pub offset:u64,pub byte_count:usize,pub units:Vec<Unit>,
}
impl Decoded{
    /// First unconsumed partial scalar, if present. A caller may explicitly
    /// reread from this address with a larger/next window, charging it again.
    pub fn incomplete_at(&self)->Option<u64>{
        self.units.last().filter(|u|u.kind==Kind::Incomplete).map(|u|u.offset)
    }
}
/// UTF-16 starts at the caller's chosen code-unit origin, even at an odd
/// absolute offset; no claim is made about alignment in the surrounding file.
/// Every input byte is accounted for by exactly one nonempty unit.
pub fn decode(encoding:Encoding,offset:u64,bytes:&[u8])->Result<Decoded,Error>{
    if bytes.len()>MAX_TEXT_BYTES{return Err(Error::WindowLimit);}
    offset.checked_add(bytes.len() as u64).ok_or(Error::OffsetOverflow)?;
    let mut out=Decoded{encoding,offset,byte_count:bytes.len(),units:Vec::with_capacity(bytes.len())};
    let mut i=0;
    while i<bytes.len(){
        let rest=&bytes[i..];
        let (length,kind)=match encoding{
            Encoding::Ascii=>if rest[0]<=127{(1,Kind::Scalar(char::from(rest[0])))}else{(1,Kind::Invalid)},
            Encoding::Utf8=>utf8_unit(rest),
            Encoding::Utf16Le|Encoding::Utf16Be=>utf16_unit(rest,encoding==Encoding::Utf16Le),
        };
        out.units.push(Unit{offset:offset+i as u64,length:length as u8,kind});
        i+=length;
    }
    Ok(out)
}
fn utf8_unit(b:&[u8])->(usize,Kind){
    let width=match b[0]{
        0x00..=0x7f=>return (1,Kind::Scalar(char::from(b[0]))),
        0xc2..=0xdf=>2,0xe0..=0xef=>3,0xf0..=0xf4=>4,
        _=>return (1,Kind::Invalid),
    };
    let prefix=&b[..width.min(b.len())];
    match std::str::from_utf8(prefix){
        Ok(s)=>(width,Kind::Scalar(s.chars().next().expect("nonempty valid scalar"))),
        Err(e)=>match e.error_len(){
            Some(n)=>(n,Kind::Invalid),
            None=>(prefix.len(),Kind::Incomplete),
        }
    }
}
fn word(b:&[u8],little:bool)->u16{
    if little{u16::from_le_bytes([b[0],b[1]])}else{u16::from_be_bytes([b[0],b[1]])}
}
fn utf16_unit(b:&[u8],little:bool)->(usize,Kind){
    if b.len()<2{return (b.len(),Kind::Incomplete);}
    let a=word(b,little);
    match a{
        0xd800..=0xdbff=>{
            if b.len()<4{return (b.len(),Kind::Incomplete);}
            let z=word(&b[2..],little);
            if !(0xdc00..=0xdfff).contains(&z){return (2,Kind::Invalid);}
            let cp=0x10000+(((a as u32-0xd800)<<10)|(z as u32-0xdc00));
            (4,Kind::Scalar(char::from_u32(cp).expect("valid surrogate pair")))
        }
        0xdc00..=0xdfff=>(2,Kind::Invalid),
        _=>(2,Kind::Scalar(char::from_u32(a as u32).expect("non-surrogate unit"))),
    }
}
#[derive(Debug,PartialEq,Eq)]
pub struct TextWindow{pub decoded:Decoded,pub source_length:u64,pub has_after:bool}
/// Read one bounded window, using the existing cumulative I/O budget.
/// A short tail is allowed; a terminal incomplete unit is still reported
/// explicitly, not repaired. Cancellation discards the whole result.
pub fn read<R:Read+Seek>(session:&mut ReadSession<R>,encoding:Encoding,offset:u64,requested:usize)->io::Result<TextWindow>{
    if requested==0||requested>MAX_TEXT_BYTES||offset>session.len(){
        return Err(io::Error::new(io::ErrorKind::InvalidInput,"invalid text window"));
    }
    let size=(session.len()-offset).min(requested as u64) as usize;
    let bytes=session.read_window(offset,size)?;
    let decoded=decode(encoding,offset,&bytes.bytes).map_err(|_|io::Error::new(io::ErrorKind::InvalidData,"text window limit"))?;
    session.cancellation.check()?;
    Ok(TextWindow{decoded,source_length:session.len(),has_after:offset+(size as u64)<session.len()})
}
