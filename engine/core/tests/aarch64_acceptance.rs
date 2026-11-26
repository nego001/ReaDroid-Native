//! Linked A64 corpus; selected code interval only, not literal pool.
//! Reproduce with fixture source and commands in fixtures/aarch64_acceptance.md.
use negrodroid_core::{Cancellation,ReadSession,aarch64_decode::{self,Op,Target,WideKind,Shift,LogicalKind,BitfieldKind,FpFormat,FpBinaryKind,FpUnaryKind,VectorLogicalKind}};
use std::io::Cursor;
const BASE:u64=0x1000;
const WORDS:[u32;31]=[
    0xd503201f,0xd2824680,0xf2b579a0,0x910043e1,0xcb400c22,0x92401c43,0xaac21464,0xd3443c85,
    0x93c420a6,0x9b0510c7,0x9ac60ce8,0x9ac72109,0x10fffe8a,0x9000000b,0xf9400bec,0xb81fc3ed,
    0xa9423fee,0x1e222820,0x1e61c083,0x4ea784c5,0x6e2a1d28,0xb4000120,0xb6380101,0x540000e0,
    0x94000006,0x14000005,0xd61f0200,0xd63f0220,0x58000092,0xffffffff,0xd65f03c0];
fn bytes()->Vec<u8>{WORDS.iter().flat_map(|w|w.to_le_bytes()).collect()}
fn expected()->Vec<Op>{
    let done=Target::Address(0x1078);
    vec![
        Op::Nop,
        Op::WideMove{kind:WideKind::Movz,wide:true,register:0,immediate:0x1234,shift:0},
        Op::WideMove{kind:WideKind::Movk,wide:true,register:0,immediate:0xabcd,shift:16},
        Op::AddSubImmediate{wide:true,subtract:false,set_flags:false,destination:1,source:31,immediate:16,shift:0},
        Op::AddSubRegister{wide:true,subtract:true,set_flags:false,destination:2,left:1,right:0,shift:Shift::Lsr,amount:3},
        Op::LogicalImmediate{kind:LogicalKind::And,wide:true,destination:3,source:2,n:1,immr:0,imms:7,mask:255},
        Op::LogicalRegister{kind:LogicalKind::Orr,wide:true,invert:false,destination:4,left:3,right:2,shift:Shift::Ror,amount:5},
        Op::Bitfield{kind:BitfieldKind::Unsigned,wide:true,destination:5,source:4,immr:4,imms:15},
        Op::Extract{wide:true,destination:6,left:5,right:4,lsb:8},
        Op::MultiplyAdd{wide:true,subtract:false,destination:7,left:6,right:5,accumulator:4},
        Op::Divide{wide:true,signed:true,destination:8,left:7,right:6},
        Op::VariableShift{wide:true,shift:Shift::Lsl,destination:9,source:8,amount_register:7},
        Op::PcAddress{page:false,register:10,target:Target::Address(BASE)},
        Op::PcAddress{page:true,register:11,target:Target::Address(BASE)},
        Op::MemoryImmediate{load:true,width:8,scaled:true,base:31,register:12,displacement:16},
        Op::MemoryImmediate{load:false,width:4,scaled:false,base:31,register:13,displacement:-4},
        Op::MemoryPair{load:true,width:8,base:31,first:14,second:15,displacement:32},
        Op::FpBinary{kind:FpBinaryKind::Add,format:FpFormat::Single,destination:0,left:1,right:2},
        Op::FpUnary{kind:FpUnaryKind::Sqrt,format:FpFormat::Double,destination:3,source:4},
        Op::VectorArithmetic{subtract:false,vector_bits:128,element_bits:32,destination:5,left:6,right:7},
        Op::VectorLogical{kind:VectorLogicalKind::Eor,vector_bits:128,destination:8,left:9,right:10},
        Op::CompareBranch{wide:true,nonzero:false,register:0,target:done},
        Op::TestBranch{nonzero:false,register:1,bit:39,target:done},
        Op::Conditional{condition:0,target:done},
        Op::Branch{link:true,target:done},
        Op::Branch{link:false,target:done},
        Op::RegisterBranch{link:false,register:16},
        Op::RegisterBranch{link:true,register:17},
        Op::LiteralLoad{width:8,signed:false,register:18,target:Target::Address(0x1080)},
        Op::Unknown,
        Op::Return{register:30},
    ]
}
#[test]
fn linked_corpus_all_words_and_operands(){
    let p=aarch64_decode::decode(BASE,&bytes()).unwrap();
    assert_eq!(p.len(),WORDS.len());
    for (i,(ins,op)) in p.iter().zip(expected()).enumerate(){
        assert_eq!(ins.address,BASE+i as u64*4);
        assert_eq!(ins.word,WORDS[i]);
        assert_eq!(ins.op,op,"instruction {i} at {:x}",ins.address);
    }
}
#[test]
fn every_split_at_instruction_boundary_matches_whole(){
    let b=bytes();let full=aarch64_decode::decode(BASE,&b).unwrap();
    for i in 1..WORDS.len(){
        let mut p=aarch64_decode::decode(BASE,&b[..i*4]).unwrap();
        p.extend(aarch64_decode::decode(BASE+(i*4) as u64,&b[i*4..]).unwrap());
        assert_eq!(p,full);
    }
}
#[test]
fn read_corpus_from_nonzero_offset_without_reading_literals(){
    let b=bytes();let mut file=vec![0xaa;17];file.extend(&b);
    let mut s=ReadSession::new(Cursor::new(file),17+b.len() as u64,b.len() as u64,Cancellation::default());
    let p=aarch64_decode::read(&mut s,17,BASE,WORDS.len()).unwrap();
    assert_eq!(p,aarch64_decode::decode(BASE,&b).unwrap());
    assert_eq!(s.remaining_budget(),0);
}
#[test]
fn unknown_word_does_not_change_alignment(){
    let p=aarch64_decode::decode(BASE,&bytes()).unwrap();
    assert_eq!(p.iter().filter(|x|x.op==Op::Unknown).count(),1);
    assert_eq!(p[29].address,0x1074);assert_eq!(p[30].address,0x1078);
    assert_eq!(p[30].op,Op::Return{register:30});
}
#[test]
fn cancellation_prevents_result_and_preserves_budget(){
    let b=bytes();let c=Cancellation::default();
    let mut s=ReadSession::new(Cursor::new(b.clone()),b.len() as u64,b.len() as u64,c.clone());
    c.cancel();
    assert_eq!(aarch64_decode::read(&mut s,0,BASE,WORDS.len()).unwrap_err().kind(),std::io::ErrorKind::Interrupted);
    assert_eq!(s.remaining_budget(),b.len() as u64);
}
#[test]
fn all_partial_words_rejected(){
    let b=bytes();
    for cut in 1..b.len(){if cut%4!=0{assert_eq!(aarch64_decode::decode(BASE,&b[..cut]),Err(aarch64_decode::Error::Length));}}
}
