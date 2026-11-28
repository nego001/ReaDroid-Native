use negrodroid_core::{Cancellation,ReadSession,binary_search::{Pattern,PatternError,Limits,search,MAX_STARTS}};
use std::io::{self,Cursor,Read,Seek,SeekFrom};
fn limits()->Limits{Limits{max_starts:MAX_STARTS,max_matches:4096}}
#[test]
fn strict_pattern_parser_and_maximum_length(){
    for p in [""," \t"]{assert!(matches!(Pattern::parse(p),Err(PatternError::Empty)));}
    for p in ["A","GG","0xAB","ABC","é","A*","AA,BB"]{assert!(matches!(Pattern::parse(p),Err(PatternError::InvalidToken)));}
    assert_eq!(Pattern::parse("aB ?f A? ??").unwrap().len(),4);
    assert_eq!(Pattern::parse(&"AA ".repeat(128)).unwrap().len(),128);
    assert!(matches!(Pattern::parse(&"AA ".repeat(129)),Err(PatternError::TooLong)));
    assert!(matches!(Pattern::parse(&" ".repeat(1025)),Err(PatternError::TooLong)));
}
#[test]
fn nibble_and_full_wildcards(){
    let bytes=[0xAB,0x1F,0x20,0xA9,0xFF,0x30,0xB9,0x1F,0x40];
    let mut s=ReadSession::new(Cursor::new(bytes),9,9,Cancellation::default());
    let p=search(&mut s,&Pattern::parse("A? ?F ??").unwrap(),0..9,0,limits()).unwrap();
    assert_eq!(p.matches,vec![0,3]);assert_eq!(p.examined_until,7);assert_eq!(p.charged_bytes,9);assert_eq!(p.next_start,None);
}
#[test]
fn chunk_boundary_and_128_bit_pattern(){
    let mut bytes=vec![0;65536+128];bytes[65530..65658].fill(0xAB);
    let len=bytes.len() as u64;
    let mut s=ReadSession::new(Cursor::new(bytes),len,len,Cancellation::default());
    let p=search(&mut s,&Pattern::parse(&"AB ".repeat(128)).unwrap(),0..len,0,limits()).unwrap();
    assert_eq!(p.matches,vec![65530]);assert_eq!(p.charged_bytes,len);
}
#[test]
fn overlapping_hits_and_hit_limited_resume(){
    let mut s=ReadSession::new(Cursor::new(b"AAAAA"),5,20,Cancellation::default());
    let pat=Pattern::parse("41 41").unwrap();
    let mut at=0;let mut hits=vec![];
    loop{
        let p=search(&mut s,&pat,0..5,at,Limits{max_matches:1,..limits()}).unwrap();
        hits.extend(p.matches);
        match p.next_start{Some(n)=>{assert!(n>at);at=n},None=>break}
    }
    assert_eq!(hits,vec![0,1,2,3]);assert_eq!(s.remaining_budget(),6);
}
#[test]
fn start_budget_and_scope_no_crossing(){
    let mut s=ReadSession::new(Cursor::new(b"AAAAAAAA"),8,20,Cancellation::default());
    let pat=Pattern::parse("41 41").unwrap();
    let lim=Limits{max_starts:2,..limits()};
    let a=search(&mut s,&pat,1..7,1,lim).unwrap();
    assert_eq!(a.matches,vec![1,2]);assert_eq!(a.next_start,Some(3));assert_eq!(a.charged_bytes,3);
    let b=search(&mut s,&pat,1..7,3,lim).unwrap();assert_eq!(b.matches,vec![3,4]);
    let c=search(&mut s,&pat,1..7,5,lim).unwrap();assert_eq!(c.matches,vec![5]);assert_eq!(c.next_start,None);
}
#[test]
fn too_short_empty_and_invalid_range(){
    let mut s=ReadSession::new(Cursor::new(b"A"),1,1,Cancellation::default());
    let pat=Pattern::parse("41 41").unwrap();
    let p=search(&mut s,&pat,0..1,0,limits()).unwrap();assert!(p.matches.is_empty());assert_eq!(p.charged_bytes,0);
    assert!(search(&mut s,&pat,0..2,0,limits()).is_err());
    assert!(search(&mut s,&pat,0..1,1,limits()).is_err());
    assert!(search(&mut s,&pat,0..1,0,Limits{max_starts:0,..limits()}).is_err());
    assert_eq!(s.remaining_budget(),1);
}
#[test]
fn budget_preflight_failure_charge_and_cancel(){
    let c=Cancellation::default();
    let pat=Pattern::parse("41").unwrap();
    let mut s=ReadSession::new(Cursor::new(b"A"),2,2,c.clone());
    assert!(search(&mut s,&pat,0..2,0,Limits{max_starts:3,max_matches:0}).is_err());
    assert_eq!(s.remaining_budget(),2);
    assert_eq!(search(&mut s,&pat,0..2,0,limits()).unwrap_err().kind(),io::ErrorKind::UnexpectedEof);
    assert_eq!(s.remaining_budget(),0);
    c.cancel();
    assert_eq!(search(&mut s,&pat,0..2,0,limits()).unwrap_err().kind(),io::ErrorKind::Interrupted);
    let mut s=ReadSession::new(Cursor::new(b"AB"),2,1,Cancellation::default());
    assert!(search(&mut s,&pat,0..2,0,limits()).is_err());assert_eq!(s.remaining_budget(),1);
}
struct Sparse(u64);
impl Read for Sparse{fn read(&mut self,b:&mut [u8])->io::Result<usize>{b.fill(0xAA);self.0+=b.len() as u64;Ok(b.len())}}
impl Seek for Sparse{fn seek(&mut self,p:SeekFrom)->io::Result<u64>{if let SeekFrom::Start(n)=p{self.0=n;Ok(n)}else{Err(io::ErrorKind::InvalidInput.into())}}}
#[test]
fn exact_u64_offsets_at_maximum_length(){
    let n=u64::MAX;
    let mut s=ReadSession::new(Sparse(0),n,4,Cancellation::default());
    let p=search(&mut s,&Pattern::parse("AA AA").unwrap(),n-4..n,n-4,limits()).unwrap();
    assert_eq!(p.matches,vec![n-4,n-3,n-2]);assert_eq!(p.examined_until,n-1);assert_eq!(p.charged_bytes,4);
}
#[test]
fn exhaustive_small_oracle(){
    for a in 0..256u16{
        let bytes:Vec<u8>=(0..8).map(|i|((a>>i)&1) as u8).collect();
        for (text,pattern) in [("00 01",vec![Some(0),Some(1)]),("?? 00 ??",vec![None,Some(0),None]),("??",vec![None])]{
            let mut s=ReadSession::new(Cursor::new(&bytes),8,8,Cancellation::default());
            let p=search(&mut s,&Pattern::parse(text).unwrap(),0..8,0,limits()).unwrap();
            let expected:Vec<u64>=bytes.windows(pattern.len()).enumerate().filter(|(_,w)|w.iter().zip(&pattern).all(|(b,p)|p.is_none_or(|v|v==*b))).map(|(i,_)|i as u64).collect();
            assert_eq!(p.matches,expected);
        }
    }
}
