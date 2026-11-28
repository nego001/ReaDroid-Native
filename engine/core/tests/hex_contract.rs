use negrodroid_core::{Cancellation,ReadSession,hex::{format,preview,Error,MAX_HEX_BYTES}};
use std::io::{self,Cursor,Read,Seek,SeekFrom};
#[test]
fn f2_2_format_exact(){
    let mut bytes=[0u8;17];bytes[0]=65;bytes[1]=32;bytes[2]=255;bytes[16]=90;
    let dump=format(0,&bytes).unwrap();
    assert!(dump.starts_with("00000000  41 20 FF 00 "));
    assert!(dump.contains("|A ..............|\n"));
    assert_eq!(dump.lines().nth(1).unwrap(),format!("00000010  5A {} |Z|","   ".repeat(15)));
    assert_eq!(format(0,&[]).unwrap(),"");
}
#[test]
fn all_ascii_boundaries(){
    let bytes:Vec<u8>=(0..=255).collect();
    let dump=format(0,&bytes).unwrap();
    let ascii:String=dump.lines().map(|s|s.split_once(" |").unwrap().1.strip_suffix('|').unwrap()).collect();
    let expected:String=bytes.iter().map(|&b|if (32..=126).contains(&b){char::from(b)}else{'.'}).collect();
    assert_eq!(ascii,expected);
}
#[test]
fn offsets_not_truncated_and_overflow_rejected(){
    assert!(format(0x1_0000_0000,&[65]).unwrap().starts_with("100000000  41"));
    assert!(format(u64::MAX,&[65]).unwrap().starts_with("FFFFFFFFFFFFFFFF  41"));
    assert_eq!(format(u64::MAX,&[1,2]),Err(Error::OffsetOverflow));
    assert_eq!(format(0,&vec![0;MAX_HEX_BYTES+1]),Err(Error::WindowLimit));
}
#[test]
fn page_reads_exact_bytes_and_charges_budget(){
    let c=Cancellation::default();
    let mut s=ReadSession::new(Cursor::new(b"ABCDE"),5,5,c);
    let p=preview(&mut s,2,4).unwrap();
    assert_eq!((p.offset,p.shown,p.source_length,p.has_before,p.has_after),(2,3,5,true,false));
    assert!(p.dump.starts_with("00000002  43 44 45"));
    assert_eq!(s.remaining_budget(),2);
    let p=preview(&mut s,0,2).unwrap();assert!(p.has_after);assert!(!p.has_before);
    assert_eq!(s.remaining_budget(),0);
    assert!(preview(&mut s,0,1).is_err());
}
#[test]
fn eof_and_bounds_and_cancellation(){
    let c=Cancellation::default();let mut s=ReadSession::new(Cursor::new(b"a"),1,1,c.clone());
    assert_eq!(preview(&mut s,2,1).unwrap_err().kind(),io::ErrorKind::InvalidInput);
    assert_eq!(preview(&mut s,0,0).unwrap_err().kind(),io::ErrorKind::InvalidInput);
    assert_eq!(preview(&mut s,0,4097).unwrap_err().kind(),io::ErrorKind::InvalidInput);
    let p=preview(&mut s,1,1).unwrap();assert_eq!(p.shown,0);assert!(p.has_before);assert!(!p.has_after);
    c.cancel();assert_eq!(preview(&mut s,0,1).unwrap_err().kind(),io::ErrorKind::Interrupted);
}
struct Sparse{pos:u64}
impl Seek for Sparse{
    fn seek(&mut self,p:SeekFrom)->io::Result<u64>{
        if let SeekFrom::Start(n)=p{self.pos=n;Ok(n)}else{Err(io::ErrorKind::InvalidInput.into())}
    }
}
impl Read for Sparse{
    fn read(&mut self,b:&mut [u8])->io::Result<usize>{b.fill(0x41);self.pos+=b.len() as u64;Ok(b.len())}
}
#[test]
fn sparse_source_64_bit_window_without_large_allocation(){
    let n=9_007_199_254_740_993;
    let mut s=ReadSession::new(Sparse{pos:0},n+2,2,Cancellation::default());
    let p=preview(&mut s,n,2).unwrap();
    assert_eq!(p.offset,n);assert_eq!(p.shown,2);assert!(p.dump.starts_with(&format!("{n:08X}  41 41")));
}
