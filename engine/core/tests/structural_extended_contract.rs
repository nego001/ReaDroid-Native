use negrodroid_core::{Cancellation,ReadSession,format::FormatHint,structural::{inspect,Header,Issue,Verdict,ByteOrder}};
use std::io::Cursor;
fn check(b:&[u8],h:FormatHint)->Verdict{
    inspect(&mut ReadSession::new(Cursor::new(b),b.len() as u64,112,Cancellation::default()),h).unwrap()
}
fn p16(b:&mut [u8],i:usize,v:u16){b[i..i+2].copy_from_slice(&v.to_le_bytes());}
fn p32(b:&mut [u8],i:usize,v:u32){b[i..i+4].copy_from_slice(&v.to_le_bytes());}
fn pe(bits:u8)->Vec<u8>{
    let optional=if bits==32{224}else{240};
    let mut b=vec![0;128+24+optional+40];
    b[..2].copy_from_slice(b"MZ");p32(&mut b,60,128);
    b[128..132].copy_from_slice(b"PE\0\0");
    p16(&mut b,132,if bits==32{0x14c}else{0x8664});
    p16(&mut b,134,1);p16(&mut b,148,optional as u16);
    p16(&mut b,152,if bits==32{0x10b}else{0x20b});b
}
fn dex()->Vec<u8>{
    let mut b=vec![0;116];b[..8].copy_from_slice(b"dex\n035\0");
    p32(&mut b,32,116);p32(&mut b,36,112);p32(&mut b,40,0x12345678);
    p32(&mut b,52,112);p32(&mut b,104,4);p32(&mut b,108,112);b
}
fn zip()->Vec<u8>{
    let mut b=vec![0;34];b[..4].copy_from_slice(b"PK\x03\x04");p16(&mut b,4,20);
    p32(&mut b,18,3);p32(&mut b,22,3);p16(&mut b,26,1);b[30]=b'a';b
}
#[test]
fn pe32_and_pe64(){
    assert_eq!(check(&pe(32),FormatHint::PortableExecutable),Verdict::HeaderChecked(Header::Pe{bits:32,machine:0x14c,sections:1}));
    assert_eq!(check(&pe(64),FormatHint::PortableExecutable),Verdict::HeaderChecked(Header::Pe{bits:64,machine:0x8664,sections:1}));
}
#[test]
fn pe_rejects_bad_signature_and_pointer(){
    let mut b=pe(64);b[128]=0;assert_eq!(check(&b,FormatHint::PortableExecutable),Verdict::Malformed(Issue::Signature));
    p32(&mut b,60,u32::MAX);assert_eq!(check(&b,FormatHint::PortableExecutable),Verdict::Malformed(Issue::TableBounds));
}
#[test]
fn pe_section_bounds_and_optional_size(){
    let mut b=pe(32);b.pop();assert_eq!(check(&b,FormatHint::PortableExecutable),Verdict::Malformed(Issue::TableBounds));
    p16(&mut b,148,2);assert_eq!(check(&b,FormatHint::PortableExecutable),Verdict::Malformed(Issue::Field));
}
#[test]
fn pe_budget_counts_both_reads(){
    let b=pe(64);let n=b.len() as u64;
    let mut s=ReadSession::new(Cursor::new(&b),n,90,Cancellation::default());
    assert!(matches!(inspect(&mut s,FormatHint::PortableExecutable).unwrap(),Verdict::HeaderChecked(_)));
    assert_eq!(s.remaining_budget(),0);
    let mut s=ReadSession::new(Cursor::new(&b),n,89,Cancellation::default());
    assert!(inspect(&mut s,FormatHint::PortableExecutable).is_err());
}
#[test]
fn dex_header_only(){
    assert_eq!(check(&dex(),FormatHint::Dex),Verdict::HeaderChecked(Header::Dex{version:35,byte_order:ByteOrder::Little,file_size:116}));
}
#[test]
fn dex_versions_and_reverse_endian_are_explicitly_unsupported(){
    let mut b=dex();b[4..7].copy_from_slice(b"041");assert_eq!(check(&b,FormatHint::Dex),Verdict::Unsupported);
    b[4..7].copy_from_slice(b"035");p32(&mut b,40,0x78563412);assert_eq!(check(&b,FormatHint::Dex),Verdict::Unsupported);
}
#[test]
fn dex_inconsistent_length_and_out_of_bounds_tables(){
    let mut b=dex();p32(&mut b,32,115);assert_eq!(check(&b,FormatHint::Dex),Verdict::Malformed(Issue::Field));
    p32(&mut b,32,116);p32(&mut b,96,u32::MAX);p32(&mut b,100,112);
    assert_eq!(check(&b,FormatHint::Dex),Verdict::Malformed(Issue::TableBounds));
}
#[test]
fn dex_data_and_map_bounds(){
    let mut b=dex();p32(&mut b,52,116);assert_eq!(check(&b,FormatHint::Dex),Verdict::Malformed(Issue::TableBounds));
    p32(&mut b,52,112);p32(&mut b,104,0);assert_eq!(check(&b,FormatHint::Dex),Verdict::Malformed(Issue::TableBounds));
}
#[test]
fn zip_first_local_header_only(){
    assert_eq!(check(&zip(),FormatHint::Zip),Verdict::HeaderChecked(Header::ZipLocal{method:0,compressed:3,uncompressed:3}));
}
#[test]
fn zip_special_features_are_not_parsed(){
    for flag in [1,8,64,8192]{let mut b=zip();p16(&mut b,6,flag);assert_eq!(check(&b,FormatHint::Zip),Verdict::Unsupported);}
    let mut b=zip();p32(&mut b,18,u32::MAX);assert_eq!(check(&b,FormatHint::Zip),Verdict::Unsupported);
}
#[test]
fn zip_length_and_stored_size_checks(){
    let mut b=zip();b.pop();assert_eq!(check(&b,FormatHint::Zip),Verdict::Malformed(Issue::TableBounds));
    p32(&mut b,22,4);assert_eq!(check(&b,FormatHint::Zip),Verdict::Malformed(Issue::Field));
}
#[test]
fn empty_zip_end_record_and_truncation(){
    let mut b=vec![0;22];b[..4].copy_from_slice(b"PK\x05\x06");
    assert_eq!(check(&b,FormatHint::Zip),Verdict::HeaderChecked(Header::ZipEmpty));
    b.pop();assert_eq!(check(&b,FormatHint::Zip),Verdict::Malformed(Issue::Truncated));
}
#[test]
fn new_formats_truncation_and_cancellation(){
    for (b,h,min) in [(pe(32),FormatHint::PortableExecutable,64),(dex(),FormatHint::Dex,112),(zip(),FormatHint::Zip,30)]{
        for n in 0..min{assert_eq!(check(&b[..n],h),Verdict::Malformed(Issue::Truncated));}
        let c=Cancellation::default();c.cancel();let n=b.len() as u64;
        assert!(inspect(&mut ReadSession::new(Cursor::new(b),n,112,c),h).is_err());
    }
}
