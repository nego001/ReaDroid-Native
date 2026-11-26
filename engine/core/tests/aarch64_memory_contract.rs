use negrodroid_core::{Cancellation,ReadSession,aarch64_decode::{self,Op,Target}};
use std::io::Cursor;
fn one(pc:u64,w:u32)->Op{aarch64_decode::decode(pc,&w.to_le_bytes()).unwrap()[0].op}
fn adr(page:bool,imm:u32,rd:u32)->u32{
    (if page{0x90000000}else{0x10000000})|((imm&3)<<29)|(((imm>>2)&0x7ffff)<<5)|rd
}
#[test]
fn adr_positive_negative_and_unaligned_target(){
    assert_eq!(one(0x1000,adr(false,3,5)),Op::PcAddress{page:false,register:5,target:Target::Address(0x1003)});
    assert_eq!(one(0x1000,adr(false,0x1fffff,0)),Op::PcAddress{page:false,register:0,target:Target::Address(0xfff)});
}
#[test]
fn adrp_uses_page_base_and_signed_displacement(){
    assert_eq!(one(0x1abc,adr(true,2,7)),Op::PcAddress{page:true,register:7,target:Target::Address(0x3000)});
    assert_eq!(one(0x1abc,adr(true,0x1fffff,7)),Op::PcAddress{page:true,register:7,target:Target::Address(0)});
}
#[test]
fn pc_address_extremes_and_overflow(){
    assert_eq!(one(0,adr(false,0x100000,1)),Op::PcAddress{page:false,register:1,target:Target::Overflow});
    assert_eq!(one(0,adr(true,0x1fffff,1)),Op::PcAddress{page:true,register:1,target:Target::Overflow});
    assert_eq!(one(u64::MAX-7,adr(true,1,1)),Op::PcAddress{page:true,register:1,target:Target::Overflow});
}
#[test]
fn literal_load_integer_width_sign_and_target(){
    assert_eq!(one(0x1000,0x18000043),Op::LiteralLoad{width:4,signed:false,register:3,target:Target::Address(0x1008)});
    assert_eq!(one(0x1000,0x58ffffe4),Op::LiteralLoad{width:8,signed:false,register:4,target:Target::Address(0xffc)});
    assert_eq!(one(0,0x98000025),Op::LiteralLoad{width:4,signed:true,register:5,target:Target::Address(4)});
    assert_eq!(one(0,0xd8000000),Op::Unknown);
    assert_eq!(one(0,0x1c000000),Op::Unknown);
}
#[test]
fn unsigned_scaled_integer_memory_all_widths(){
    for size in 0..4u32{for load in [false,true]{
        let w=0x39000000|(size<<30)|((load as u32)<<22)|(4095<<10)|(31<<5)|9;
        let width=1u8<<size;
        assert_eq!(one(0,w),Op::MemoryImmediate{load,width,scaled:true,base:31,register:9,displacement:4095*i32::from(width)});
    }}
}
#[test]
fn signed_unscaled_integer_memory_all_widths(){
    for size in 0..4u32{for load in [false,true]{for field in [0,255,256,511]{
        let w=0x38000000|(size<<30)|((load as u32)<<22)|(field<<12)|(3<<5)|31;
        let displacement=if field>=256{field as i32-512}else{field as i32};
        assert_eq!(one(0,w),Op::MemoryImmediate{load,width:1u8<<size,scaled:false,base:3,register:31,displacement});
    }}}
}
#[test]
fn excluded_memory_encodings_remain_unknown(){
    for w in [0xf8400400,0xf8400c00,0xf8606800,0xf8400800,0x39800000,0x3d400000,0x38400400,0x69400000,0xa9800000,0xa8800000,0xa8000000]{
        assert_eq!(one(0,w),Op::Unknown,"word {w:08x}");
    }
}
#[test]
fn pair_signed_offset_and_register_fields(){
    for (size,width) in [(0u32,4u8),(2,8)]{for load in [false,true]{for field in [0,63,64,127]{
        let w=0x29000000|(size<<30)|((load as u32)<<22)|(field<<15)|(7<<10)|(31<<5)|5;
        let delta=if field>=64{field as i32-128}else{field as i32};
        assert_eq!(one(0,w),Op::MemoryPair{load,width,base:31,first:5,second:7,displacement:delta*i32::from(width)});
    }}}
}
#[test]
fn static_literal_never_reads_pointed_to_bytes(){
    let word=0x58000040u32.to_le_bytes();
    let mut s=ReadSession::new(Cursor::new(word),4,4,Cancellation::default());
    let p=aarch64_decode::read(&mut s,0,0x1000,1).unwrap();
    assert_eq!(p[0].op,Op::LiteralLoad{width:8,signed:false,register:0,target:Target::Address(0x1008)});
    assert_eq!(s.remaining_budget(),0);
}
#[test]
fn mixed_existing_and_new_words_preserve_exact_addresses(){
    let words=[0xd503201fu32,0x10000000,0xf9400421,0xa9401fe5,0xd65f03c0];
    let bytes:Vec<u8>=words.iter().flat_map(|w|w.to_le_bytes()).collect();
    let p=aarch64_decode::decode(0x1000,&bytes).unwrap();
    assert_eq!(p.iter().map(|i|i.word).collect::<Vec<_>>(),words);
    assert_eq!(p[1].op,Op::PcAddress{page:false,register:0,target:Target::Address(0x1004)});
    assert_eq!(p[2].op,Op::MemoryImmediate{load:true,width:8,scaled:true,base:1,register:1,displacement:8});
    assert_eq!(p[3].address,0x100c);
    assert_eq!(p[4].op,Op::Return{register:30});
}
