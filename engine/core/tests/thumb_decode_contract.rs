use negrodroid_core::{Cancellation,ReadSession,thumb_decode::{self,Op,Target,ImmKind,Error,MAX_BYTES}};
use std::io::{self,Cursor};
fn bytes(h:&[u16])->Vec<u8>{h.iter().flat_map(|v|v.to_le_bytes()).collect()}
fn one(pc:u32,h:&[u16])->Op{thumb_decode::decode(pc,&bytes(h)).unwrap()[0].op}
#[test]
fn exhaustive_first_halfword_width(){
    for h in 0..=u16::MAX{
        assert_eq!(thumb_decode::is_wide(h),h>=0xe800);
    }
}
#[test]
fn mixed_width_unknown_preserves_boundaries(){
    let p=thumb_decode::decode(0x1000,&bytes(&[0xbf00,0xe800,0xbf00,0x2007,0xffff,0xffff,0x4770])).unwrap();
    assert_eq!(p.iter().map(|i|i.address).collect::<Vec<_>>(),[0x1000,0x1002,0x1006,0x1008,0x100c]);
    assert_eq!(p.iter().map(|i|i.width()).collect::<Vec<_>>(),[2,4,2,4,2]);
    assert_eq!(p[1].second,Some(0xbf00));assert_eq!(p[1].op,Op::Unknown);
    assert_eq!(p[3].op,Op::Unknown);assert_eq!(p[4].op,Op::Exchange{link:false,register:14});
}
#[test]
fn short_branches_pc_bias_and_condition(){
    assert_eq!(one(0x1000,&[0xe001]),Op::Branch{link:false,condition:None,target:Target::Address(0x1006)});
    assert_eq!(one(0x1000,&[0xe7fc]),Op::Branch{link:false,condition:None,target:Target::Address(0xffc)});
    assert_eq!(one(0x1000,&[0xd1fe]),Op::Branch{link:false,condition:Some(1),target:Target::Address(0x1000)});
    for h in [0xde00,0xdf00]{assert_eq!(one(0,&[h]),Op::Unknown);}
}
#[test]
fn wide_branch_and_bl_signed_offsets(){
    assert_eq!(one(0x1000,&[0xf000,0xf802]),Op::Branch{link:true,condition:None,target:Target::Address(0x1008)});
    assert_eq!(one(0x1000,&[0xf000,0xb802]),Op::Branch{link:false,condition:None,target:Target::Address(0x1008)});
    assert_eq!(one(0x1000,&[0xf7ff,0xfffc]),Op::Branch{link:true,condition:None,target:Target::Address(0xffc)});
    assert_eq!(one(0x1000,&[0xf000,0xe800]),Op::Unknown);
    assert_eq!(one(0x1000,&[0xf000,0x8000]),Op::Branch{link:false,condition:Some(0),target:Target::Address(0x1004)});
}
#[test]
fn checked_target_overflow(){
    assert_eq!(one(0,&[0xe7fc]),Op::Branch{link:false,condition:None,target:Target::Overflow});
    assert_eq!(one(u32::MAX-3,&[0xe000]),Op::Branch{link:false,condition:None,target:Target::Overflow});
}
#[test]
fn immediate_and_exchange_operands(){
    for (h,kind) in [(0x2307,ImmKind::Mov),(0x2b07,ImmKind::Cmp),(0x3307,ImmKind::Add),(0x3b07,ImmKind::Sub)]{
        assert_eq!(one(0,&[h]),Op::Immediate{kind,register:3,value:7});
    }
    assert_eq!(one(0,&[0x4798]),Op::Exchange{link:true,register:3});
    assert_eq!(one(0,&[0x4778]),Op::Unknown);
    assert_eq!(one(0,&[0xbf00]),Op::Nop);
    assert_eq!(one(0,&[0xbf08]),Op::It{condition:0,mask:8});
}
#[test]
fn literal_alignment_and_word_memory(){
    assert_eq!(one(0x1002,&[0x4b02]),Op::LiteralLoad{register:3,target:Target::Address(0x100c)});
    assert_eq!(one(0,&[0x60ca]),Op::MemoryWord{load:false,base:1,register:2,displacement:12});
    assert_eq!(one(0,&[0x68ca]),Op::MemoryWord{load:true,base:1,register:2,displacement:12});
}
#[test]
fn exact_window_alignment_and_limits(){
    assert_eq!(thumb_decode::decode(0,&[]),Err(Error::Length));
    assert_eq!(thumb_decode::decode(0,&[0]),Err(Error::Length));
    assert_eq!(thumb_decode::decode(1,&[0,0]),Err(Error::Alignment));
    assert_eq!(thumb_decode::decode(u32::MAX-1,&[0,0]),Err(Error::AddressOverflow));
    assert_eq!(thumb_decode::decode(0,&vec![0;MAX_BYTES+2]),Err(Error::Length));
    assert_eq!(thumb_decode::decode(0,&vec![0;MAX_BYTES]).unwrap().len(),MAX_BYTES/2);
}
#[test]
fn truncated_wide_rejects_entire_window(){
    assert_eq!(thumb_decode::decode(0,&bytes(&[0xbf00,0xf000])),Err(Error::Truncated{offset:2}));
    assert_eq!(thumb_decode::decode(0,&bytes(&[0xe800])),Err(Error::Truncated{offset:0}));
}
#[test]
fn source_budget_and_cancel(){
    let mut b=vec![0xff];b.extend(bytes(&[0xbf00,0xf000,0xf802]));
    let c=Cancellation::default();let mut s=ReadSession::new(Cursor::new(b),7,6,c.clone());
    let p=thumb_decode::read(&mut s,1,0x1000,6).unwrap();
    assert_eq!(p[1].address,0x1002);assert_eq!(s.remaining_budget(),0);
    c.cancel();assert_eq!(thumb_decode::read(&mut s,1,0x1000,2).unwrap_err().kind(),io::ErrorKind::Interrupted);
}
