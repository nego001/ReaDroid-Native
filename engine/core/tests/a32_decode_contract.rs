use negrodroid_core::{Cancellation,ReadSession,a32_decode::{self,DataKind,Op,Target,Error,MAX_INSTRUCTIONS}};
use std::io::{self,Cursor};
fn one(pc:u32,w:u32)->Op{a32_decode::decode(pc,&w.to_le_bytes()).unwrap()[0].op}
#[test]
fn conditions_and_unconditional_space(){
    for c in 0..15u32{
        let w=(c<<28)|0x0a000000;
        let i=a32_decode::decode(0x1000,&w.to_le_bytes()).unwrap()[0];
        assert_eq!(i.condition,c as u8);assert_eq!(i.word,w);
        assert_eq!(i.op,Op::Branch{link:false,target:Target::Address(0x1008)});
    }
    assert_eq!(one(0,0xfa000000),Op::Unknown);
}
#[test]
fn branch_pc_bias_signed_displacements(){
    assert_eq!(one(0x1000,0xea000000),Op::Branch{link:false,target:Target::Address(0x1008)});
    assert_eq!(one(0x1000,0xebfffffc),Op::Branch{link:true,target:Target::Address(0xff8)});
    assert_eq!(one(0x4000000,0xea800000),Op::Branch{link:false,target:Target::Address(0x2000008)});
    assert_eq!(one(0x4000000,0xea7fffff),Op::Branch{link:false,target:Target::Address(0x6000004)});
}
#[test]
fn branch_coordinate_overflow(){
    assert_eq!(one(0,0xeafffffc),Op::Branch{link:false,target:Target::Overflow});
    assert_eq!(one(u32::MAX-7,0xea000000),Op::Branch{link:false,target:Target::Overflow});
}
#[test]
fn nop_exchange_and_unknown(){
    assert_eq!(one(0,0xe320f000),Op::Nop);
    assert_eq!(one(0,0xe12fff1e),Op::Exchange{link:false,register:14});
    assert_eq!(one(0,0x112fff33),Op::Exchange{link:true,register:3});
    assert_eq!(one(0,0xe12fff20),Op::Unknown);
    assert_eq!(one(0,0xffffffff),Op::Unknown);
}
#[test]
fn immediate_rotate_and_operand_roles(){
    assert_eq!(one(0,0xe3a004ff),Op::DataImmediate{kind:DataKind::Mov,set_flags:false,destination:Some(0),source:None,imm8:255,rotate:8,value:0xff000000});
    assert_eq!(one(0,0xe2812001),Op::DataImmediate{kind:DataKind::Add,set_flags:false,destination:Some(2),source:Some(1),imm8:1,rotate:0,value:1});
    assert_eq!(one(0,0xe3520007),Op::DataImmediate{kind:DataKind::Cmp,set_flags:true,destination:None,source:Some(2),imm8:7,rotate:0,value:7});
}
#[test]
fn exhaustive_immediate_rotation(){
    for rot in 0..16u32{for imm in 0..256u32{
        let w=0xe3a00000|(rot<<8)|imm;
        let mut expected=0u32;
        for i in 0..8u32{if imm&(1<<i)!=0{expected|=1<<((i+32-rot*2)%32);}}
        assert!(matches!(one(0,w),Op::DataImmediate{value,..} if value==expected));
    }}
}
#[test]
fn excludes_special_immediate_forms_and_pc_operands(){
    for w in [0xe3000000,0xe3400000,0xe3a1f000,0xe28f0000,0xe3501000,0xe320f001]{
        assert_eq!(one(0,w),Op::Unknown,"{w:08x}");
    }
}
#[test]
fn immediate_memory_forms_and_exclusions(){
    assert_eq!(one(0,0xe59d2010),Op::MemoryImmediate{load:true,byte:false,base:13,register:2,displacement:16});
    assert_eq!(one(0,0xe5434007),Op::MemoryImmediate{load:false,byte:true,base:3,register:4,displacement:-7});
    for w in [0xe49d2010,0xe5bd2010,0xe79d2001,0xe59f0000,0xe59df000]{assert_eq!(one(0,w),Op::Unknown);}
}
#[test]
fn bounds_and_alignment(){
    assert_eq!(a32_decode::decode(0,&[]),Err(Error::Length));
    assert_eq!(a32_decode::decode(0,&[0;3]),Err(Error::Length));
    assert_eq!(a32_decode::decode(2,&[0;4]),Err(Error::Alignment));
    assert_eq!(a32_decode::decode(u32::MAX-3,&[0;4]),Err(Error::AddressOverflow));
    assert_eq!(a32_decode::decode(0,&vec![0;MAX_INSTRUCTIONS*4+4]),Err(Error::Length));
}
#[test]
fn exact_read_budget_and_cancel(){
    let mut b=vec![0x77];b.extend(0xe320f000u32.to_le_bytes());b.extend(0xe12fff1eu32.to_le_bytes());
    let c=Cancellation::default();let mut s=ReadSession::new(Cursor::new(b),9,8,c.clone());
    let p=a32_decode::read(&mut s,1,0x1000,2).unwrap();
    assert_eq!(p[0].address,0x1000);assert_eq!(p[1].address,0x1004);assert_eq!(s.remaining_budget(),0);
    c.cancel();assert_eq!(a32_decode::read(&mut s,1,0x1000,1).unwrap_err().kind(),io::ErrorKind::Interrupted);
}
