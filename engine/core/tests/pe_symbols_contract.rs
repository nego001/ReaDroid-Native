use negrodroid_core::{Cancellation,ReadSession,pe_symbols::{Inspector,Name,SectionRef,MAX_PAGE}};
use std::io::{self,Cursor};
fn w16(b:&mut[u8],i:usize,v:u16){b[i..i+2].copy_from_slice(&v.to_le_bytes());}
fn w32(b:&mut[u8],i:usize,v:u32){b[i..i+4].copy_from_slice(&v.to_le_bytes());}
const PE:usize=128;const OPT:usize=PE+24;const SYM:usize=1024;const STR:usize=SYM+4*18;
fn fixture(plus:bool)->Vec<u8>{
    let mut b=vec![0;1400];b[..2].copy_from_slice(b"MZ");w32(&mut b,60,PE as u32);
    b[PE..PE+4].copy_from_slice(b"PE\0\0");w16(&mut b,PE+4,if plus{0x8664}else{0x14c});w16(&mut b,PE+6,1);
    w32(&mut b,PE+12,SYM as u32);w32(&mut b,PE+16,4);
    let size=if plus{112}else{96};w16(&mut b,PE+20,size as u16);
    w16(&mut b,OPT,if plus{0x20b}else{0x10b});w32(&mut b,OPT+32,4096);w32(&mut b,OPT+36,512);
    w32(&mut b,OPT+56,8192);w32(&mut b,OPT+60,512);
    let t=OPT+size;b[t..t+5].copy_from_slice(b".text");w32(&mut b,t+8,512);w32(&mut b,t+12,4096);
    w32(&mut b,t+16,512);w32(&mut b,t+20,512);
    b[SYM..SYM+8].copy_from_slice(b"abcdefgh");w32(&mut b,SYM+8,17);w16(&mut b,SYM+12,1);
    w16(&mut b,SYM+14,0x20);b[SYM+16]=2;b[SYM+17]=1;
    b[SYM+18..SYM+36].fill(0xff); // aux intentionally not a symbol
    w32(&mut b,SYM+36+4,4);w16(&mut b,SYM+36+12,0xffff);
    b[SYM+54..SYM+57].copy_from_slice(b"end");w16(&mut b,SYM+54+12,0xfffe);
    let name=b"long_symbol\0";w32(&mut b,STR,(4+name.len()) as u32);
    b[STR+4..STR+4+name.len()].copy_from_slice(name);b
}
fn open(b:&[u8],budget:u64)->io::Result<Inspector<Cursor<&[u8]>>>{
    Inspector::open(ReadSession::new(Cursor::new(b),b.len() as u64,budget,Cancellation::default()))
}
#[test]
fn both_pe_classes_and_classic_records(){
    for plus in [false,true]{let b=fixture(plus);let mut i=open(&b,4096).unwrap();let p=i.next(3).unwrap();
        assert_eq!(p.raw_total,4);assert_eq!(p.entries.len(),3);assert_eq!(p.next_record,None);
        let a=&p.entries[0];assert_eq!(a.name,Name::Bytes(b"abcdefgh".to_vec()));
        assert_eq!((a.value,a.type_code,a.storage_class,a.auxiliary_count),(17,0x20,2,1));
        assert_eq!(a.section,SectionRef::Index(1));
        assert_eq!(p.entries[1].record_index,2);assert_eq!(p.entries[1].name,Name::Bytes(b"long_symbol".to_vec()));
        assert_eq!(p.entries[1].section,SectionRef::Absolute);assert_eq!(p.entries[2].section,SectionRef::Debug);
    }
}
#[test]
fn page_cursor_skips_aux_and_restart(){
    let b=fixture(false);let mut i=open(&b,4096).unwrap();
    assert_eq!(i.next(1).unwrap().next_record,Some(2));assert_eq!(i.cursor(),2);
    assert_eq!(i.next(1).unwrap().next_record,Some(3));assert_eq!(i.next(1).unwrap().next_record,None);
    assert!(i.next(1).unwrap().entries.is_empty());i.restart().unwrap();assert_eq!(i.cursor(),0);
    assert_eq!(i.next(1).unwrap().entries[0].record_index,0);
}
#[test]
fn absent_table_and_inconsistent_pair(){
    let mut b=fixture(false);w32(&mut b,PE+12,0);w32(&mut b,PE+16,0);
    let mut i=open(&b,4096).unwrap();assert_eq!(i.raw_total(),0);assert!(i.next(1).unwrap().entries.is_empty());
    w32(&mut b,PE+16,4);assert!(open(&b,4096).is_err());
}
#[test]
fn invalid_table_and_string_extents(){
    let mut b=fixture(false);w32(&mut b,PE+16,u32::MAX);assert!(open(&b,4096).is_err());
    w32(&mut b,PE+16,4);w32(&mut b,STR,3);assert!(open(&b,4096).is_err());
    w32(&mut b,STR,u32::MAX);assert!(open(&b,4096).is_err());
}
#[test]
fn table_overlapping_section_rejected(){
    let mut b=fixture(false);w32(&mut b,PE+12,600);w32(&mut b,672,4);
    assert!(open(&b,4096).is_err());
}
#[test]
fn auxiliary_overrun_and_bad_section_atomic(){
    let mut b=fixture(false);b[SYM+54+17]=1;
    let mut i=open(&b,4096).unwrap();assert!(i.next(3).is_err());assert_eq!(i.cursor(),0);
    b[SYM+54+17]=0;w16(&mut b,SYM+36+12,2);
    let mut i=open(&b,4096).unwrap();i.next(1).unwrap();assert!(i.next(1).is_err());assert_eq!(i.cursor(),2);
}
#[test]
fn bad_string_offset_and_missing_nul(){
    let mut b=fixture(false);w32(&mut b,SYM+36+4,3);
    let mut i=open(&b,4096).unwrap();assert!(i.next(2).is_err());
    w32(&mut b,SYM+36+4,4);b[STR+15]=b'x';
    let mut i=open(&b,4096).unwrap();assert!(i.next(2).is_err());
}
#[test]
fn bounded_long_names_and_raw_bytes(){
    let mut b=fixture(false);b[STR+4]=0xff;
    let mut i=open(&b,4096).unwrap();let p=i.next(2).unwrap();
    assert!(matches!(&p.entries[1].name,Name::Bytes(n) if n[0]==0xff));
    w32(&mut b,STR,300);b[STR+4..STR+299].fill(b'x');
    let mut i=open(&b,4096).unwrap();assert_eq!(i.next(2).unwrap().entries[1].name,Name::TooLong);
}
#[test]
fn invalid_page_and_budget_no_cursor_commit(){
    let b=fixture(false);let mut i=open(&b,4096).unwrap();
    let charged=4096-i.remaining_budget();let mut i=open(&b,charged+18).unwrap();
    assert!(i.next(MAX_PAGE+1).is_err());assert_eq!(i.remaining_budget(),18);
    assert!(i.next(2).is_err());assert_eq!(i.cursor(),0);assert_eq!(i.remaining_budget(),0);
}
#[test]
fn cancellation_preserves_cursor(){
    let b=fixture(true);let c=Cancellation::default();
    let mut i=Inspector::open(ReadSession::new(Cursor::new(&b),b.len() as u64,4096,c.clone())).unwrap();
    i.next(1).unwrap();c.cancel();
    assert_eq!(i.next(1).unwrap_err().kind(),io::ErrorKind::Interrupted);
    assert!(i.restart().is_err());assert_eq!(i.cursor(),2);
}
