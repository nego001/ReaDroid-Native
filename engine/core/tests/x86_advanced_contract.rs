use negrodroid_core::x86_decode::{self,Mode,Op,Operand,Memory,Base,Target,Stop,Immediate};
fn one(mode:Mode,pc:u64,b:&[u8])->Op{
    let p=x86_decode::decode(mode,pc,b).unwrap();
    assert_eq!(p.stop,Stop::Complete);assert_eq!(p.consumed,b.len());
    assert_eq!(p.instructions.len(),1);assert_eq!(p.instructions[0].bytes,b);
    p.instructions[0].op
}
#[test] fn byte_extension_high_and_rex(){
    assert_eq!(one(Mode::X64,0,&[0x0f,0xb6,0xc4]),Op::ExtendMove{signed:false,destination_width:32,source_width:8,destination:0,source:Operand::HighByte(0)});
    assert_eq!(one(Mode::X64,0,&[0x45,0x0f,0xbe,0xc4]),Op::ExtendMove{signed:true,destination_width:32,source_width:8,destination:8,source:Operand::Register(12)});
    assert_eq!(one(Mode::X64,0,&[0x40,0x0f,0xb6,0xc4]),Op::ExtendMove{signed:false,destination_width:32,source_width:8,destination:0,source:Operand::Register(4)});
}
#[test] fn word_extension_and_rex_priority(){
    assert_eq!(one(Mode::X64,0,&[0x66,0x48,0x0f,0xbf,0xc1]),Op::ExtendMove{signed:true,destination_width:64,source_width:16,destination:0,source:Operand::Register(1)});
    assert_eq!(one(Mode::X86,0,&[0x66,0x0f,0xb6,0xc1]),Op::ExtendMove{signed:false,destination_width:16,source_width:8,destination:0,source:Operand::Register(1)});
}
#[test] fn extension_memory_rip(){
    assert_eq!(one(Mode::X64,0x1000,&[0x48,0x0f,0xbe,0x05,0xfc,0xff,0xff,0xff]),Op::ExtendMove{signed:true,destination_width:64,source_width:8,destination:0,source:Operand::Memory(Memory{base:Base::Rip,index:None,scale:1,displacement:-4,rip_target:Some(Target::Address(0x1004))})});
}
#[test] fn multiply_register_widths(){
    for (mode,prefix,width) in [(Mode::X86,&[][..],32),(Mode::X86,&[0x66][..],16),(Mode::X64,&[0x48][..],64)]{
        let mut b=prefix.to_vec();b.extend([0x0f,0xaf,0xc1]);
        assert_eq!(one(mode,0,&b),Op::Multiply{width,destination:0,source:Operand::Register(1)});
    }
}
#[test] fn multiply_immediate_sign_extension(){
    for raw in 0..=255u8 {
        assert_eq!(one(Mode::X64,0,&[0x48,0x6b,0xc1,raw]),Op::MultiplyImmediate{width:64,destination:0,source:Operand::Register(1),immediate:Immediate{encoded_bits:8,raw:raw as u64,value:raw as i8 as i64 as u64}});
    }
}
#[test] fn multiply_immediate_rip_final_length(){
    assert_eq!(one(Mode::X64,0x1000,&[0x48,0x69,0x05,0,0,0,0,0xff,0xff,0xff,0xff]),Op::MultiplyImmediate{width:64,destination:0,source:Operand::Memory(Memory{base:Base::Rip,index:None,scale:1,displacement:0,rip_target:Some(Target::Address(0x100b))}),immediate:Immediate{encoded_bits:32,raw:0xffffffff,value:u64::MAX}});
}
#[test] fn conditional_move_all_conditions_and_registers(){
    for c in 0..16u8{for dst in 0..16u8{for src in 0..16u8{
        let rex=0x48|((dst>>3)<<2)|(src>>3);
        assert_eq!(one(Mode::X64,0,&[rex,0x0f,0x40|c,0xc0|((dst&7)<<3)|(src&7)]),Op::ConditionalMove{condition:c,width:64,destination:dst,source:Operand::Register(src)});
    }}}
}
#[test] fn setcc_byte_registers(){
    for c in 0..16u8{for r in 0..8u8{
        let dest=if r>=4{Operand::HighByte(r-4)}else{Operand::Register(r)};
        assert_eq!(one(Mode::X86,0,&[0x0f,0x90|c,0xc0|r]),Op::SetCondition{condition:c,destination:dest});
        assert_eq!(one(Mode::X64,0,&[0x41,0x0f,0x90|c,0xc0|r]),Op::SetCondition{condition:c,destination:Operand::Register(r+8)});
    }}
}
#[test] fn advanced_truncation_every_split(){
    for b in [&[0x48,0x0f,0xb6,0x05,0,0,0,0][..],&[0x66,0x69,0x44,0x24,0x01,0x02,0x03],&[0x41,0x0f,0x94,0xc0]]{
        for n in 1..b.len(){let p=x86_decode::decode(Mode::X64,0,&b[..n]).unwrap();assert_eq!(p.stop,Stop::Truncated{offset:0});assert!(p.instructions.is_empty());}
    }
}
#[test] fn excluded_forms_preserve_verified_prefix(){
    for tail in [&[0x66,0x0f,0xb7,0xc0][..],&[0x0f,0x94,0xc8],&[0x67,0x0f,0xb6,0xc0],&[0xf3,0x0f,0x2a,0xc0],&[0x0f,0x38,0x00,0xc0]]{
        let mut b=vec![0x90];b.extend(tail);
        let p=x86_decode::decode(Mode::X64,0,&b).unwrap();assert_eq!(p.stop,Stop::Unsupported{offset:1});assert_eq!(p.consumed,1);assert_eq!(p.instructions.len(),1);
    }
}
