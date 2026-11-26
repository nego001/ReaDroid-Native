use negrodroid_core::{Cancellation,ReadSession,binary_comparison::{compare,Limits,Difference,Interval,MAX_POSITIONS}};
use std::io::{self,Cursor,Read,Seek,SeekFrom};
fn lim()->Limits{Limits{max_positions:MAX_POSITIONS,max_ranges:4096}}
fn session(b:&[u8],budget:u64)->ReadSession<Cursor<&[u8]>>{ReadSession::new(Cursor::new(b),b.len() as u64,budget,Cancellation::default())}
fn range(start:u64,end:u64,kind:Difference)->Interval{Interval{start,end,kind}}
#[test]
fn equal_and_empty_sources(){
    let mut a=session(b"abc",3);let mut b=session(b"abc",3);
    let p=compare(&mut a,&mut b,0..3,0,lim()).unwrap();
    assert_eq!((p.equal,p.changed,p.next_start,p.left_charged,p.right_charged),(3,0,None,3,3));
    assert!(p.ranges.is_empty());
    let mut a=session(b"",0);let mut b=session(b"",0);
    let p=compare(&mut a,&mut b,0..0,0,lim()).unwrap();
    assert_eq!(p.examined_until,0);assert_eq!(p.next_start,None);
}
#[test]
fn positional_changes_and_length_tails(){
    let mut a=session(b"ABCDEF",4);let mut b=session(b"AXYD",4);
    let p=compare(&mut a,&mut b,0..6,0,lim()).unwrap();
    assert_eq!(p.ranges,vec![range(1,3,Difference::Changed),range(4,6,Difference::LeftOnly)]);
    assert_eq!((p.equal,p.changed,p.left_only,p.right_only),(2,2,2,0));
    assert_eq!((p.left_charged,p.right_charged),(4,4));
    let mut a=session(b"",0);let mut b=session(b"ABC",0);
    let p=compare(&mut a,&mut b,0..3,0,lim()).unwrap();
    assert_eq!(p.ranges,vec![range(0,3,Difference::RightOnly)]);
    assert_eq!((p.left_charged,p.right_charged),(0,0));
}
#[test]
fn differences_coalesce_across_chunks(){
    let a=vec![0u8;65540];let mut b=a.clone();b[65534..65539].fill(1);
    let mut l=session(&a,65540);let mut r=session(&b,65540);
    let p=compare(&mut l,&mut r,0..65540,0,lim()).unwrap();
    assert_eq!(p.ranges,vec![range(65534,65539,Difference::Changed)]);
    assert_eq!(p.equal,65535);
}
#[test]
fn range_cap_continuation_no_skipped_position(){
    let mut a=session(b"AAAAAA",20);let mut b=session(b"BABABA",20);
    let mut start=0;let mut intervals=vec![];
    loop{
        let p=compare(&mut a,&mut b,0..6,start,Limits{max_ranges:1,..lim()}).unwrap();
        assert_eq!(p.equal+p.changed+p.left_only+p.right_only,p.examined_until-start);
        intervals.extend(p.ranges);
        match p.next_start{Some(n)=>{assert!(n>start);start=n},None=>break}
    }
    assert_eq!(intervals,vec![range(0,1,Difference::Changed),range(2,3,Difference::Changed),range(4,5,Difference::Changed)]);
    assert_eq!(a.remaining_budget(),8);assert_eq!(b.remaining_budget(),8);
}
#[test]
fn position_cap_and_scope_split_long_range(){
    let mut a=session(b"AAAAAA",6);let mut b=session(b"BBBBBB",6);
    let limits=Limits{max_positions:2,..lim()};
    let p=compare(&mut a,&mut b,1..5,1,limits).unwrap();
    assert_eq!(p.ranges,vec![range(1,3,Difference::Changed)]);assert_eq!(p.next_start,Some(3));
    let p=compare(&mut a,&mut b,1..5,3,limits).unwrap();
    assert_eq!(p.ranges,vec![range(3,5,Difference::Changed)]);assert_eq!(p.next_start,None);
}
#[test]
fn dual_budget_preflight_and_failed_read_accounting(){
    let mut a=session(b"AB",2);let mut b=session(b"AB",1);
    assert!(compare(&mut a,&mut b,0..2,0,lim()).is_err());
    assert_eq!((a.remaining_budget(),b.remaining_budget()),(2,1));
    let mut a=session(b"AB",2);
    let mut b=ReadSession::new(Cursor::new(b"A"),2,2,Cancellation::default());
    assert_eq!(compare(&mut a,&mut b,0..2,0,lim()).unwrap_err().kind(),io::ErrorKind::UnexpectedEof);
    assert_eq!((a.remaining_budget(),b.remaining_budget()),(0,0));
}
#[test]
fn cancelled_either_source_and_invalid_limits(){
    let c=Cancellation::default();c.cancel();
    let mut a=session(b"A",1);let mut b=ReadSession::new(Cursor::new(b"A"),1,1,c);
    assert_eq!(compare(&mut a,&mut b,0..1,0,lim()).unwrap_err().kind(),io::ErrorKind::Interrupted);
    assert_eq!((a.remaining_budget(),b.remaining_budget()),(1,1));
    let mut b=session(b"A",1);
    assert!(compare(&mut a,&mut b,0..2,0,lim()).is_err());
    assert!(compare(&mut a,&mut b,0..1,0,Limits{max_ranges:0,..lim()}).is_err());
    assert!(compare(&mut a,&mut b,0..1,0,Limits{max_positions:MAX_POSITIONS+1,..lim()}).is_err());
}
struct Sparse{at:u64,value:u8}
impl Read for Sparse{fn read(&mut self,b:&mut [u8])->io::Result<usize>{b.fill(self.value);self.at+=b.len() as u64;Ok(b.len())}}
impl Seek for Sparse{fn seek(&mut self,p:SeekFrom)->io::Result<u64>{if let SeekFrom::Start(n)=p{self.at=n;Ok(n)}else{Err(io::ErrorKind::InvalidInput.into())}}}
#[test]
fn exact_u64_maximum_extent(){
    let n=u64::MAX;
    let mut a=ReadSession::new(Sparse{at:0,value:1},n,2,Cancellation::default());
    let mut b=ReadSession::new(Sparse{at:0,value:2},n-2,2,Cancellation::default());
    let p=compare(&mut a,&mut b,n-4..n,n-4,lim()).unwrap();
    assert_eq!(p.ranges,vec![range(n-4,n-2,Difference::Changed),range(n-2,n,Difference::LeftOnly)]);
    assert_eq!(p.examined_until,n);assert_eq!(p.next_start,None);
}
#[test]
fn exhaustive_small_positional_oracle(){
    for a in 0..16u8{for b in 0..16u8{for al in 0..=4{for bl in 0..=4{
        let av:Vec<u8>=(0..al).map(|i|(a>>i)&1).collect();
        let bv:Vec<u8>=(0..bl).map(|i|(b>>i)&1).collect();
        let n=al.max(bl) as u64;
        let mut l=session(&av,4);let mut r=session(&bv,4);
        let p=compare(&mut l,&mut r,0..n,0,lim()).unwrap();
        let mut expected=vec![];
        for i in 0..n as usize{
            let kind=match (av.get(i),bv.get(i)){
                (Some(x),Some(y)) if x==y=>None,
                (Some(_),Some(_))=>Some(Difference::Changed),
                (Some(_),None)=>Some(Difference::LeftOnly),
                (None,Some(_))=>Some(Difference::RightOnly),
                _=>unreachable!(),
            };
            expected.push(kind);
        }
        let mut actual=vec![None;n as usize];
        for interval in &p.ranges{
            for i in interval.start..interval.end{
                assert!(actual[i as usize].is_none());actual[i as usize]=Some(interval.kind);
            }
        }
        assert_eq!(actual,expected);
        assert_eq!(p.equal+p.changed+p.left_only+p.right_only,n);
    }}}}
}
