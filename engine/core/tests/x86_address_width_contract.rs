use negrodroid_core::x86_decode::{self,Mode,Op,Operand,Memory,Base,Target,Stop,BinaryKind,Immediate};
fn one(mode:Mode,pc:u64,b:&[u8],width:u8)->Op{
    let p=x86_decode::decode(mode,pc,b).unwrap();assert_eq!(p.stop,Stop::Complete);assert_eq!(p.consumed,b.len());assert_eq!(p.instructions.len(),1);assert_eq!(p.instructions[0].bytes,b);assert_eq!(p.instructions[0].address_width,width);p.instructions[0].op
}
fn mem(base:Base,index:Option<u8>,scale:u8,displacement:i64,rip_target:Option<Target>)->Operand{Operand::Memory(Memory{base,index,scale,displacement,rip_target})}
fn mov(width:u8,src:Operand)->Op{Op::Binary{kind:BinaryKind::Mov,width,destination:Operand::Register(0),source:src}}
#[test] fn all_16bit_modrm_memory_forms(){
    let table=[(3,Some(6)),(3,Some(7)),(5,Some(6)),(5,Some(7)),(6,None),(7,None),(5,None),(3,None)];
    for form in 0..3u8{for r in 0..8u8{for reg in 0..8u8{
        let mut b=vec![0x67,0x8b,(form<<6)|(reg<<3)|r];
        let (base,index,disp)=if form==0&&r==6{b.extend([0x34,0xf2]);(Base::None,None,0xf234)}
        else{let (base,index)=table[r as usize];let disp=match form{0=>0,1=>{b.push(0x80);-128},_=>{b.extend([0x00,0x80]);-32768}};(Base::Register(base),index,disp)};
        assert_eq!(one(Mode::X86,0,&b,16),Op::Binary{kind:BinaryKind::Mov,width:32,destination:Operand::Register(reg),source:mem(base,index,1,disp,None)});
    }}}
}
#[test] fn no_sib_in_16bit_addressing(){
    assert_eq!(one(Mode::X86,0,&[0x67,0x8b,0x04],16),mov(32,mem(Base::Register(6),None,1,0,None)));
}
#[test] fn prefix_order_and_operand_independence(){
    for b in [[0x66,0x67,0x8b,0x00],[0x67,0x66,0x8b,0x00]]{assert_eq!(one(Mode::X86,0,&b,16),mov(16,mem(Base::Register(3),Some(6),1,0,None)));}
    assert_eq!(one(Mode::X64,0,&[0x67,0x66,0x48,0x8b,0x00],32),mov(64,mem(Base::Register(0),None,1,0,None)));
}
#[test] fn eip_relative_zero_extended_wrap(){
    assert_eq!(one(Mode::X64,0x1_ffff_fffcu64,&[0x67,0x8b,0x05,0xfc,0xff,0xff,0xff],32),mov(32,mem(Base::Eip,None,1,-4,Some(Target::Address(0xffff_ffff)))));
    assert_eq!(one(Mode::X64,0x1_0000_0000,&[0x67,0x8b,0x05,0,0,0,0],32),mov(32,mem(Base::Eip,None,1,0,Some(Target::Address(7)))));
}
#[test] fn eip_final_length_with_immediate(){
    assert_eq!(one(Mode::X64,0x1_0000_1000,&[0x67,0x83,0x05,0,0,0,0,0xff],32),Op::BinaryImmediate{kind:BinaryKind::Add,width:32,operand:mem(Base::Eip,None,1,0,Some(Target::Address(0x1008))),immediate:Immediate{encoded_bits:8,raw:255,value:0xffff_ffff}});
}
#[test] fn sib_absolute_32_bit_is_not_eip_relative(){
    assert_eq!(one(Mode::X64,0,&[0x67,0x8b,0x04,0x25,0,0,0,0x80],32),mov(32,mem(Base::None,None,1,0x8000_0000,None)));
}
#[test] fn sib_rex_extended_base_index(){
    assert_eq!(one(Mode::X64,0,&[0x67,0x43,0x8b,0x44,0xa5,0x80],32),mov(32,mem(Base::Register(13),Some(12),4,-128,None)));
}
#[test] fn default_widths_preserved(){
    assert_eq!(one(Mode::X64,0,&[0x8b,0x00],64),mov(32,mem(Base::Register(0),None,1,0,None)));
    assert_eq!(one(Mode::X86,0,&[0x8b,0x00],32),mov(32,mem(Base::Register(0),None,1,0,None)));
}
#[test] fn all_truncation_boundaries(){
    for (mode,b) in [(Mode::X86,&[0x67,0x66,0xc7,0x86,0x12,0x34,0x56,0x78][..]),(Mode::X64,&[0x67,0x48,0x69,0x05,0,0,0,0,1,2,3,4][..])]{for n in 1..b.len(){let p=x86_decode::decode(mode,0,&b[..n]).unwrap();assert_eq!(p.stop,Stop::Truncated{offset:0});assert!(p.instructions.is_empty());}}
}
#[test] fn excluded_prefixes_and_register_forms_stop_exactly(){
    for tail in [&[0x67,0x67,0x8b,0x00][..],&[0x67,0x66,0x66,0x8b,0x00],&[0x48,0x67,0x8b,0x00],&[0x67,0x8b,0xc0],&[0x67,0xe8,0,0,0,0],&[0x67,0x0f,0x84,0,0,0,0],&[0x67,0xf3,0x8b,0x00]]{let mut b=vec![0x90];b.extend(tail);let p=x86_decode::decode(Mode::X64,0,&b).unwrap();assert_eq!(p.stop,Stop::Unsupported{offset:1});assert_eq!(p.consumed,1);}
}
