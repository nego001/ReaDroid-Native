use negrodroid_core::{Cancellation,ReadSession,pe_structure::{self,Kind,Issue,Unsupported,Verdict,Mapping}};
use std::io::{self,Cursor};
fn w16(b:&mut[u8],i:usize,v:u16){b[i..i+2].copy_from_slice(&v.to_le_bytes());}
fn w32(b:&mut[u8],i:usize,v:u32){b[i..i+4].copy_from_slice(&v.to_le_bytes());}
fn w64(b:&mut[u8],i:usize,v:u64){b[i..i+8].copy_from_slice(&v.to_le_bytes());}
const PE:usize=128;const OPT:usize=PE+24;
fn fixture(plus:bool)->(Vec<u8>,usize){
    let mut b=vec![0;1024];
    b[..2].copy_from_slice(b"MZ");w32(&mut b,60,PE as u32);
    b[PE..PE+4].copy_from_slice(b"PE\0\0");w16(&mut b,PE+4,if plus{0x8664}else{0x14c});
    w16(&mut b,PE+6,2);let min=if plus{112}else{96};let size=min+16;
    w16(&mut b,PE+20,size as u16);w16(&mut b,PE+22,2);
    w16(&mut b,OPT,if plus{0x20b}else{0x10b});w32(&mut b,OPT+16,0x1000);
    if plus{w64(&mut b,OPT+24,0x140000000)}else{w32(&mut b,OPT+28,0x400000)}
    w32(&mut b,OPT+32,4096);w32(&mut b,OPT+36,512);w32(&mut b,OPT+56,0x3000);w32(&mut b,OPT+60,512);
    w32(&mut b,OPT+min-4,2);w32(&mut b,OPT+min+8,0x1000);w32(&mut b,OPT+min+12,8);
    let tab=OPT+size;
    b[tab..tab+5].copy_from_slice(b".text");w32(&mut b,tab+8,600);w32(&mut b,tab+12,0x1000);
    w32(&mut b,tab+16,512);w32(&mut b,tab+20,512);w32(&mut b,tab+36,0x60000020);
    b[tab+40..tab+44].copy_from_slice(b".bss");w32(&mut b,tab+48,100);w32(&mut b,tab+52,0x2000);
    (b,tab)
}
fn check(b:&[u8])->Verdict{
    let mut s=ReadSession::new(Cursor::new(b),b.len() as u64,8192,Cancellation::default());
    pe_structure::inspect(&mut s).unwrap()
}
#[test]
fn pe32_pe32plus_headers_sections_and_directory_declarations(){
    for plus in [false,true]{
        let (b,_)=fixture(plus);
        let Verdict::Checked(p)=check(&b)else{panic!("expected checked")};
        assert_eq!(p.kind,if plus{Kind::Pe32Plus}else{Kind::Pe32});
        assert_eq!(p.image_base,if plus{0x140000000}else{0x400000});
        assert_eq!(p.entry_rva,0x1000);assert_eq!(p.sections.len(),2);
        assert_eq!(p.sections[0].name,*b".text\0\0\0");
        assert_eq!(p.directories[1].address,0x1000);assert_eq!(p.directories[1].size,8);
        assert_eq!(p.map_rva(0),Mapping::FileOffset(0));
        assert_eq!(p.map_rva(0x1001),Mapping::FileOffset(513));
        assert_eq!(p.map_rva(0x1200),Mapping::VirtualOnly);
        assert_eq!(p.map_rva(0x2000),Mapping::VirtualOnly);
        assert_eq!(p.map_rva(0x2064),Mapping::Unmapped);
        assert_eq!(p.map_rva(0x3000),Mapping::Unmapped);
    }
}
#[test]
fn truncated_and_wrong_signatures(){
    let (mut b,_)=fixture(false);
    assert_eq!(check(&b[..63]),Verdict::Malformed(Issue::Truncated));
    b[0]=0;assert_eq!(check(&b),Verdict::Malformed(Issue::Signature));b[0]=b'M';
    b[PE]=0;assert_eq!(check(&b),Verdict::Malformed(Issue::Signature));
}
#[test]
fn invalid_pe_offset_and_section_table(){
    let (mut b,t)=fixture(false);
    assert_eq!(check(&b[..t+79]),Verdict::Malformed(Issue::TableBounds));
    w32(&mut b,60,u32::MAX);assert_eq!(check(&b),Verdict::Malformed(Issue::TableBounds));
    w32(&mut b,60,63);assert_eq!(check(&b),Verdict::Malformed(Issue::TableBounds));
}
#[test]
fn unsupported_magic_and_optional_limit(){
    let (mut b,_)=fixture(false);w16(&mut b,OPT,0x107);
    assert_eq!(check(&b),Verdict::Unsupported(Unsupported::OptionalMagic));
    w16(&mut b,PE+20,4097);assert_eq!(check(&b),Verdict::Unsupported(Unsupported::OptionalSize));
}
#[test]
fn declared_directories_must_fit_optional_header(){
    let (mut b,_)=fixture(false);w32(&mut b,OPT+92,3);
    assert_eq!(check(&b),Verdict::Malformed(Issue::TableBounds));
}
#[test]
fn raw_ranges_and_overlap(){
    let (mut b,t)=fixture(false);w32(&mut b,t+20,513);
    assert_eq!(check(&b),Verdict::Malformed(Issue::RawBounds));
    w32(&mut b,t+20,511);assert_eq!(check(&b),Verdict::Malformed(Issue::RawBounds));
    w32(&mut b,t+20,512);w32(&mut b,t+56,1);w32(&mut b,t+60,512);
    assert_eq!(check(&b),Verdict::Malformed(Issue::Overlap));
}
#[test]
fn virtual_ranges_and_overlap(){
    let (mut b,t)=fixture(false);w32(&mut b,t+52,0x1100);
    assert_eq!(check(&b),Verdict::Malformed(Issue::Overlap));
    w32(&mut b,t+52,u32::MAX);
    assert_eq!(check(&b),Verdict::Malformed(Issue::VirtualBounds));
}
#[test]
fn structural_limits_and_header_bounds(){
    let (mut b,_)=fixture(false);w16(&mut b,PE+6,97);
    assert_eq!(check(&b),Verdict::Malformed(Issue::Field));
    w16(&mut b,PE+6,2);w32(&mut b,OPT+60,64);
    assert_eq!(check(&b),Verdict::Malformed(Issue::Field));
}
#[test]
fn budget_and_cancellation_no_partial_report(){
    let (b,_)=fixture(false);let c=Cancellation::default();
    let mut s=ReadSession::new(Cursor::new(&b),b.len() as u64,100,c.clone());
    assert_eq!(pe_structure::inspect(&mut s).unwrap_err().kind(),io::ErrorKind::Other);
    assert_eq!(s.remaining_budget(),12);
    c.cancel();assert_eq!(pe_structure::inspect(&mut s).unwrap_err().kind(),io::ErrorKind::Interrupted);
    assert_eq!(s.remaining_budget(),12);
}
#[test]
fn truncated_backing_read_charged_and_header_only_io(){
    let (b,t)=fixture(true);
    let mut s=ReadSession::new(Cursor::new(&b[..t+10]),b.len() as u64,8192,Cancellation::default());
    assert_eq!(pe_structure::inspect(&mut s).unwrap_err().kind(),io::ErrorKind::UnexpectedEof);
    let mut s=ReadSession::new(Cursor::new(&b),b.len() as u64,8192,Cancellation::default());
    assert!(matches!(pe_structure::inspect(&mut s).unwrap(),Verdict::Checked(_)));
    assert_eq!(8192-s.remaining_budget(),64+24+128+80);
}
