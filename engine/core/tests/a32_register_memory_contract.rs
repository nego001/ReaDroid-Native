use negrodroid_core::a32_decode::{self,Op,DataKind,Shift};
fn one(w:u32)->Op{a32_decode::decode(0,&w.to_le_bytes()).unwrap()[0].op}
#[test]
fn immediate_shift_semantics(){
    for (kind,amount,shift) in [(0,0,Shift::Lsl(0)),(0,31,Shift::Lsl(31)),(1,0,Shift::Lsr(32)),
        (1,7,Shift::Lsr(7)),(2,0,Shift::Asr(32)),(2,5,Shift::Asr(5)),(3,0,Shift::Rrx),(3,31,Shift::Ror(31))]{
        let w=0xe0812003|(amount<<7)|(kind<<5);
        assert_eq!(one(w),Op::DataRegister{kind:DataKind::Add,set_flags:false,destination:Some(2),source:Some(1),operand:3,shift});
    }
}
#[test]
fn register_data_roles_and_flags(){
    assert_eq!(one(0xe1b02003),Op::DataRegister{kind:DataKind::Mov,set_flags:true,destination:Some(2),source:None,operand:3,shift:Shift::Lsl(0)});
    assert_eq!(one(0xe1510002),Op::DataRegister{kind:DataKind::Cmp,set_flags:true,destination:None,source:Some(1),operand:2,shift:Shift::Lsl(0)});
    assert_eq!(one(0xe0112003),Op::DataRegister{kind:DataKind::And,set_flags:true,destination:Some(2),source:Some(1),operand:3,shift:Shift::Lsl(0)});
}
#[test]
fn register_special_and_pc_forms_excluded(){
    assert_eq!(one(0xe0812413),Op::DataRegisterShift{kind:DataKind::Add,set_flags:false,destination:Some(2),source:Some(1),operand:3,shift:a32_decode::ShiftKind::Lsl,amount_register:4});
    for w in [0xe081f003,0xe08f2003,0xe081200f,0xe0812f13,0xe1a12003,0xe1501002,0xe1000000]{
        assert_eq!(one(w),Op::Unknown,"{w:08x}");
    }
}
#[test]
fn multiply_accumulate_and_flags(){
    assert_eq!(one(0xe0000291),Op::Multiply{set_flags:false,destination:0,left:1,right:2,accumulator:None});
    assert_eq!(one(0xe0335492),Op::Multiply{set_flags:true,destination:3,left:2,right:4,accumulator:Some(5)});
    for w in [0xe00f0291,0xe0000f91,0xe0001291,0xe0800291]{assert_eq!(one(w),Op::Unknown);}
}
#[test]
fn register_offset_memory(){
    assert_eq!(one(0xe7932104),Op::MemoryRegister{load:true,byte:false,base:3,register:2,offset:4,add:true,shift:Shift::Lsl(2)});
    assert_eq!(one(0xe7432064),Op::MemoryRegister{load:false,byte:true,base:3,register:2,offset:4,add:false,shift:Shift::Rrx});
    for w in [0xe7b32104,0xe7932114,0xe79f2104,0xe793210f]{assert_eq!(one(w),Op::Unknown);}
}
#[test]
fn immediate_pre_and_post_writeback(){
    assert_eq!(one(0xe5b32008),Op::MemoryWriteback{load:true,byte:false,base:3,register:2,pre:true,displacement:8});
    assert_eq!(one(0xe4432007),Op::MemoryWriteback{load:false,byte:true,base:3,register:2,pre:false,displacement:-7});
    for w in [0xe4b32008,0xe5b33008,0xe5bf2008,0xe5b3f008]{assert_eq!(one(w),Op::Unknown);}
}
#[test]
fn block_transfer_modes_and_register_list(){
    for p in 0..2u32{for u in 0..2u32{for l in 0..2u32{
        let w=0xe82d0007|(p<<24)|(u<<23)|(l<<20);
        assert_eq!(one(w),Op::BlockTransfer{load:l!=0,pre:p!=0,increment:u!=0,writeback:true,base:13,list:7});
    }}}
    assert_eq!(one(0xe92d400f),Op::BlockTransfer{load:false,pre:true,increment:false,writeback:true,base:13,list:0x400f});
}
#[test]
fn block_transfer_rejects_pc_empty_user_and_base_conflict(){
    for w in [0xe92d0000,0xe8bd8001,0xe96d0001,0xe92d2001,0xe89f0001]{assert_eq!(one(w),Op::Unknown);}
}
#[test]
fn raw_condition_and_words_preserved(){
    let words=[0x00812003u32,0x10000291,0x27932104,0x35b32008,0x492d400f,0xffffffff];
    let bytes:Vec<_>=words.iter().flat_map(|w|w.to_le_bytes()).collect();
    let d=a32_decode::decode(0x1000,&bytes).unwrap();
    assert_eq!(d.iter().map(|i|i.word).collect::<Vec<_>>(),words);
    assert_eq!(d.iter().map(|i|i.condition).collect::<Vec<_>>(),[0,1,2,3,4,15]);
    assert_eq!(d[5].address,0x1014);assert_eq!(d[5].op,Op::Unknown);
}
#[test]
fn existing_immediate_memory_and_control_flow_distinct(){
    assert!(matches!(one(0xe2812001),Op::DataImmediate{..}));
    assert!(matches!(one(0xe59d2010),Op::MemoryImmediate{..}));
    assert!(matches!(one(0xea000000),Op::Branch{..}));
    assert!(matches!(one(0xe12fff1e),Op::Exchange{..}));
    assert_eq!(one(0xe320f000),Op::Nop);
}
