use negrodroid_core::{Cancellation,ReadSession,dex_identifiers::{Inspector,Kind,Record,StringValue,MAX_PAGE}};
use std::io::{self,Cursor};
fn w16(b:&mut[u8],i:usize,v:u16){b[i..i+2].copy_from_slice(&v.to_le_bytes());}
fn w32(b:&mut[u8],i:usize,v:u32){b[i..i+4].copy_from_slice(&v.to_le_bytes());}
fn fixture()->Vec<u8>{
    let mut b=vec![0;512];b[..8].copy_from_slice(b"dex\n039\0");
    for (i,v) in [(32,512),(36,112),(40,0x12345678),(52,256),(56,4),(60,112),(64,2),(68,128),
        (72,1),(76,136),(80,1),(84,148),(88,1),(92,156),(96,1),(100,164),(104,256),(108,256)]{w32(&mut b,i,v);}
    w32(&mut b,256,10);
    for (i,(kind,n,at)) in [(0,1,0),(1,4,112),(2,2,128),(3,1,136),(4,1,148),(5,1,156),
        (6,1,164),(0x1000,1,256),(0x2002,4,384),(0x1001,1,448)].into_iter().enumerate(){
        let p=260+12*i;w16(&mut b,p,kind);w32(&mut b,p+4,n);w32(&mut b,p+8,at);
    }
    for (i,(at,data)) in [(384,b"\x03Lx;\0".as_slice()),(392,b"\x01I\0"),(400,b"\x03foo\0"),(410,b"\x01V\0")].into_iter().enumerate(){
        w32(&mut b,112+4*i,at as u32);b[at..at+data.len()].copy_from_slice(data);
    }
    w32(&mut b,128,0);w32(&mut b,132,1);
    w32(&mut b,136,3);w32(&mut b,140,1);w32(&mut b,144,448);
    w16(&mut b,148,0);w16(&mut b,150,1);w32(&mut b,152,2);
    w16(&mut b,156,0);w16(&mut b,158,0);w32(&mut b,160,2);
    w32(&mut b,164,0);w32(&mut b,168,1);w32(&mut b,172,u32::MAX);
    w32(&mut b,176,448);w32(&mut b,180,u32::MAX);
    w32(&mut b,448,1);w16(&mut b,452,1);b
}
fn open(b:&[u8],budget:u64)->Inspector<Cursor<&[u8]>>{
    Inspector::open(ReadSession::new(Cursor::new(b),b.len() as u64,budget,Cancellation::default())).unwrap()
}
fn units(s:&str)->StringValue{StringValue::Units(s.encode_utf16().collect())}
#[test]
fn all_identifier_kinds_and_explicit_resolution(){
    let b=fixture();let mut i=open(&b,4096);
    assert_eq!(i.string(2).unwrap(),units("foo"));assert_eq!(i.descriptor(0).unwrap(),units("Lx;"));
    assert_eq!(i.page(Kind::Prototype,0,1).unwrap().records,[Record::Prototype{shorty:3,return_type:1,parameters_offset:448}]);
    assert_eq!(i.page(Kind::Field,0,1).unwrap().records,[Record::Field{class:0,field_type:1,name:2}]);
    assert_eq!(i.page(Kind::Method,0,1).unwrap().records,[Record::Method{class:0,prototype:0,name:2}]);
    assert_eq!(i.page(Kind::Class,0,1).unwrap().records,[Record::Class{class:0,flags:1,superclass:None,interfaces_offset:448,
        source_file:None,annotations_offset:0,class_data_offset:0,static_values_offset:0}]);
    assert_eq!(i.type_list(448).unwrap(),[1]);assert!(i.type_list(0).unwrap().is_empty());
}
#[test]
fn modified_utf8_nul_and_surrogates_preserved(){
    let mut b=fixture();let data=[3,0xc0,0x80,0xed,0xa0,0xbd,0xed,0xb8,0x80,0];
    b[410..420].copy_from_slice(&data);let mut i=open(&b,4096);
    assert_eq!(i.string(3).unwrap(),StringValue::Units(vec![0,0xd83d,0xde00]));
    b[410..415].copy_from_slice(&[1,0xed,0xa0,0x80,0]);let mut i=open(&b,4096);
    assert_eq!(i.string(3).unwrap(),StringValue::Units(vec![0xd800]));
}
#[test]
fn malformed_modified_utf8_and_declared_length(){
    for data in [vec![1,0xc1,0x81,0],vec![2,b'A',0],vec![1,0xf0,0x9f,0x98,0x80,0],vec![1,0xe0,0x80,0x80,0],vec![1,0xc2,0,0]]{
        let mut b=fixture();b[410..410+data.len()].copy_from_slice(&data);let mut i=open(&b,4096);
        assert_eq!(i.string(3).unwrap_err().kind(),io::ErrorKind::InvalidData);
    }
}
#[test]
fn uleb_overflow_and_long_declaration(){
    let mut b=fixture();b[410..415].copy_from_slice(&[0xff,0xff,0xff,0xff,0x10]);
    let mut i=open(&b,4096);assert!(i.string(3).is_err());
    b[410..412].copy_from_slice(&[0x81,0x02]);let mut i=open(&b,4096);
    assert_eq!(i.string(3).unwrap(),StringValue::TooLong{declared_units:257});
}
#[test]
fn page_bounds_and_continuation(){
    let b=fixture();let mut i=open(&b,4096);
    let p=i.page(Kind::String,0,2).unwrap();assert_eq!(p.next,Some(2));assert_eq!(p.total,4);
    assert_eq!(i.page(Kind::String,2,2).unwrap().next,None);
    assert!(i.page(Kind::String,4,1).unwrap().records.is_empty());
    assert!(i.page(Kind::Type,3,1).is_err());assert!(i.page(Kind::Type,0,MAX_PAGE+1).is_err());
    assert!(i.string(4).is_err());assert!(i.descriptor(2).is_err());
}
#[test]
fn invalid_fixed_indices_rejected(){
    for (at,value,kind) in [(128,4,Kind::Type),(136,4,Kind::Prototype),(152,4,Kind::Field),(160,4,Kind::Method),(172,2,Kind::Class)]{
        let mut b=fixture();w32(&mut b,at,value);let mut i=open(&b,4096);
        assert!(i.page(kind,0,1).is_err());
    }
}
#[test]
fn variable_regions_and_alignment(){
    let mut b=fixture();w32(&mut b,112,448);let mut i=open(&b,4096);assert!(i.string(0).is_err());
    w32(&mut b,112,384);w32(&mut b,144,449);let mut i=open(&b,4096);
    assert!(i.page(Kind::Prototype,0,1).is_err());assert!(i.type_list(449).is_err());
    w32(&mut b,184,448);let mut i=open(&b,4096);assert!(i.page(Kind::Class,0,1).is_err());
}
#[test]
fn list_limit_and_index_checks(){
    let mut b=fixture();w32(&mut b,448,129);let mut i=open(&b,4096);
    assert_eq!(i.type_list(448).unwrap_err().kind(),io::ErrorKind::Unsupported);
    w32(&mut b,448,1);w16(&mut b,452,2);let mut i=open(&b,4096);assert!(i.type_list(448).is_err());
    assert!(i.type_list(508).is_ok()); // zero count within declared region; no item-boundary proof
}
#[test]
fn region_boundary_stops_string_before_next_kind(){
    let mut b=fixture();w32(&mut b,124,446);b[446]=1;b[447]=b'A';
    let mut i=open(&b,4096);assert!(i.string(3).is_err());
}
#[test]
fn budget_and_cancellation(){
    let b=fixture();let c=Cancellation::default();
    let mut i=Inspector::open(ReadSession::new(Cursor::new(&b),512,240,c.clone())).unwrap();
    assert_eq!(i.remaining_budget(),4);
    assert_eq!(i.string(0).unwrap_err().kind(),io::ErrorKind::Other);
    assert_eq!(i.remaining_budget(),0);
    c.cancel();assert_eq!(i.page(Kind::Type,0,1).unwrap_err().kind(),io::ErrorKind::Interrupted);
}
