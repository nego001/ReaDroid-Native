use negrodroid_core::{Cancellation,ReadSession,aarch64_decode::{self,Op,Shift,LogicalKind}};
use std::io::Cursor;
fn one(w:u32)->Op{aarch64_decode::decode(0,&w.to_le_bytes()).unwrap()[0].op}
#[test]
fn add_sub_register_all_flags_and_shifts(){
    for wide in [false,true]{for subtract in [false,true]{for flags in [false,true]{for (sh,shift) in [(0,Shift::Lsl),(1,Shift::Lsr),(2,Shift::Asr)]{
        let w=0x0b000000|((wide as u32)<<31)|((subtract as u32)<<30)|((flags as u32)<<29)|(sh<<22)|(7<<16)|(13<<10)|(9<<5)|4;
        assert_eq!(one(w),Op::AddSubRegister{wide,subtract,set_flags:flags,destination:4,left:9,right:7,shift,amount:13});
    }}}}
}
#[test]
fn add_sub_rejects_reserved_and_extended_forms(){
    for w in [0x0bc00000,0x0b008000,0x8b200000,0xcb200000]{assert_eq!(one(w),Op::Unknown);}
    assert_eq!(one(0x8b00fc00),Op::AddSubRegister{wide:true,subtract:false,set_flags:false,destination:0,left:0,right:0,shift:Shift::Lsl,amount:63});
}
#[test]
fn logical_register_all_kinds_invert_and_shifts(){
    for wide in [false,true]{for invert in [false,true]{for (k,kind) in [(0,LogicalKind::And),(1,LogicalKind::Orr),(2,LogicalKind::Eor),(3,LogicalKind::Ands)]{
        for (sh,shift) in [(0,Shift::Lsl),(1,Shift::Lsr),(2,Shift::Asr),(3,Shift::Ror)]{
            let w=0x0a000000|((wide as u32)<<31)|(k<<29)|(sh<<22)|((invert as u32)<<21)|(8<<16)|(31<<10)|(31<<5)|5;
            assert_eq!(one(w),Op::LogicalRegister{kind,wide,invert,destination:5,left:31,right:8,shift,amount:31});
        }
    }}}
}
#[test]
fn logical_register_width_limits_and_alias_raw(){
    assert_eq!(one(0x0a008000),Op::Unknown);
    assert_eq!(one(0xaa0103e0),Op::LogicalRegister{kind:LogicalKind::Orr,wide:true,invert:false,destination:0,left:31,right:1,shift:Shift::Lsl,amount:0});
}
#[test]
fn multiply_add_sub_all_widths(){
    for wide in [false,true]{for subtract in [false,true]{
        let w=0x1b000000|((wide as u32)<<31)|((subtract as u32)<<15)|(4<<16)|(7<<10)|(9<<5)|3;
        assert_eq!(one(w),Op::MultiplyAdd{wide,subtract,destination:3,left:9,right:4,accumulator:7});
    }}
    assert_eq!(one(0x9b027c20),Op::MultiplyAdd{wide:true,subtract:false,destination:0,left:1,right:2,accumulator:31});
}
#[test]
fn excludes_widening_and_high_half_multiply(){
    for w in [0x9b200000,0x9ba00000,0x9b400000,0x9bc00000,0x3b000000]{assert_eq!(one(w),Op::Unknown);}
}
#[test]
fn divide_both_widths_and_signedness(){
    for wide in [false,true]{for signed in [false,true]{
        let w=0x1ac00800|((wide as u32)<<31)|((signed as u32)<<10)|(31<<16)|(7<<5)|2;
        assert_eq!(one(w),Op::Divide{wide,signed,destination:2,left:7,right:31});
    }}
    assert_eq!(one(0x1ac01000),Op::Unknown);
}
#[test]
fn variable_shift_four_kinds(){
    for wide in [false,true]{for (sh,shift) in [(0,Shift::Lsl),(1,Shift::Lsr),(2,Shift::Asr),(3,Shift::Ror)]{
        let w=0x1ac02000|((wide as u32)<<31)|(sh<<10)|(12<<16)|(5<<5)|9;
        assert_eq!(one(w),Op::VariableShift{wide,shift,destination:9,source:5,amount_register:12});
    }}
    assert_eq!(one(0x1ac03000),Op::Unknown);
}
#[test]
fn existing_and_new_encodings_remain_distinct(){
    assert!(matches!(one(0x91000420),Op::AddSubImmediate{..}));
    assert!(matches!(one(0xf9400421),Op::MemoryImmediate{..}));
    assert!(matches!(one(0x8b020020),Op::AddSubRegister{..}));
    assert_eq!(one(0xd503201f),Op::Nop);
    assert_eq!(one(0xffffffff),Op::Unknown);
}
#[test]
fn source_budget_no_operand_evaluation(){
    let words=[0x9adf0820u32,0x9b027c20,0x9ac22c20];
    let bytes:Vec<u8>=words.iter().flat_map(|w|w.to_le_bytes()).collect();
    let mut s=ReadSession::new(Cursor::new(bytes),12,12,Cancellation::default());
    let p=aarch64_decode::read(&mut s,0,0x8000,3).unwrap();
    assert_eq!(p.iter().map(|x|x.word).collect::<Vec<_>>(),words);
    assert_eq!(p[2].address,0x8008);
    assert_eq!(s.remaining_budget(),0);
}
