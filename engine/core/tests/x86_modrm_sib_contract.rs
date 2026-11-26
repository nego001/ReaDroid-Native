use negrodroid_core::x86_decode::{self,Mode,Op,Operand,Base,Memory,BinaryKind,Target,Stop};
fn one(mode:Mode,pc:u64,b:&[u8])->Op{let p=x86_decode::decode(mode,pc,b).unwrap();assert_eq!(p.stop,Stop::Complete);assert_eq!(p.instructions.len(),1);p.instructions[0].op}
fn mem(base:Base,index:Option<u8>,scale:u8,displacement:i64)->Operand{
    Operand::Memory(Memory{base,index,scale,displacement,rip_target:None})
}
fn mov(width:u8,destination:Operand,source:Operand)->Op{Op::Binary{kind:BinaryKind::Mov,width,destination,source}}
#[test]
fn register_direction_and_rex_extension(){
    assert_eq!(one(Mode::X86,0,&[0x89,0xca]),mov(32,Operand::Register(2),Operand::Register(1)));
    assert_eq!(one(Mode::X64,0,&[0x4d,0x8b,0xca]),mov(64,Operand::Register(9),Operand::Register(10)));
    assert_eq!(one(Mode::X64,0,&[0x45,0x89,0xca]),mov(32,Operand::Register(10),Operand::Register(9)));
}
#[test]
fn all_register_modrm_pairs(){
    for rex in [0x40u8,0x41,0x44,0x45,0x48,0x49,0x4c,0x4d]{
        for reg in 0..8u8{for rm in 0..8u8{
            let b=[rex,0x8b,0xc0|(reg<<3)|rm];
            assert_eq!(one(Mode::X64,0,&b),mov(if rex&8!=0{64}else{32},Operand::Register(reg|(((rex>>2)&1)<<3)),Operand::Register(rm|((rex&1)<<3))));
        }}
    }
}
#[test]
fn binary_operations_both_directions(){
    for (opcode,kind) in [(0x01,BinaryKind::Add),(0x09,BinaryKind::Or),(0x21,BinaryKind::And),(0x29,BinaryKind::Sub),(0x31,BinaryKind::Xor),(0x39,BinaryKind::Cmp)]{
        for direction in [0,2]{
            let (destination,source)=if direction==0{(Operand::Register(2),Operand::Register(1))}else{(Operand::Register(1),Operand::Register(2))};
            assert_eq!(one(Mode::X86,0,&[opcode|direction,0xca]),Op::Binary{kind,width:32,destination,source});
        }
    }
    assert_eq!(one(Mode::X86,0,&[0x85,0xca]),Op::Binary{kind:BinaryKind::Test,width:32,destination:Operand::Register(2),source:Operand::Register(1)});
}
#[test]
fn signed_displacement_and_base(){
    assert_eq!(one(Mode::X64,0,&[0x48,0x8b,0x43,0xf8]),mov(64,Operand::Register(0),mem(Base::Register(3),None,1,-8)));
    assert_eq!(one(Mode::X86,0,&[0x8b,0x83,0,0,0,0x80]),mov(32,Operand::Register(0),mem(Base::Register(3),None,1,i64::from(i32::MIN))));
    assert_eq!(one(Mode::X64,0,&[0x49,0x8b,0x45,0]),mov(64,Operand::Register(0),mem(Base::Register(13),None,1,0)));
}
#[test]
fn rip_relative_and_absolute_mode_difference(){
    let b=[0x8b,0x05,0xfc,0xff,0xff,0xff];
    assert_eq!(one(Mode::X86,0x1000,&b),mov(32,Operand::Register(0),mem(Base::None,None,1,0xffff_fffc)));
    assert_eq!(one(Mode::X64,0x1000,&b),mov(32,Operand::Register(0),Operand::Memory(Memory{base:Base::Rip,index:None,scale:1,displacement:-4,rip_target:Some(Target::Address(0x1002))})));
    assert_eq!(one(Mode::X64,0,&[0x49,0x8b,0x05,0xf0,0xff,0xff,0xff]),mov(64,Operand::Register(0),Operand::Memory(Memory{base:Base::Rip,index:None,scale:1,displacement:-16,rip_target:Some(Target::Overflow)})));
}
#[test]
fn sib_scale_index_base_extensions(){
    for bits in 0..4u8{
        let b=[0x4b,0x8b,0x44,(bits<<6)|(4<<3)|3,0xf0];
        assert_eq!(one(Mode::X64,0,&b),mov(64,Operand::Register(0),mem(Base::Register(11),Some(12),1<<bits,-16)));
    }
    assert_eq!(one(Mode::X64,0,&[0x48,0x8b,0x04,0xe4]),mov(64,Operand::Register(0),mem(Base::Register(4),None,1,0)));
}
#[test]
fn sib_no_base_not_rip_and_disp32(){
    let b=[0x8b,0x04,0x8d,0xfc,0xff,0xff,0xff];
    assert_eq!(one(Mode::X86,0,&b),mov(32,Operand::Register(0),mem(Base::None,Some(1),4,0xffff_fffc)));
    assert_eq!(one(Mode::X64,0,&b),mov(32,Operand::Register(0),mem(Base::None,Some(1),4,-4)));
    assert_eq!(one(Mode::X64,0,&[0x49,0x8b,0x04,0x25,1,0,0,0]),mov(64,Operand::Register(0),mem(Base::None,None,1,1)));
}
#[test]
fn lea_requires_memory_and_retains_address(){
    let memory=Memory{base:Base::Register(3),index:Some(2),scale:4,displacement:8,rip_target:None};
    assert_eq!(one(Mode::X64,0,&[0x48,0x8d,0x44,0x93,8]),Op::Lea{width:64,destination:0,memory});
    assert_eq!(x86_decode::decode(Mode::X64,0,&[0x8d,0xc0,0x90]).unwrap().stop,Stop::Unsupported{offset:0});
}
#[test]
fn truncated_modrm_sib_disp_never_emits_partial(){
    let b=[0x48,0x8b,0x84,0x93,1,2,3,4];
    for n in 1..b.len(){
        let p=x86_decode::decode(Mode::X64,0,&b[..n]).unwrap();
        assert_eq!(p.stop,Stop::Truncated{offset:0});assert_eq!(p.consumed,0);
    }
}
#[test]
fn mixed_stream_stops_at_unsupported_prefix(){
    let b=[0x90,0x48,0x8b,0x43,0xf8,0x31,0xc0,0x66,0x89,0xc0,0xc3];
    let p=x86_decode::decode(Mode::X64,0x1000,&b).unwrap();
    assert_eq!(p.stop,Stop::Unsupported{offset:7});assert_eq!(p.consumed,7);
    assert_eq!(p.instructions.iter().map(|x|x.address).collect::<Vec<_>>(),[0x1000,0x1001,0x1005]);
    assert_eq!(p.instructions[1].bytes,&b[1..5]);
}
