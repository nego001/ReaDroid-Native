use negrodroid_core::{Cancellation,ReadSession,format::FormatHint,structural::{inspect,ByteOrder,Header,Issue,Verdict}};
use std::io::Cursor;

fn check(b:&[u8],hint:FormatHint)->Verdict {
    inspect(&mut ReadSession::new(Cursor::new(b),b.len() as u64,64,Cancellation::default()),hint).unwrap()
}
fn elf64()->Vec<u8>{
    let mut b=vec![0;64];
    b[..7].copy_from_slice(b"\x7fELF\x02\x01\x01");
    b[16..18].copy_from_slice(&1u16.to_le_bytes());
    b[18..20].copy_from_slice(&62u16.to_le_bytes());
    b[20..24].copy_from_slice(&1u32.to_le_bytes());
    b[52..54].copy_from_slice(&64u16.to_le_bytes());
    b
}
fn elf32be()->Vec<u8>{
    let mut b=vec![0;52];
    b[..7].copy_from_slice(b"\x7fELF\x01\x02\x01");
    b[16..18].copy_from_slice(&1u16.to_be_bytes());
    b[18..20].copy_from_slice(&20u16.to_be_bytes());
    b[20..24].copy_from_slice(&1u32.to_be_bytes());
    b[40..42].copy_from_slice(&52u16.to_be_bytes());
    b
}
// Known CRC for 1x1 RGBA IHDR; deliberately no IDAT or IEND.
fn png()->Vec<u8>{b"\x89PNG\r\n\x1a\n\x00\x00\x00\x0dIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89".to_vec()}
#[test]
fn elf_64_little_and_32_big_endian(){
    assert_eq!(check(&elf64(),FormatHint::Elf),Verdict::HeaderChecked(Header::Elf{bits:64,byte_order:ByteOrder::Little,machine:62}));
    assert_eq!(check(&elf32be(),FormatHint::Elf),Verdict::HeaderChecked(Header::Elf{bits:32,byte_order:ByteOrder::Big,machine:20}));
}
#[test]
fn elf_truncation_and_wrong_signature(){
    for n in 0..64 {assert_eq!(check(&elf64()[..n],FormatHint::Elf),Verdict::Malformed(Issue::Truncated));}
    let mut b=elf64();b[0]=0;assert_eq!(check(&b,FormatHint::Elf),Verdict::Malformed(Issue::Signature));
}
#[test]
fn elf_invalid_header_fields(){
    for i in [4,5,6,20,52] {let mut b=elf64();b[i]=0;assert_eq!(check(&b,FormatHint::Elf),Verdict::Malformed(Issue::Field));}
}
#[test]
fn elf_table_range_and_overflow(){
    let mut b=elf64();b.resize(120,0);
    b[32..40].copy_from_slice(&64u64.to_le_bytes());
    b[54..56].copy_from_slice(&56u16.to_le_bytes());b[56..58].copy_from_slice(&1u16.to_le_bytes());
    assert!(matches!(check(&b,FormatHint::Elf),Verdict::HeaderChecked(_)));
    b.pop();assert_eq!(check(&b,FormatHint::Elf),Verdict::Malformed(Issue::TableBounds));
    b[32..40].copy_from_slice(&u64::MAX.to_le_bytes());
    assert_eq!(check(&b,FormatHint::Elf),Verdict::Malformed(Issue::TableBounds));
}
#[test]
fn elf_extended_numbering_is_not_claimed(){
    let mut b=elf64();b[56..58].copy_from_slice(&0xffffu16.to_le_bytes());
    assert_eq!(check(&b,FormatHint::Elf),Verdict::Unsupported);
}
#[test]
fn png_known_header_and_crc(){
    assert_eq!(check(&png(),FormatHint::Png),Verdict::HeaderChecked(Header::Png{width:1,height:1,bit_depth:8,color_type:6}));
}
#[test]
fn png_short_wrong_magic_and_chunk(){
    let b=png();for n in 0..33 {assert_eq!(check(&b[..n],FormatHint::Png),Verdict::Malformed(Issue::Truncated));}
    let mut b=png();b[0]=0;assert_eq!(check(&b,FormatHint::Png),Verdict::Malformed(Issue::Signature));
    let mut b=png();b[15]=0;assert_eq!(check(&b,FormatHint::Png),Verdict::Malformed(Issue::Field));
}
#[test]
fn png_fields_and_crc_checked(){
    for (i,v) in [(19,0),(23,0),(24,1),(25,5),(26,1),(27,1),(28,2)]{
        let mut b=png();b[i]=v;assert_eq!(check(&b,FormatHint::Png),Verdict::Malformed(Issue::Field));
    }
    let mut b=png();b[32]^=1;assert_eq!(check(&b,FormatHint::Png),Verdict::Malformed(Issue::Checksum));
}
#[test]
fn unsupported_does_not_read_and_supported_obeys_budget(){
    let b=elf64();let mut s=ReadSession::new(Cursor::new(&b),64,0,Cancellation::default());
    assert_eq!(inspect(&mut s,FormatHint::Jpeg).unwrap(),Verdict::Unsupported);
    assert!(inspect(&mut s,FormatHint::Elf).is_err());
}
#[test]
fn cancelled_or_physically_truncated_reader_is_error(){
    let c=Cancellation::default();c.cancel();
    assert!(inspect(&mut ReadSession::new(Cursor::new(elf64()),64,64,c),FormatHint::Elf).is_err());
    assert!(inspect(&mut ReadSession::new(Cursor::new(vec![0;4]),64,64,Cancellation::default()),FormatHint::Elf).is_err());
}
#[test]
fn large_source_reads_at_most_header(){
    let mut b=elf64();b.resize(8192,0);
    let mut s=ReadSession::new(Cursor::new(b),8192,64,Cancellation::default());
    assert!(matches!(inspect(&mut s,FormatHint::Elf).unwrap(),Verdict::HeaderChecked(_)));
    assert_eq!(s.remaining_budget(),0);
}
