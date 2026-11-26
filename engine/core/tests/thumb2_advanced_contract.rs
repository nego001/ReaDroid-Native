use negrodroid_core::thumb_decode::{self,Op,Target,MemKind};
fn one(pc:u32,a:u16,b:u16)->Op{let bytes=[a.to_le_bytes(),b.to_le_bytes()].concat();thumb_decode::decode(pc,&bytes).unwrap()[0].op}
fn mov(top:bool,rd:u16,v:u16)->(u16,u16){
    ((if top{0xf2c0}else{0xf240})|((v>>12)&15)|(((v>>11)&1)<<10),
     (((v>>8)&7)<<12)|(rd<<8)|(v&255))
}
#[test]
fn wide_move_known_words(){
    assert_eq!(one(0,0xf241,0x2034),Op::WideMove{top:false,destination:0,value:0x1234});
    assert_eq!(one(0,0xf6ca,0x30cd),Op::WideMove{top:true,destination:0,value:0xabcd});
}
#[test]
fn exhaustive_wide_move_immediates(){
    for top in [false,true]{for value in 0..=u16::MAX{
        let (a,b)=mov(top,7,value);
        assert_eq!(one(0,a,b),Op::WideMove{top,destination:7,value});
    }}
}
#[test]
fn wide_move_invalid_destinations(){
    for rd in [13,15]{let (a,b)=mov(false,rd,123);assert_eq!(one(0,a,b),Op::Unknown);}
}
#[test]
fn addw_subw_all_immediates(){
    for subtract in [false,true]{for value in 0..4096u16{
        let a=(if subtract{0xf2a0}else{0xf200})|3|(((value>>11)&1)<<10);
        let b=(((value>>8)&7)<<12)|(2<<8)|(value&255);
        assert_eq!(one(0,a,b),Op::WideAddSub{subtract,destination:2,source:3,value});
    }}
}
#[test]
fn addw_subw_excluded_special_operands(){
    for (a,b) in [(0xf20f,0x0201),(0xf20d,0x0201),(0xf203,0x0d01),(0xf2a3,0x0f01)]{assert_eq!(one(0,a,b),Op::Unknown);}
}
#[test]
fn conditional_wide_branches_signed_offsets(){
    assert_eq!(one(0x1000,0xf000,0x8002),Op::Branch{link:false,condition:Some(0),target:Target::Address(0x1008)});
    assert_eq!(one(0x1000,0xf47f,0xaffc),Op::Branch{link:false,condition:Some(1),target:Target::Address(0xffc)});
    assert_eq!(one(0,0xf47f,0xaffc),Op::Branch{link:false,condition:Some(1),target:Target::Overflow});
    assert_eq!(one(0,0xf380,0x8000),Op::Unknown);
}
#[test]
fn conditional_wide_j_bits_and_conditions(){
    for c in 0..14u16{
        for (b,delta) in [(0x8000,0),(0xa000,1<<18),(0x8800,1<<19),(0xa800,(1<<18)+(1<<19))]{
            assert_eq!(one(0x1000,0xf000|(c<<6),b),Op::Branch{link:false,condition:Some(c as u8),target:Target::Address(0x1004+delta)});
        }
    }
}
#[test]
fn wide_memory_all_types_and_displacements(){
    for (a,load,kind) in [(0xf8c0,false,MemKind::Word),(0xf8d0,true,MemKind::Word),(0xf880,false,MemKind::Byte),
        (0xf890,true,MemKind::Byte),(0xf8a0,false,MemKind::Half),(0xf8b0,true,MemKind::Half),
        (0xf990,true,MemKind::SignedByte),(0xf9b0,true,MemKind::SignedHalf)]{
        for displacement in [0,1,255,4095]{
            assert_eq!(one(0,a|3,0x2000|displacement),Op::MemoryImmediate{load,kind,base:3,register:2,displacement});
        }
    }
}
#[test]
fn wide_memory_excludes_special_encodings(){
    for (a,b) in [(0xf8df,0x2000),(0xf8d3,0xf000),(0xf893,0xd000),(0xf853,0x2b04),(0xf993,0xf000)]{assert_eq!(one(0,a,b),Op::Unknown);}
}
#[test]
fn mixed_width_raw_words_and_addresses(){
    let halves=[0xbf00u16,0xf241,0x2034,0xf8d3,0x2004,0xf000,0x8000,0x4770];
    let bytes:Vec<_>=halves.iter().flat_map(|w|w.to_le_bytes()).collect();
    let p=thumb_decode::decode(0x1000,&bytes).unwrap();
    assert_eq!(p.iter().map(|i|i.address).collect::<Vec<_>>(),[0x1000,0x1002,0x1006,0x100a,0x100e]);
    assert_eq!(p[1].second,Some(0x2034));assert_eq!(p[3].op,Op::Branch{link:false,condition:Some(0),target:Target::Address(0x100e)});
}
