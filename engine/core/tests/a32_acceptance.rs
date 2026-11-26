//! Original linked ARMv7 A32 fixture; no execution.
use negrodroid_core::{Cancellation,ReadSession,a32_decode::{self,Op,Target,DataKind,Shift,ShiftKind,ExtraKind,ExtraOffset}};
use std::io::Cursor;
const BASE:u32=0x1000;
const WORDS:[u32;27]=[
    0xe320f000,0xe3a000ff,0xe2801001,0xe3510007,0x104121a0,0xe1a03062,0xe0834112,
    0xe0050394,0xe0263495,0xe0887695,0xe0ea9695,0xe59d0010,0xe54d1007,0xe7932104,
    0xe5b32008,0xe4432007,0xe92d400f,0xe8bd400f,0xe1d32abc,0xe19320d4,0xe1532afc,
    0x0a000003,0xeb000002,0xe12fff1e,0xe12fff33,0xffffffff,0xe12fff1e];
fn bytes()->Vec<u8>{WORDS.iter().flat_map(|w|w.to_le_bytes()).collect()}
fn expected()->Vec<Op>{
    use Op::*;
    vec![
        Nop,
        DataImmediate{kind:DataKind::Mov,set_flags:false,destination:Some(0),source:None,imm8:255,rotate:0,value:255},
        DataImmediate{kind:DataKind::Add,set_flags:false,destination:Some(1),source:Some(0),imm8:1,rotate:0,value:1},
        DataImmediate{kind:DataKind::Cmp,set_flags:true,destination:None,source:Some(1),imm8:7,rotate:0,value:7},
        DataRegister{kind:DataKind::Sub,set_flags:false,destination:Some(2),source:Some(1),operand:0,shift:Shift::Lsr(3)},
        DataRegister{kind:DataKind::Mov,set_flags:false,destination:Some(3),source:None,operand:2,shift:Shift::Rrx},
        DataRegisterShift{kind:DataKind::Add,set_flags:false,destination:Some(4),source:Some(3),operand:2,shift:ShiftKind::Lsl,amount_register:1},
        Multiply{set_flags:false,destination:5,left:4,right:3,accumulator:None},
        Multiply{set_flags:false,destination:6,left:5,right:4,accumulator:Some(3)},
        LongMultiply{signed:false,accumulate:false,set_flags:false,high:8,low:7,left:5,right:6},
        LongMultiply{signed:true,accumulate:true,set_flags:false,high:10,low:9,left:5,right:6},
        MemoryImmediate{load:true,byte:false,base:13,register:0,displacement:16},
        MemoryImmediate{load:false,byte:true,base:13,register:1,displacement:-7},
        MemoryRegister{load:true,byte:false,base:3,register:2,offset:4,add:true,shift:Shift::Lsl(2)},
        MemoryWriteback{load:true,byte:false,base:3,register:2,pre:true,displacement:8},
        MemoryWriteback{load:false,byte:true,base:3,register:2,pre:false,displacement:-7},
        BlockTransfer{load:false,pre:true,increment:false,writeback:true,base:13,list:0x400f},
        BlockTransfer{load:true,pre:false,increment:true,writeback:true,base:13,list:0x400f},
        ExtraMemory{kind:ExtraKind::Halfword,load:true,base:3,register:2,offset:ExtraOffset::Immediate(172)},
        ExtraMemory{kind:ExtraKind::SignedByte,load:true,base:3,register:2,offset:ExtraOffset::Register{register:4,add:true}},
        ExtraMemory{kind:ExtraKind::SignedHalfword,load:true,base:3,register:2,offset:ExtraOffset::Immediate(-172)},
        Branch{link:false,target:Target::Address(0x1068)},
        Branch{link:true,target:Target::Address(0x1068)},
        Exchange{link:false,register:14},
        Exchange{link:true,register:3},
        Unknown,
        Exchange{link:false,register:14},
    ]
}
#[test]
fn linked_a32_corpus_all_typed_operands(){
    let p=a32_decode::decode(BASE,&bytes()).unwrap();
    assert_eq!(p.len(),WORDS.len());
    for (i,(ins,op)) in p.iter().zip(expected()).enumerate(){
        assert_eq!(ins.address,BASE+4*i as u32);assert_eq!(ins.word,WORDS[i]);
        assert_eq!(ins.condition,(WORDS[i]>>28) as u8);
        assert_eq!(ins.op,op,"word {i} at {:08x}",ins.address);
    }
}
#[test]
fn every_internal_split_equals_whole(){
    let b=bytes();let whole=a32_decode::decode(BASE,&b).unwrap();
    for i in 1..WORDS.len(){
        let mut p=a32_decode::decode(BASE,&b[..4*i]).unwrap();
        p.extend(a32_decode::decode(BASE+4*i as u32,&b[4*i..]).unwrap());
        assert_eq!(p,whole);
    }
}
#[test]
fn nonzero_source_offset_and_exact_budget(){
    let b=bytes();let mut file=vec![0xaa;13];file.extend(&b);
    let mut s=ReadSession::new(Cursor::new(file),13+b.len() as u64,b.len() as u64,Cancellation::default());
    assert_eq!(a32_decode::read(&mut s,13,BASE,WORDS.len()).unwrap(),a32_decode::decode(BASE,&b).unwrap());
    assert_eq!(s.remaining_budget(),0);
}
#[test]
fn unknown_preserves_next_instruction_alignment(){
    let p=a32_decode::decode(BASE,&bytes()).unwrap();
    assert_eq!(p.iter().filter(|i|i.op==Op::Unknown).count(),1);
    assert_eq!(p[25].address,0x1064);assert_eq!(p[26].address,0x1068);
    assert_eq!(p[26].op,Op::Exchange{link:false,register:14});
}
#[test]
fn all_partial_words_rejected(){
    let b=bytes();for i in 1..b.len(){if i%4!=0{assert_eq!(a32_decode::decode(BASE,&b[..i]),Err(a32_decode::Error::Length));}}
}
#[test]
fn cancelled_read_preserves_budget(){
    let b=bytes();let c=Cancellation::default();let mut s=ReadSession::new(Cursor::new(b.clone()),b.len() as u64,b.len() as u64,c.clone());
    c.cancel();assert_eq!(a32_decode::read(&mut s,0,BASE,WORDS.len()).unwrap_err().kind(),std::io::ErrorKind::Interrupted);
    assert_eq!(s.remaining_budget(),b.len() as u64);
}
