use negrodroid_core::x86_decode::{self,Mode,Op,Operand,Base,Memory,BinaryKind,UnaryKind,Immediate,Target,Stop};
fn one(m:Mode,pc:u64,b:&[u8])->Op{let p=x86_decode::decode(m,pc,b).unwrap();assert_eq!(p.stop,Stop::Complete);assert_eq!(p.instructions.len(),1);p.instructions[0].op}
fn imm(kind:BinaryKind,width:u8,operand:Operand,encoded_bits:u8,raw:u64,value:u64)->Op{
    Op::BinaryImmediate{kind,width,operand,immediate:Immediate{encoded_bits,raw,value}}
}
#[test]
fn group1_all_selectors_and_sign_extension(){
    let kinds=[BinaryKind::Add,BinaryKind::Or,BinaryKind::Adc,BinaryKind::Sbb,BinaryKind::And,BinaryKind::Sub,BinaryKind::Xor,BinaryKind::Cmp];
    for (s,k) in kinds.into_iter().enumerate(){
        for raw in 0..=255u8{
            let m=0xc0|((s as u8)<<3)|3;
            assert_eq!(one(Mode::X64,0,&[0x48,0x83,m,raw]),imm(k,64,Operand::Register(3),8,u64::from(raw),raw as i8 as i64 as u64));
            assert_eq!(one(Mode::X86,0,&[0x83,m,raw]),imm(k,32,Operand::Register(3),8,u64::from(raw),u64::from(raw as i8 as i32 as u32)));
        }
        assert_eq!(one(Mode::X64,0,&[0x48,0x81,0xc0|((s as u8)<<3)|3,0,0,0,0x80]),imm(k,64,Operand::Register(3),32,0x80000000,0xffffffff80000000));
    }
}
#[test]
fn c7_and_test_immediate_widths(){
    assert_eq!(one(Mode::X86,0,&[0xc7,0xc1,0xff,0xff,0xff,0xff]),imm(BinaryKind::Mov,32,Operand::Register(1),32,0xffffffff,0xffffffff));
    assert_eq!(one(Mode::X64,0,&[0x49,0xc7,0xc1,0xff,0xff,0xff,0xff]),imm(BinaryKind::Mov,64,Operand::Register(9),32,0xffffffff,u64::MAX));
    assert_eq!(one(Mode::X64,0,&[0x48,0xf7,0xc2,0,0,0,0x80]),imm(BinaryKind::Test,64,Operand::Register(2),32,0x80000000,0xffffffff80000000));
}
#[test]
fn rip_relative_uses_complete_instruction_length(){
    let cases:[(&[u8],BinaryKind,u8,u64,u64,u64);3]=[
        (&[0x48,0x83,0x05,0xfc,0xff,0xff,0xff,0x80],BinaryKind::Add,8,128,0xffffffffffffff80,0x1004),
        (&[0x48,0xc7,0x05,0xfc,0xff,0xff,0xff,1,0,0,0],BinaryKind::Mov,32,1,1,0x1007),
        (&[0x48,0xf7,0x05,0xfc,0xff,0xff,0xff,1,0,0,0],BinaryKind::Test,32,1,1,0x1007)];
    for (b,k,bits,raw,val,t) in cases{
        let operand=Operand::Memory(Memory{base:Base::Rip,index:None,scale:1,displacement:-4,rip_target:Some(Target::Address(t))});
        assert_eq!(one(Mode::X64,0x1000,b),imm(k,64,operand,bits,raw,val));
    }
}
#[test]
fn accumulator_immediate_forms(){
    for (opcode,k) in [(5,BinaryKind::Add),(0x0d,BinaryKind::Or),(0x15,BinaryKind::Adc),(0x1d,BinaryKind::Sbb),(0x25,BinaryKind::And),(0x2d,BinaryKind::Sub),(0x35,BinaryKind::Xor),(0x3d,BinaryKind::Cmp),(0xa9,BinaryKind::Test)]{
        assert_eq!(one(Mode::X64,0,&[0x48,opcode,0xff,0xff,0xff,0xff]),imm(k,64,Operand::Register(0),32,0xffffffff,u64::MAX));
    }
}
#[test]
fn group3_unary_all_supported(){
    for (s,k) in [(2,UnaryKind::Not),(3,UnaryKind::Neg),(4,UnaryKind::Mul),(5,UnaryKind::Imul),(6,UnaryKind::Div),(7,UnaryKind::Idiv)]{
        assert_eq!(one(Mode::X64,0,&[0x49,0xf7,0xc0|(s<<3)|1]),Op::Unary{kind:k,width:64,operand:Operand::Register(9)});
    }
}
#[test]
fn group5_indirect_control_and_width(){
    for (s,k) in [(0,UnaryKind::Inc),(1,UnaryKind::Dec),(2,UnaryKind::Call),(4,UnaryKind::Jump),(6,UnaryKind::Push)]{
        for mode in [Mode::X86,Mode::X64]{
            let width=if mode==Mode::X64&&s>=2{64}else{32};
            assert_eq!(one(mode,0,&[0xff,0xc0|(s<<3)|2]),Op::Unary{kind:k,width,operand:Operand::Register(2)});
        }
    }
}
#[test]
fn indirect_rip_reference_not_resolved_destination(){
    assert_eq!(one(Mode::X64,0x1000,&[0xff,0x15,4,0,0,0]),Op::Unary{kind:UnaryKind::Call,width:64,operand:Operand::Memory(Memory{base:Base::Rip,index:None,scale:1,displacement:4,rip_target:Some(Target::Address(0x100a))})});
}
#[test]
fn unsupported_groups_stop_without_guessing(){
    for b in [&[0xc7,0xc8][..],&[0xf7,0xc8],&[0xff,0xd8],&[0xff,0xe8],&[0xff,0xf8],&[0x44,0x83,0xc0,1]]{
        let p=x86_decode::decode(Mode::X64,0,b).unwrap();assert_eq!(p.stop,Stop::Unsupported{offset:0});assert_eq!(p.consumed,0);
    }
}
#[test]
fn truncated_group_immediate_rejects_entire_instruction(){
    let b=[0x48,0xc7,0x84,0x93,1,2,3,4,5,6,7,8];
    for n in 1..b.len(){
        let p=x86_decode::decode(Mode::X64,0,&b[..n]).unwrap();
        assert_eq!(p.stop,Stop::Truncated{offset:0});assert!(p.instructions.is_empty());
    }
}
#[test]
fn mixed_groups_preserve_boundaries(){
    let b=[0x90,0x48,0x83,0xc0,0xff,0xf7,0xd8,0xff,0xd0,0xc3];
    let p=x86_decode::decode(Mode::X64,0x1000,&b).unwrap();
    assert_eq!(p.stop,Stop::Complete);assert_eq!(p.instructions.iter().map(|i|i.address).collect::<Vec<_>>(),[0x1000,0x1001,0x1005,0x1007,0x1009]);
}
