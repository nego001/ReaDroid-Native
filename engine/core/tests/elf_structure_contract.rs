use negrodroid_core::{Cancellation,ReadSession,elf_structure::{self,Class,Order,Issue,Unsupported,Verdict,Mapping}};
use std::io::{self,Cursor};
fn put(b:&mut[u8],at:usize,n:usize,v:u64,o:Order){
    let bytes=match o{Order::Little=>v.to_le_bytes(),Order::Big=>v.to_be_bytes()};
    b[at..at+n].copy_from_slice(match o{Order::Little=>&bytes[..n],Order::Big=>&bytes[8-n..]});
}
struct Fixture{b:Vec<u8>,h:usize,pw:usize,sw:usize,ph:usize,sh:usize,word:usize,order:Order}
fn fixture(class:Class,order:Order)->Fixture{
    let (h,pw,sw,word)=match class{Class::Elf32=>(52,32,40,4),Class::Elf64=>(64,56,64,8)};
    let ph=h;let sh=ph+pw*2;
    let mut b=vec![0;1024];b[..4].copy_from_slice(b"\x7fELF");
    b[4]=if class==Class::Elf32{1}else{2};b[5]=if order==Order::Little{1}else{2};b[6]=1;
    for (at,n,v) in [(16,2,3),(18,2,if word==4{3}else{62}),(20,4,1),(24,word,0x1000),
        (24+word,word,ph as u64),(24+2*word,word,sh as u64),(h-12,2,h as u64),
        (h-10,2,pw as u64),(h-8,2,2),(h-6,2,sw as u64),(h-4,2,3),(h-2,2,2)]{
        put(&mut b,at,n,v,order);
    }
    let fields:Vec<(usize,usize,u64)>=if word==4{vec![(0,4,1),(4,4,512),(8,4,0x1000),(16,4,64),(20,4,128),(24,4,5),(28,4,512)]}
        else{vec![(0,4,1),(4,4,5),(8,8,512),(16,8,0x1000),(32,8,64),(40,8,128),(48,8,512)]};
    for (at,n,v) in fields{put(&mut b,ph+at,n,v,order);}
    for (idx,kind,flags,address,offset,size,align) in [(1,8,2,0x1040,576,64,16),(2,3,0,0,640,32,1)]{
        let at=sh+idx*sw;
        for (off,n,v) in [(0,4,idx as u64),(4,4,kind),(8,word,flags),(8+word,word,address),
            (8+2*word,word,offset),(8+3*word,word,size),(16+4*word,word,align)]{
            put(&mut b,at+off,n,v,order);
        }
    }
    Fixture{b,h,pw,sw,ph,sh,word,order}
}
fn inspect(b:&[u8])->Verdict{
    let mut s=ReadSession::new(Cursor::new(b),b.len() as u64,300000,Cancellation::default());
    elf_structure::inspect(&mut s).unwrap()
}
#[test]
fn both_classes_and_byte_orders(){
    for class in [Class::Elf32,Class::Elf64]{for order in [Order::Little,Order::Big]{
        let f=fixture(class,order);let Verdict::Checked(p)=inspect(&f.b)else{panic!("expected checked")};
        assert_eq!((p.class,p.order,p.entry,p.kind),(class,order,0x1000,3));
        assert_eq!(p.machine,if class==Class::Elf32{3}else{62});
        assert_eq!(p.segments.len(),2);assert_eq!(p.sections.len(),3);assert_eq!(p.section_names,Some(2));
        assert_eq!(p.sections[1].kind,8);assert_eq!(p.sections[1].size,64);assert_eq!(p.segments[0].flags,5);
        assert_eq!(p.map_vaddr(0x1000),Mapping::FileOffset(512));
        assert_eq!(p.map_vaddr(0x103f),Mapping::FileOffset(575));
        assert_eq!(p.map_vaddr(0x1040),Mapping::VirtualOnly);
        assert_eq!(p.map_vaddr(0x1080),Mapping::Unmapped);
    }}
}
#[test]
fn truncated_signature_and_ident_fields(){
    let mut f=fixture(Class::Elf64,Order::Little);
    assert_eq!(inspect(&f.b[..15]),Verdict::Malformed(Issue::Truncated));
    assert_eq!(inspect(&f.b[..63]),Verdict::Malformed(Issue::Truncated));
    f.b[0]=0;assert_eq!(inspect(&f.b),Verdict::Malformed(Issue::Signature));
    f.b[0]=0x7f;f.b[5]=0;assert_eq!(inspect(&f.b),Verdict::Malformed(Issue::Field));
}
#[test]
fn extended_numbering_and_table_limits(){
    let mut f=fixture(Class::Elf64,Order::Big);
    put(&mut f.b,f.h-8,2,0xffff,f.order);
    assert_eq!(inspect(&f.b),Verdict::Unsupported(Unsupported::ExtendedNumbering));
    put(&mut f.b,f.h-8,2,257,f.order);
    assert_eq!(inspect(&f.b),Verdict::Unsupported(Unsupported::TableLimit));
}
#[test]
fn table_bounds_entry_size_and_overflow(){
    let mut f=fixture(Class::Elf64,Order::Little);
    put(&mut f.b,32,8,u64::MAX,f.order);
    assert_eq!(inspect(&f.b),Verdict::Malformed(Issue::TableBounds));
    put(&mut f.b,32,8,f.ph as u64,f.order);
    put(&mut f.b,f.h-10,2,55,f.order);
    assert_eq!(inspect(&f.b),Verdict::Malformed(Issue::TableBounds));
}
#[test]
fn segment_file_and_memory_extent_checks(){
    let mut f=fixture(Class::Elf64,Order::Little);
    put(&mut f.b,f.ph+8,8,1000,f.order);
    assert_eq!(inspect(&f.b),Verdict::Malformed(Issue::FileBounds));
    put(&mut f.b,f.ph+8,8,512,f.order);
    put(&mut f.b,f.ph+40,8,63,f.order);
    assert_eq!(inspect(&f.b),Verdict::Malformed(Issue::VirtualBounds));
    put(&mut f.b,f.ph+40,8,128,f.order);put(&mut f.b,f.ph+16,8,u64::MAX,f.order);
    assert_eq!(inspect(&f.b),Verdict::Malformed(Issue::VirtualBounds));
}
#[test]
fn alignment_and_congruence(){
    let mut f=fixture(Class::Elf32,Order::Big);
    put(&mut f.b,f.ph+28,4,3,f.order);
    assert_eq!(inspect(&f.b),Verdict::Malformed(Issue::Alignment));
    put(&mut f.b,f.ph+28,4,512,f.order);put(&mut f.b,f.ph+4,4,513,f.order);
    assert_eq!(inspect(&f.b),Verdict::Malformed(Issue::Alignment));
}
#[test]
fn nobits_has_no_file_payload_and_section_bounds(){
    let mut f=fixture(Class::Elf64,Order::Little);
    let at=f.sh+f.sw;
    put(&mut f.b,at+8+2*f.word,f.word,u64::MAX,f.order);
    assert!(matches!(inspect(&f.b),Verdict::Checked(_)));
    put(&mut f.b,at+4,4,1,f.order);
    assert_eq!(inspect(&f.b),Verdict::Malformed(Issue::FileBounds));
}
#[test]
fn overlapping_load_mapping_is_ambiguous(){
    let mut f=fixture(Class::Elf64,Order::Little);
    let a=f.b[f.ph..f.ph+f.pw].to_vec();
    f.b[f.ph+f.pw..f.ph+2*f.pw].copy_from_slice(&a);
    let Verdict::Checked(p)=inspect(&f.b)else{panic!("expected checked")};
    assert_eq!(p.map_vaddr(0x1000),Mapping::Ambiguous);
}
#[test]
fn section_string_table_index_and_type(){
    let mut f=fixture(Class::Elf64,Order::Little);
    put(&mut f.b,f.h-2,2,3,f.order);
    assert_eq!(inspect(&f.b),Verdict::Malformed(Issue::Field));
    put(&mut f.b,f.h-2,2,1,f.order);
    assert_eq!(inspect(&f.b),Verdict::Malformed(Issue::Field));
}
#[test]
fn exact_header_table_budget_and_cancel(){
    let f=fixture(Class::Elf64,Order::Little);let c=Cancellation::default();
    let needed=(f.h+2*f.pw+3*f.sw) as u64;
    let mut s=ReadSession::new(Cursor::new(&f.b),f.b.len() as u64,needed,c.clone());
    assert!(matches!(elf_structure::inspect(&mut s).unwrap(),Verdict::Checked(_)));
    assert_eq!(s.remaining_budget(),0);
    let mut s=ReadSession::new(Cursor::new(&f.b),f.b.len() as u64,needed-1,c.clone());
    assert_eq!(elf_structure::inspect(&mut s).unwrap_err().kind(),io::ErrorKind::Other);
    assert_eq!(s.remaining_budget(),needed-1-f.h as u64);
    c.cancel();assert_eq!(elf_structure::inspect(&mut s).unwrap_err().kind(),io::ErrorKind::Interrupted);
}
