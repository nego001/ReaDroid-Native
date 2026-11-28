use negrodroid_core::{Cancellation,ReadSession,dex_structure::{self,Issue,Unsupported,Verdict}};
use std::io::{self,Cursor};
fn w16(b:&mut[u8],i:usize,v:u16){b[i..i+2].copy_from_slice(&v.to_le_bytes());}
fn w32(b:&mut[u8],i:usize,v:u32){b[i..i+4].copy_from_slice(&v.to_le_bytes());}
const MAP:usize=128;
fn row(b:&mut[u8],i:usize,kind:u16,count:u32,offset:u32){
    let at=MAP+4+i*12;w16(b,at,kind);w32(b,at+4,count);w32(b,at+8,offset);
}
fn fixture()->Vec<u8>{
    let mut b=vec![0;256];b[..8].copy_from_slice(b"dex\n039\0");
    w32(&mut b,8,0x12345678);b[12..32].fill(0xAB);
    w32(&mut b,32,256);w32(&mut b,36,112);w32(&mut b,40,0x12345678);
    w32(&mut b,52,MAP as u32);w32(&mut b,56,2);w32(&mut b,60,112);
    w32(&mut b,64,1);w32(&mut b,68,120);
    w32(&mut b,104,128);w32(&mut b,108,128);
    w32(&mut b,MAP,5);row(&mut b,0,0,1,0);row(&mut b,1,1,2,112);
    row(&mut b,2,2,1,120);row(&mut b,3,0x1000,1,128);row(&mut b,4,0x2002,2,192);
    b
}
fn inspect(b:&[u8])->Verdict{
    let mut s=ReadSession::new(Cursor::new(b),b.len() as u64,8192,Cancellation::default());
    dex_structure::inspect(&mut s).unwrap()
}
#[test]
fn classic_versions_and_header_map_declarations(){
    for v in [35u16,37,38,39,40]{
        let mut b=fixture();b[4..7].copy_from_slice(format!("{v:03}").as_bytes());
        let Verdict::Checked(d)=inspect(&b)else{panic!("expected checked")};
        assert_eq!(d.version,v);assert_eq!(d.file_size,256);assert_eq!(d.strings.count,2);
        assert_eq!(d.types.offset,120);assert_eq!(d.map.len(),5);
        assert_eq!(d.checksum_declared,0x12345678);assert_eq!(d.signature_declared,[0xAB;20]);
    }
}
#[test]
fn version_endian_and_magic_outcomes(){
    let mut b=fixture();b[4..7].copy_from_slice(b"041");
    assert_eq!(inspect(&b),Verdict::Unsupported(Unsupported::Version));
    b[4..7].copy_from_slice(b"039");w32(&mut b,40,0x78563412);
    assert_eq!(inspect(&b),Verdict::Unsupported(Unsupported::ReverseEndian));
    b[0]=0;assert_eq!(inspect(&b),Verdict::Malformed(Issue::Signature));
}
#[test]
fn truncation_and_file_size(){
    let mut b=fixture();assert_eq!(inspect(&b[..7]),Verdict::Malformed(Issue::Truncated));
    assert_eq!(inspect(&b[..111]),Verdict::Malformed(Issue::Truncated));
    w32(&mut b,32,255);assert_eq!(inspect(&b),Verdict::Malformed(Issue::Field));
}
#[test]
fn fixed_table_bounds_and_overlap(){
    let mut b=fixture();w32(&mut b,56,u32::MAX);
    assert_eq!(inspect(&b),Verdict::Malformed(Issue::Bounds));
    w32(&mut b,56,2);w32(&mut b,68,116);
    assert_eq!(inspect(&b),Verdict::Malformed(Issue::Overlap));
}
#[test]
fn data_and_map_bounds(){
    let mut b=fixture();w32(&mut b,52,129);assert_eq!(inspect(&b),Verdict::Malformed(Issue::Bounds));
    w32(&mut b,52,128);w32(&mut b,MAP,11);
    assert_eq!(inspect(&b),Verdict::Malformed(Issue::Bounds));
    w32(&mut b,MAP,129);assert_eq!(inspect(&b),Verdict::Unsupported(Unsupported::MapLimit));
}
#[test]
fn duplicate_and_unsorted_map(){
    let mut b=fixture();row(&mut b,4,2,1,192);
    assert_eq!(inspect(&b),Verdict::Malformed(Issue::DuplicateType));
    row(&mut b,4,0x2002,2,124);assert_eq!(inspect(&b),Verdict::Malformed(Issue::MapOrder));
}
#[test]
fn map_cross_checks_and_known_extent(){
    let mut b=fixture();row(&mut b,1,1,1,112);
    assert_eq!(inspect(&b),Verdict::Malformed(Issue::MapMismatch));
    row(&mut b,1,1,2,112);row(&mut b,4,0x2002,2,180);
    assert_eq!(inspect(&b),Verdict::Malformed(Issue::Overlap));
    row(&mut b,4,0x2002,2,192);w32(&mut b,MAP,2);
    assert_eq!(inspect(&b),Verdict::Malformed(Issue::MapMismatch));
}
#[test]
fn unknown_map_kind_is_declaration_not_payload_validation(){
    let mut b=fixture();row(&mut b,4,0x7777,u32::MAX,192);
    let Verdict::Checked(d)=inspect(&b)else{panic!("expected checked")};
    assert_eq!(d.map[4].kind,0x7777);assert_eq!(d.map[4].count,u32::MAX);
}
#[test]
fn read_budget_exact_and_cancel(){
    let b=fixture();let c=Cancellation::default();
    let mut s=ReadSession::new(Cursor::new(&b),256,176,c.clone());
    assert!(matches!(dex_structure::inspect(&mut s).unwrap(),Verdict::Checked(_)));
    assert_eq!(s.remaining_budget(),0);
    let mut s=ReadSession::new(Cursor::new(&b),256,175,c.clone());
    assert_eq!(dex_structure::inspect(&mut s).unwrap_err().kind(),io::ErrorKind::Other);
    assert_eq!(s.remaining_budget(),59);
    c.cancel();assert_eq!(dex_structure::inspect(&mut s).unwrap_err().kind(),io::ErrorKind::Interrupted);
}
#[test]
fn truncated_backing_map_read_remains_charged(){
    let b=fixture();let mut s=ReadSession::new(Cursor::new(&b[..150]),256,176,Cancellation::default());
    assert_eq!(dex_structure::inspect(&mut s).unwrap_err().kind(),io::ErrorKind::UnexpectedEof);
    assert_eq!(s.remaining_budget(),0);
}
