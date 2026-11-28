use negrodroid_core::a32_decode::{self,Op,DataKind,ShiftKind,ExtraKind,ExtraOffset};
fn one(w:u32)->Op{a32_decode::decode(0,&w.to_le_bytes()).unwrap()[0].op}
#[test]
fn register_shift_all_types(){
    for (k,shift) in [(0,ShiftKind::Lsl),(1,ShiftKind::Lsr),(2,ShiftKind::Asr),(3,ShiftKind::Ror)]{
        assert_eq!(one(0xe0812413|(k<<5)),Op::DataRegisterShift{kind:DataKind::Add,set_flags:false,destination:Some(2),source:Some(1),operand:3,shift,amount_register:4});
    }
}
#[test]
fn register_shift_unary_and_comparison(){
    assert_eq!(one(0xe1b02413),Op::DataRegisterShift{kind:DataKind::Mov,set_flags:true,destination:Some(2),source:None,operand:3,shift:ShiftKind::Lsl,amount_register:4});
    assert_eq!(one(0xe1510412),Op::DataRegisterShift{kind:DataKind::Cmp,set_flags:true,destination:None,source:Some(1),operand:2,shift:ShiftKind::Lsl,amount_register:4});
}
#[test]
fn register_shift_excludes_pc_and_special_forms(){
    for w in [0xe081f413,0xe08f2413,0xe081241f,0xe0812f13,0xe1a12413,0xe1512412]{assert_eq!(one(w),Op::Unknown,"{w:08x}");}
}
#[test]
fn long_multiply_all_modes(){
    for signed in [false,true]{for accumulate in [false,true]{for flags in [false,true]{
        let w=0xe0810392|((signed as u32)<<22)|((accumulate as u32)<<21)|((flags as u32)<<20);
        assert_eq!(one(w),Op::LongMultiply{signed,accumulate,set_flags:flags,high:1,low:0,left:2,right:3});
    }}}
}
#[test]
fn long_multiply_rejects_pc_and_identical_destinations(){
    for w in [0xe0800392,0xe08f0392,0xe081f392,0xe0810f92,0xe081039f]{assert_eq!(one(w),Op::Unknown);}
}
#[test]
fn extra_immediate_load_store(){
    for (w,kind,load,delta) in [(0xe1d32abc,ExtraKind::Halfword,true,172),(0xe1432abc,ExtraKind::Halfword,false,-172),
        (0xe1d32adc,ExtraKind::SignedByte,true,172),(0xe1532afc,ExtraKind::SignedHalfword,true,-172)]{
        assert_eq!(one(w),Op::ExtraMemory{kind,load,base:3,register:2,offset:ExtraOffset::Immediate(delta)});
    }
}
#[test]
fn extra_register_offsets(){
    for (w,kind,load,add) in [(0xe19320b4,ExtraKind::Halfword,true,true),(0xe10320b4,ExtraKind::Halfword,false,false),
        (0xe19320d4,ExtraKind::SignedByte,true,true),(0xe11320f4,ExtraKind::SignedHalfword,true,false)]{
        assert_eq!(one(w),Op::ExtraMemory{kind,load,base:3,register:2,offset:ExtraOffset::Register{register:4,add}});
    }
}
#[test]
fn extra_excluded_forms(){
    for w in [0xe1c320d4,0xe1c320f4,0xe1f320b4,0xe0d320b4,0xe1df20b4,0xe1d3f0b4,0xe19320bf,0xe19321b4]{
        assert_eq!(one(w),Op::Unknown,"{w:08x}");
    }
}
#[test]
fn extra_immediate_all_256_values(){
    for n in 0..256u32{for add in [false,true]{
        let w=0xe15320b0|((add as u32)<<23)|((n>>4)<<8)|(n&15);
        assert_eq!(one(w),Op::ExtraMemory{kind:ExtraKind::Halfword,load:true,base:3,register:2,
            offset:ExtraOffset::Immediate(if add{n as i16}else{-(n as i16)})});
    }}
}
#[test]
fn old_forms_and_new_forms_distinct(){
    assert!(matches!(one(0xe0812003),Op::DataRegister{..}));
    assert!(matches!(one(0xe0812413),Op::DataRegisterShift{..}));
    assert!(matches!(one(0xe0000291),Op::Multiply{..}));
    assert!(matches!(one(0xe0810392),Op::LongMultiply{..}));
    assert!(matches!(one(0xe5932004),Op::MemoryImmediate{..}));
    assert!(matches!(one(0xe19320b4),Op::ExtraMemory{..}));
    assert_eq!(one(0xffffffff),Op::Unknown);
}
