use negrodroid_core::{Cancellation,ReadSession,aarch64_decode::{self,Op,Target,WideKind,Error,MAX_INSTRUCTIONS}};
use std::io::{self,Cursor};
fn one(pc:u64,w:u32)->Op{aarch64_decode::decode(pc,&w.to_le_bytes()).unwrap()[0].op}
#[test]
fn fixed_words_and_unknown_preserved(){
    let words=[0xd503201fu32,0xd65f03c0,0xffffffff,0];
    let bytes:Vec<u8>=words.iter().flat_map(|w|w.to_le_bytes()).collect();
    let d=aarch64_decode::decode(0x1000,&bytes).unwrap();
    assert_eq!(d.iter().map(|x|x.word).collect::<Vec<_>>(),words);
    assert_eq!(d.iter().map(|x|x.address).collect::<Vec<_>>(),[0x1000,0x1004,0x1008,0x100c]);
    assert_eq!(d[0].op,Op::Nop);assert_eq!(d[1].op,Op::Return{register:30});
    assert_eq!(d[2].op,Op::Unknown);assert_eq!(d[3].op,Op::Unknown);
}
#[test]
fn direct_branch_signed_displacements(){
    assert_eq!(one(0x1000,0x14000002),Op::Branch{link:false,target:Target::Address(0x1008)});
    assert_eq!(one(0x1000,0x97ffffff),Op::Branch{link:true,target:Target::Address(0xffc)});
    assert_eq!(one(0x10000000,0x16000000),Op::Branch{link:false,target:Target::Address(0x08000000)});
    assert_eq!(one(0x10000000,0x15ffffff),Op::Branch{link:false,target:Target::Address(0x17fffffc)});
}
#[test]
fn target_overflow_is_explicit(){
    assert_eq!(one(0,0x17ffffff),Op::Branch{link:false,target:Target::Overflow});
    assert_eq!(one(u64::MAX-7,0x14000002),Op::Branch{link:false,target:Target::Overflow});
}
#[test]
fn conditional_compare_and_test_branches(){
    assert_eq!(one(0x1000,0x54000041),Op::Conditional{condition:1,target:Target::Address(0x1008)});
    assert_eq!(one(0x1000,0xb5ffffe3),Op::CompareBranch{wide:true,nonzero:true,register:3,target:Target::Address(0xffc)});
    assert_eq!(one(0x1000,0x34000025),Op::CompareBranch{wide:false,nonzero:false,register:5,target:Target::Address(0x1004)});
    let w=0x37000000|(1<<31)|(7<<19)|(2<<5)|4;
    assert_eq!(one(0x1000,w),Op::TestBranch{nonzero:true,register:4,bit:39,target:Target::Address(0x1008)});
    assert_eq!(one(0x1000,0x54000010),Op::Unknown);
}
#[test]
fn indirect_branches_and_returns(){
    assert_eq!(one(0,0xd61f00a0),Op::RegisterBranch{link:false,register:5});
    assert_eq!(one(0,0xd63f00e0),Op::RegisterBranch{link:true,register:7});
    assert_eq!(one(0,0xd65f0120),Op::Return{register:9});
    assert_eq!(one(0,0xd65f0121),Op::Unknown);
}
#[test]
fn wide_moves_and_reserved_encodings(){
    let imm=0x1234u32<<5;
    assert_eq!(one(0,0xd2800000|imm|3),Op::WideMove{kind:WideKind::Movz,wide:true,register:3,immediate:0x1234,shift:0});
    assert_eq!(one(0,0xf2c00000|imm|4),Op::WideMove{kind:WideKind::Movk,wide:true,register:4,immediate:0x1234,shift:32});
    assert_eq!(one(0,0x12a00000|imm),Op::WideMove{kind:WideKind::Movn,wide:false,register:0,immediate:0x1234,shift:16});
    assert_eq!(one(0,0x52c00000),Op::Unknown);
    assert_eq!(one(0,0x32800000),Op::Unknown);
}
#[test]
fn add_sub_immediates_preserve_raw_register_fields(){
    assert_eq!(one(0,0x91000420),Op::AddSubImmediate{wide:true,subtract:false,set_flags:false,destination:0,source:1,immediate:1,shift:0});
    assert_eq!(one(0,0x71400c3f),Op::AddSubImmediate{wide:false,subtract:true,set_flags:true,destination:31,source:1,immediate:3,shift:12});
    assert_eq!(one(0,0x91800000),Op::Unknown);
}
#[test]
fn range_and_alignment_limits(){
    assert_eq!(aarch64_decode::decode(0,&[]),Err(Error::Length));
    assert_eq!(aarch64_decode::decode(0,&[0;3]),Err(Error::Length));
    assert_eq!(aarch64_decode::decode(2,&[0;4]),Err(Error::Alignment));
    assert_eq!(aarch64_decode::decode(u64::MAX-3,&[0;4]),Err(Error::AddressOverflow));
    assert_eq!(aarch64_decode::decode(0,&vec![0;4*(MAX_INSTRUCTIONS+1)]),Err(Error::Length));
    assert_eq!(aarch64_decode::decode(0,&vec![0;4*MAX_INSTRUCTIONS]).unwrap().len(),MAX_INSTRUCTIONS);
}
#[test]
fn source_offset_independent_from_virtual_address(){
    let mut b=vec![0x77];b.extend(0xd503201fu32.to_le_bytes());b.extend(0xd65f03c0u32.to_le_bytes());
    let c=Cancellation::default();let mut s=ReadSession::new(Cursor::new(b),9,8,c.clone());
    assert!(aarch64_decode::read(&mut s,1,1,2).is_err());assert_eq!(s.remaining_budget(),8);
    let out=aarch64_decode::read(&mut s,1,0x8000,2).unwrap();
    assert_eq!((out[0].address,out[1].address),(0x8000,0x8004));assert_eq!(s.remaining_budget(),0);
    c.cancel();assert_eq!(aarch64_decode::read(&mut s,1,0x8000,1).unwrap_err().kind(),io::ErrorKind::Interrupted);
}
#[test]
fn truncation_charged_and_no_partial_result(){
    let mut s=ReadSession::new(Cursor::new([0u8;3]),8,8,Cancellation::default());
    assert_eq!(aarch64_decode::read(&mut s,0,0,2).unwrap_err().kind(),io::ErrorKind::UnexpectedEof);
    assert_eq!(s.remaining_budget(),0);
}
