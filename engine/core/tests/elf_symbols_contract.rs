use negrodroid_core::{Cancellation,ReadSession,elf_structure::{Class,Order},elf_symbols::{Inspector,Name,SectionRef,MAX_PAGE}};
use std::io::{self,Cursor};
fn put(b:&mut[u8],at:usize,n:usize,v:u64,o:Order){
    let bytes=if o==Order::Little{v.to_le_bytes()}else{v.to_be_bytes()};
    b[at..at+n].copy_from_slice(if o==Order::Little{&bytes[..n]}else{&bytes[8-n..]});
}
struct F{b:Vec<u8>,h:usize,w:usize,sw:usize,sym:usize,order:Order}
fn fixture(class:Class,order:Order)->F{
    let (h,w,sw,sym)=if class==Class::Elf32{(52,4,40,16)}else{(64,8,64,24)};
    let mut b=vec![0u8;1024];b[..4].copy_from_slice(b"\x7fELF");
    b[4]=if w==4{1}else{2};b[5]=if order==Order::Little{1}else{2};b[6]=1;
    for (at,n,v) in [(16,2,1),(18,2,if w==4{3}else{62}),(20,4,1),(24+2*w,w,h as u64),(h-12,2,h as u64),
        (h-6,2,sw as u64),(h-4,2,5),(h-2,2,1)]{put(&mut b,at,n,v,order);}
    let names=b"\0.shstrtab\0.strtab\0.symtab\0.text\0";
    let strings=b"\0alpha\0beta\0";
    b[512..512+names.len()].copy_from_slice(names);
    b[560..560+strings.len()].copy_from_slice(strings);
    for (idx,name,kind,offset,size,link,info,ent) in [
        (1,1,3,512,names.len() as u64,0,0,0),(2,11,3,560,strings.len() as u64,0,0,0),
        (3,19,2,600,3*sym as u64,2,1,sym as u64),(4,27,1,800,8,0,0,0)]{
        let at=h+idx*sw;
        for (p,n,v) in [(0,4,name),(4,4,kind),(8+2*w,w,offset),(8+3*w,w,size),(8+4*w,4,link),
            (12+4*w,4,info),(16+4*w,w,1),(16+5*w,w,ent)]{put(&mut b,at+p,n,v,order);}
    }
    for (idx,name,val,sh) in [(1,1,0x1234,4),(2,7,0x5678,0xffff)]{
        let at=600+idx*sym;put(&mut b,at,4,name,order);
        if w==4{put(&mut b,at+4,4,val,order);put(&mut b,at+8,4,4,order);b[at+12]=0x12;b[at+13]=2;put(&mut b,at+14,2,sh,order);}
        else{b[at+4]=0x12;b[at+5]=2;put(&mut b,at+6,2,sh,order);put(&mut b,at+8,8,val,order);put(&mut b,at+16,8,4,order);}
    }
    F{b,h,w,sw,sym,order}
}
fn open(b:&[u8],budget:u64)->Inspector<Cursor<&[u8]>>{
    Inspector::open(ReadSession::new(Cursor::new(b),b.len() as u64,budget,Cancellation::default())).unwrap()
}
#[test]
fn all_classes_orders_and_symbol_metadata(){
    for class in [Class::Elf32,Class::Elf64]{for order in [Order::Little,Order::Big]{
        let f=fixture(class,order);let mut i=open(&f.b,4096);
        let p=i.sections(0,5).unwrap();assert_eq!(p.total,5);
        assert_eq!(p.entries[4].name,Name::Bytes(b".text".to_vec()));
        let p=i.symbols(3,0,3).unwrap();assert_eq!(p.total,3);assert_eq!(p.next,None);
        assert_eq!(p.entries[0].section,SectionRef::Undefined);
        assert_eq!(p.entries[1].name,Name::Bytes(b"alpha".to_vec()));
        assert_eq!((p.entries[1].value,p.entries[1].size,p.entries[1].binding,p.entries[1].kind,p.entries[1].visibility),(0x1234,4,1,2,2));
        assert_eq!(p.entries[1].section,SectionRef::Index(4));
        assert_eq!(p.entries[2].section,SectionRef::ExtendedUnsupported);
    }}
}
#[test]
fn pagination_and_empty_end(){
    let f=fixture(Class::Elf64,Order::Little);let mut i=open(&f.b,4096);
    assert_eq!(i.sections(0,2).unwrap().next,Some(2));assert_eq!(i.sections(2,3).unwrap().next,None);
    let p=i.symbols(3,1,1).unwrap();assert_eq!(p.next,Some(2));assert_eq!(p.entries[0].index,1);
    let p=i.symbols(3,3,1).unwrap();assert!(p.entries.is_empty());assert_eq!(p.next,None);
    assert!(i.symbols(3,4,1).is_err());assert!(i.sections(0,MAX_PAGE+1).is_err());
}
#[test]
fn missing_section_names_explicit(){
    let mut f=fixture(Class::Elf32,Order::Big);put(&mut f.b,f.h-2,2,0,f.order);
    let mut i=open(&f.b,4096);assert!(i.sections(0,5).unwrap().entries.iter().all(|e|e.name==Name::Absent));
}
#[test]
fn string_boundary_and_name_index_rejected(){
    let mut f=fixture(Class::Elf64,Order::Little);f.b[560]=1;
    let mut i=open(&f.b,4096);assert_eq!(i.symbols(3,1,1).unwrap_err().kind(),io::ErrorKind::InvalidData);
    f.b[560]=0;put(&mut f.b,600+f.sym,4,500,f.order);
    let mut i=open(&f.b,4096);assert_eq!(i.symbols(3,1,1).unwrap_err().kind(),io::ErrorKind::InvalidData);
}
#[test]
fn long_names_are_explicit_and_raw_non_utf8_preserved(){
    let mut f=fixture(Class::Elf64,Order::Little);
    f.b[561]=0xff;
    let mut i=open(&f.b,4096);assert_eq!(i.symbols(3,1,1).unwrap().entries[0].name,Name::Bytes(vec![0xff,b'l',b'p',b'h',b'a']));
    // Move linked string table to a disjoint region beyond original fixture.
    f.b.resize(1600,0);let t=f.h+2*f.sw;
    put(&mut f.b,t+8+2*f.w,f.w,1024,f.order);put(&mut f.b,t+8+3*f.w,f.w,300,f.order);
    f.b[1025..1323].fill(b'x');
    let mut i=open(&f.b,4096);assert_eq!(i.symbols(3,1,1).unwrap().entries[0].name,Name::TooLong);
}
#[test]
fn bad_link_and_entry_width(){
    let mut f=fixture(Class::Elf64,Order::Little);let t=f.h+3*f.sw;
    put(&mut f.b,t+8+4*f.w,4,4,f.order);
    let mut i=open(&f.b,4096);assert!(i.symbols(3,0,1).is_err());
    put(&mut f.b,t+8+4*f.w,4,2,f.order);put(&mut f.b,t+16+5*f.w,f.w,23,f.order);
    let mut i=open(&f.b,4096);assert!(i.symbols(3,0,1).is_err());
}
#[test]
fn compressed_tables_unsupported(){
    let mut f=fixture(Class::Elf64,Order::Little);let t=f.h+3*f.sw;
    put(&mut f.b,t+8,f.w,0x800,f.order);
    let mut i=open(&f.b,4096);assert_eq!(i.symbols(3,0,1).unwrap_err().kind(),io::ErrorKind::Unsupported);
    put(&mut f.b,t+8,f.w,0,f.order);put(&mut f.b,f.h+2*f.sw+8,f.w,0x800,f.order);
    let mut i=open(&f.b,4096);assert_eq!(i.symbols(3,0,1).unwrap_err().kind(),io::ErrorKind::Unsupported);
}
#[test]
fn reserved_and_invalid_section_reference(){
    let mut f=fixture(Class::Elf32,Order::Little);
    put(&mut f.b,600+f.sym+14,2,0xfff1,f.order);
    let mut i=open(&f.b,4096);assert_eq!(i.symbols(3,1,1).unwrap().entries[0].section,SectionRef::Reserved(0xfff1));
    put(&mut f.b,600+f.sym+14,2,5,f.order);
    let mut i=open(&f.b,4096);assert!(i.symbols(3,1,1).is_err());
}
#[test]
fn bounded_read_budget_and_cancellation(){
    let f=fixture(Class::Elf64,Order::Little);let c=Cancellation::default();
    let mut i=Inspector::open(ReadSession::new(Cursor::new(&f.b),f.b.len() as u64,(f.h+5*f.sw+2) as u64,c.clone())).unwrap();
    assert_eq!(i.symbols(3,0,1).unwrap_err().kind(),io::ErrorKind::Other);
    assert_eq!(i.remaining_budget(),0);c.cancel();
    assert_eq!(i.sections(0,1).unwrap_err().kind(),io::ErrorKind::Interrupted);
}
#[test]
fn dynamic_table_uses_same_bounded_contract(){
    let mut f=fixture(Class::Elf64,Order::Big);
    put(&mut f.b,f.h+3*f.sw+4,4,11,f.order);
    let mut i=open(&f.b,4096);
    assert_eq!(i.symbols(3,2,1).unwrap().entries[0].name,Name::Bytes(b"beta".to_vec()));
    assert!(i.symbols(4,0,1).is_err());
}
