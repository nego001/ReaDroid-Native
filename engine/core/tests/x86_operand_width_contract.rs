use negrodroid_core::x86_decode::{self,Mode,Op,Operand,Base,Memory,BinaryKind,UnaryKind,Immediate,Target,Stop};
fn one(m:Mode,b:&[u8])->Op{let p=x86_decode::decode(m,0x1000,b).unwrap();assert_eq!(p.stop,Stop::Complete);assert_eq!(p.instructions.len(),1);p.instructions[0].op}
fn mov(width:u8,destination:Operand,source:Operand)->Op{Op::Binary{kind:BinaryKind::Mov,width,destination,source}}
fn imm(kind:BinaryKind,width:u8,operand:Operand,bits:u8,raw:u64,value:u64)->Op{Op::BinaryImmediate{kind,width,operand,immediate:Immediate{encoded_bits:bits,raw,value}}}
#[test]
fn high_byte_vs_rex_low_byte(){
    for i in 0..4u8{
        assert_eq!(one(Mode::X86,&[0x88,0xc0|((i+4)<<3)]),mov(8,Operand::Register(0),Operand::HighByte(i)));
        assert_eq!(one(Mode::X64,&[0x40,0x88,0xc0|((i+4)<<3)]),mov(8,Operand::Register(0),Operand::Register(i+4)));
        assert_eq!(one(Mode::X64,&[0x44,0x88,0xc0|((i+4)<<3)]),mov(8,Operand::Register(0),Operand::Register(i+12)));
    }
}
#[test]
fn byte_rm_high_and_memory_base_distinct(){
    assert_eq!(one(Mode::X64,&[0x8a,0xc4]),mov(8,Operand::Register(0),Operand::HighByte(0)));
    let memory=Memory{base:Base::Register(4),index:None,scale:1,displacement:0,rip_target:None};
    assert_eq!(one(Mode::X64,&[0x88,0x24,0x24]),mov(8,Operand::Memory(memory),Operand::HighByte(0)));
}
#[test]
fn byte_immediate_all_registers_and_values(){
    for v in 0..=255u8{for i in 0..8u8{
        let reg=if i<4{Operand::Register(i)}else{Operand::HighByte(i-4)};
        assert_eq!(one(Mode::X64,&[0xb0|i,v]),imm(BinaryKind::Mov,8,reg,8,v as u64,v as u64));
        assert_eq!(one(Mode::X64,&[0x41,0xb0|i,v]),imm(BinaryKind::Mov,8,Operand::Register(i+8),8,v as u64,v as u64));
    }}
}
#[test]
fn operand_override_and_rex_w_precedence(){
    assert_eq!(one(Mode::X86,&[0x66,0x89,0xca]),mov(16,Operand::Register(2),Operand::Register(1)));
    assert_eq!(one(Mode::X64,&[0x66,0x45,0x89,0xca]),mov(16,Operand::Register(10),Operand::Register(9)));
    assert_eq!(one(Mode::X64,&[0x66,0x4d,0x89,0xca]),mov(64,Operand::Register(10),Operand::Register(9)));
}
#[test]
fn immediate_width_and_sign_extension(){
    assert_eq!(one(Mode::X86,&[0x66,0xb9,0x34,0x12]),Op::MoveImmediate{register:1,width:16,value:0x1234});
    assert_eq!(one(Mode::X64,&[0x66,0x83,0xc0,0x80]),imm(BinaryKind::Add,16,Operand::Register(0),8,128,0xff80));
    assert_eq!(one(Mode::X64,&[0x66,0x81,0xc0,0x34,0x12]),imm(BinaryKind::Add,16,Operand::Register(0),16,0x1234,0x1234));
    assert_eq!(one(Mode::X64,&[0x66,0x05,0xff,0xff]),imm(BinaryKind::Add,16,Operand::Register(0),16,65535,65535));
}
#[test]
fn byte_groups_preserve_unsigned_bit_pattern(){
    assert_eq!(one(Mode::X86,&[0x80,0xc4,0xff]),imm(BinaryKind::Add,8,Operand::HighByte(0),8,255,255));
    assert_eq!(one(Mode::X64,&[0x40,0xc6,0xc4,0x80]),imm(BinaryKind::Mov,8,Operand::Register(4),8,128,128));
    assert_eq!(one(Mode::X86,&[0xf6,0xc4,0x80]),imm(BinaryKind::Test,8,Operand::HighByte(0),8,128,128));
    assert_eq!(one(Mode::X86,&[0xf6,0xd4]),Op::Unary{kind:UnaryKind::Not,width:8,operand:Operand::HighByte(0)});
}
#[test]
fn width_override_preserves_address_size_and_full_rip(){
    let memory=Operand::Memory(Memory{base:Base::Rip,index:None,scale:1,displacement:-4,rip_target:Some(Target::Address(0x1005))});
    assert_eq!(one(Mode::X64,&[0x66,0xc7,0x05,0xfc,0xff,0xff,0xff,0x34,0x12]),imm(BinaryKind::Mov,16,memory,16,0x1234,0x1234));
}
#[test]
fn push_pop_width_and_indirect_exclusion(){
    assert_eq!(one(Mode::X64,&[0x66,0x41,0x50]),Op::PushPop{pop:false,register:8,width:16});
    assert_eq!(one(Mode::X86,&[0x66,0x58]),Op::PushPop{pop:true,register:0,width:16});
    for b in [&[0x66,0xff,0xd0][..],&[0x66,0xe8,0,0,0,0],&[0x67,0x89,0xc0],&[0x66,0x66,0x89,0xc0],&[0x48,0x66,0x89,0xc0]]{
        assert_eq!(x86_decode::decode(Mode::X64,0,b).unwrap().stop,Stop::Unsupported{offset:0});
    }
}
#[test]
fn truncation_does_not_emit_prefix_or_partial_word(){
    let b=[0x66,0x41,0xc7,0xc0,0x34,0x12];
    for n in 1..b.len(){let p=x86_decode::decode(Mode::X64,0,&b[..n]).unwrap();assert_eq!(p.stop,Stop::Truncated{offset:0});assert_eq!(p.consumed,0);}
}
#[test]
fn byte_and_word_stream_boundaries(){
    let b=[0xb4,0xff,0x40,0xb4,1,0x66,0xb8,0x34,0x12,0x90];
    let p=x86_decode::decode(Mode::X64,0x1000,&b).unwrap();
    assert_eq!(p.stop,Stop::Complete);assert_eq!(p.instructions.iter().map(|i|i.address).collect::<Vec<_>>(),[0x1000,0x1002,0x1005,0x1009]);
}
