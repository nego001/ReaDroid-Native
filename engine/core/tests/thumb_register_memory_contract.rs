use negrodroid_core::thumb_decode::{self,Op,ShiftKind,Operand,AluKind,HighKind,MemKind};
fn one(h:u16)->Op{thumb_decode::decode(0,&h.to_le_bytes()).unwrap()[0].op}
#[test]
fn short_shift_all_amounts(){
    for (k,kind) in [(0,ShiftKind::Lsl),(1,ShiftKind::Lsr),(2,ShiftKind::Asr)]{
        for amount in 0..32u16{
            assert_eq!(one((k<<11)|(amount<<6)|(3<<3)|2),Op::ShiftImmediate{kind,amount:if amount==0&&k!=0{32}else{amount as u8},destination:2,source:3});
        }
    }
}
#[test]
fn short_add_sub_three_operands(){
    for immediate in [false,true]{for subtract in [false,true]{
        let h=0x1800|((immediate as u16)<<10)|((subtract as u16)<<9)|(4<<6)|(3<<3)|2;
        assert_eq!(one(h),Op::AddSub{subtract,destination:2,source:3,operand:if immediate{Operand::Immediate(4)}else{Operand::Register(4)}});
    }}
}
#[test]
fn short_alu_all_16_opcodes(){
    let kinds=[AluKind::And,AluKind::Eor,AluKind::Lsl,AluKind::Lsr,AluKind::Asr,AluKind::Adc,AluKind::Sbc,
        AluKind::Ror,AluKind::Tst,AluKind::Rsb,AluKind::Cmp,AluKind::Cmn,AluKind::Orr,AluKind::Mul,AluKind::Bic,AluKind::Mvn];
    for (k,kind) in kinds.into_iter().enumerate(){
        assert_eq!(one(0x4000|((k as u16)<<6)|(5<<3)|2),Op::Alu{kind,rdn:2,source:5});
    }
}
#[test]
fn high_register_roles_and_exclusions(){
    assert_eq!(one(0x4488),Op::HighRegister{kind:HighKind::Add,destination:8,source:1});
    assert_eq!(one(0x4548),Op::HighRegister{kind:HighKind::Cmp,destination:0,source:9});
    assert_eq!(one(0x46c8),Op::HighRegister{kind:HighKind::Mov,destination:8,source:9});
    for h in [0x4501,0x46ff,0x46ed,0x47ff]{assert_eq!(one(h),Op::Unknown);}
}
#[test]
fn all_register_offset_memory_types(){
    let kinds=[(false,MemKind::Word),(false,MemKind::Half),(false,MemKind::Byte),(true,MemKind::SignedByte),
        (true,MemKind::Word),(true,MemKind::Half),(true,MemKind::Byte),(true,MemKind::SignedHalf)];
    for (k,(load,kind)) in kinds.into_iter().enumerate(){
        assert_eq!(one(0x5000|((k as u16)<<9)|(4<<6)|(3<<3)|2),Op::MemoryRegister{load,kind,base:3,register:2,offset:4});
    }
}
#[test]
fn byte_half_immediate_scaling(){
    for (base,kind,scale) in [(0x7000,MemKind::Byte,1),(0x8000,MemKind::Half,2)]{
        for load in [false,true]{for imm in 0..32u16{
            let h=base|((load as u16)<<11)|(imm<<6)|(3<<3)|2;
            assert_eq!(one(h),Op::MemoryImmediate{load,kind,base:3,register:2,displacement:imm*scale});
        }}
    }
}
#[test]
fn stack_relative_word_memory(){
    for load in [false,true]{
        assert_eq!(one(0x9000|((load as u16)<<11)|(3<<8)|255),Op::MemoryImmediate{load,kind:MemKind::Word,base:13,register:3,displacement:1020});
    }
}
#[test]
fn push_pop_lr_pc_lists(){
    assert_eq!(one(0xb503),Op::StackList{pop:false,list:0x4003});
    assert_eq!(one(0xbd03),Op::StackList{pop:true,list:0x8003});
    assert_eq!(one(0xb500),Op::StackList{pop:false,list:0x4000});
    assert_eq!(one(0xbd00),Op::StackList{pop:true,list:0x8000});
    for h in [0xb400,0xbc00]{assert_eq!(one(h),Op::Unknown);}
}
#[test]
fn block_transfer_lists_and_conflicts(){
    assert_eq!(one(0xc307),Op::BlockTransfer{load:false,base:3,list:7});
    assert_eq!(one(0xcb07),Op::BlockTransfer{load:true,base:3,list:7});
    for h in [0xc300,0xcb00,0xc308,0xcb08]{assert_eq!(one(h),Op::Unknown);}
}
#[test]
fn mixed_new_and_existing_instruction_boundaries(){
    let words=[0x0008u16,0x1888,0xf000,0xf802,0xb503,0x6800,0xbf00,0xbd03];
    let bytes:Vec<_>=words.iter().flat_map(|w|w.to_le_bytes()).collect();
    let p=thumb_decode::decode(0x1000,&bytes).unwrap();
    assert_eq!(p.iter().map(|i|i.address).collect::<Vec<_>>(),[0x1000,0x1002,0x1004,0x1008,0x100a,0x100c,0x100e]);
    assert!(matches!(p[2].op,Op::Branch{link:true,..}));
    assert_eq!(p[5].op,Op::Nop);
}
