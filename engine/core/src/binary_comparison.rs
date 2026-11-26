//! Bounded positional comparison. No insertion/deletion alignment, source
//! opening, mutation, hash inference or claim of whole-file equality from a page.
use crate::ReadSession;
use std::io::{self,Read,Seek};
use std::ops::Range;
pub const MAX_POSITIONS:u64=16*1024*1024;
pub const MAX_RANGES:usize=4096;
const CHUNK:u64=64*1024;

#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Difference{Changed,LeftOnly,RightOnly}
#[derive(Debug,Clone,PartialEq,Eq)]
pub struct Interval{pub start:u64,pub end:u64,pub kind:Difference}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub struct Limits{pub max_positions:u64,pub max_ranges:usize}
#[derive(Debug,PartialEq,Eq)]
pub struct Page{
    pub left_length:u64,pub right_length:u64,
    pub start:u64,pub examined_until:u64,pub next_start:Option<u64>,
    pub equal:u64,pub changed:u64,pub left_only:u64,pub right_only:u64,
    pub ranges:Vec<Interval>,pub left_charged:u64,pub right_charged:u64,
}
fn invalid()->io::Error{io::Error::new(io::ErrorKind::InvalidInput,"invalid comparison range or limits")}
fn budget()->io::Error{io::Error::new(io::ErrorKind::Other,"comparison page exceeds read budget")}
/// Compare equal source-relative offsets in the explicit scope. Missing
/// tails are reported from the supplied lengths, not read or zero-padded.
/// Range count limits stop BEFORE a new interval would exceed the cap;
/// a long interval may be split by a page boundary. Adjacent pages may be
/// coalesced by a caller only for the same stable sources and scope.
/// No partial page on error, and admitted I/O remains charged.
pub fn compare<L:Read+Seek,R:Read+Seek>(
    left:&mut ReadSession<L>,right:&mut ReadSession<R>,scope:Range<u64>,start:u64,limits:Limits
)->io::Result<Page>{
    let ll=left.len();let rl=right.len();let common=ll.min(rl);
    if scope.start>scope.end||scope.end>ll.max(rl)||start<scope.start||start>scope.end||
        limits.max_positions==0||limits.max_positions>MAX_POSITIONS||
        limits.max_ranges==0||limits.max_ranges>MAX_RANGES{return Err(invalid());}
    left.cancellation.check()?;right.cancellation.check()?;
    let stop=start+(scope.end-start).min(limits.max_positions);
    // Only positions present in both sources are read. Unpaired tails
    // describe extent differences, not observed content or integrity.
    let paired=stop.min(common).saturating_sub(start);
    let lb=left.remaining_budget();let rb=right.remaining_budget();
    if paired>lb||paired>rb{return Err(budget());}
    let mut p=Page{left_length:ll,right_length:rl,start,examined_until:start,next_start:None,
        equal:0,changed:0,left_only:0,right_only:0,ranges:Vec::with_capacity(limits.max_ranges),
        left_charged:0,right_charged:0};
    let mut pos=start;
    'scan: while pos<stop{
        left.cancellation.check()?;right.cancellation.check()?;
        if pos>=common{
            let kind=if ll>rl{Difference::LeftOnly}else{Difference::RightOnly};
            if !record(&mut p,pos,stop,kind,limits.max_ranges){break;}
            p.examined_until=stop;
            break;
        }
        let end=stop.min(common);
        let size=(end-pos).min(CHUNK) as usize;
        let a=left.read_window(pos,size)?;
        right.cancellation.check()?;left.cancellation.check()?;
        let b=right.read_window(pos,size)?;
        for (i,(&x,&y)) in a.bytes.iter().zip(&b.bytes).enumerate(){
            if i%1024==0{left.cancellation.check()?;right.cancellation.check()?;}
            let at=pos+i as u64;
            if x==y{p.equal+=1;}
            else if !record(&mut p,at,at+1,Difference::Changed,limits.max_ranges){break 'scan;}
            p.examined_until=at+1;
        }
        pos+=size as u64;
    }
    left.cancellation.check()?;right.cancellation.check()?;
    p.next_start=(p.examined_until<scope.end).then_some(p.examined_until);
    p.left_charged=lb-left.remaining_budget();p.right_charged=rb-right.remaining_budget();
    Ok(p)
}
fn record(p:&mut Page,start:u64,end:u64,kind:Difference,cap:usize)->bool{
    if let Some(last)=p.ranges.last_mut().filter(|i|i.end==start&&i.kind==kind){
        last.end=end;
    }else{
        if p.ranges.len()==cap{return false;}
        p.ranges.push(Interval{start,end,kind});
    }
    let n=end-start;
    match kind{Difference::Changed=>p.changed+=n,Difference::LeftOnly=>p.left_only+=n,Difference::RightOnly=>p.right_only+=n}
    true
}
