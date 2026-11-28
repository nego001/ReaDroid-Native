//! Synthetic linked ARMv7 Thumb fixture. See fixtures/thumb_acceptance.md.
use negrodroid_core::{Cancellation,ReadSession,thumb_decode::{self,Op,Target,Context,ContextError,Error,ImmKind,ShiftKind,Operand,AluKind,HighKind,MemKind}};
use std::io::Cursor;
const BASE:u32=0x1000;
const HALVES:[u16;32]=[
    0xbf00,0x2007,0x08c1,0x180a,0x404a,0x4690,0x88d3,0x5653,0xb503,
    0xf241,0x2434,0xf6ca,0x34cd,0xf204,0x7589,0xf8d5,0x6123,0xbf0c,
    0x2001,0x2002,0xbf1c,0xf245,0x6778,0x3101,0xf000,0x8005,
    0xf000,0xf803,0xe001,0xffff,0xffff,0xbd03];
const OFFSETS:[u32;24]=[0,2,4,6,8,10,12,14,16,18,22,26,30,34,36,38,40,42,46,48,52,56,58,62];
fn bytes()->Vec<u8>{HALVES.iter().flat_map(|w|w.to_le_bytes()).collect()}
fn expected()->Vec<Op>{
    use Op::*;
    let done=Target::Address(0x103e);
    vec![
        Nop,
        Immediate{kind:ImmKind::Mov,register:0,value:7},
        ShiftImmediate{kind:ShiftKind::Lsr,amount:3,destination:1,source:0},
        AddSub{subtract:false,destination:2,source:1,operand:Operand::Register(0)},
        Alu{kind:AluKind::Eor,rdn:2,source:1},
        HighRegister{kind:HighKind::Mov,destination:8,source:2},
        MemoryImmediate{load:true,kind:MemKind::Half,base:2,register:3,displacement:6},
        MemoryRegister{load:true,kind:MemKind::SignedByte,base:2,register:3,offset:1},
        StackList{pop:false,list:0x4003},
        WideMove{top:false,destination:4,value:0x1234},
        WideMove{top:true,destination:4,value:0xabcd},
        WideAddSub{subtract:false,destination:5,source:4,value:0x789},
        MemoryImmediate{load:true,kind:MemKind::Word,base:5,register:6,displacement:0x123},
        It{condition:0,mask:12},
        Immediate{kind:ImmKind::Mov,register:0,value:1},
        Immediate{kind:ImmKind::Mov,register:0,value:2},
        It{condition:1,mask:12},
        WideMove{top:false,destination:7,value:0x5678},
        Immediate{kind:ImmKind::Add,register:1,value:1},
        Branch{link:false,condition:Some(0),target:done},
        Branch{link:true,condition:None,target:done},
        Branch{link:false,condition:None,target:done},
        Unknown,
        StackList{pop:true,list:0x8003},
    ]
}
#[test]
fn linked_fixture_exact_words_widths_operands(){
    let p=thumb_decode::decode(BASE,&bytes()).unwrap();
    assert_eq!(p.len(),OFFSETS.len());
    for (i,(ins,op)) in p.iter().zip(expected()).enumerate(){
        let offset=OFFSETS[i];
        let end=OFFSETS.get(i+1).copied().unwrap_or(64);
        assert_eq!(ins.address,BASE+offset);
        assert_eq!(u32::from(ins.width()),end-offset);
        assert_eq!(ins.first,HALVES[offset as usize/2]);
        assert_eq!(ins.second,if end-offset==4{Some(HALVES[offset as usize/2+1])}else{None});
        assert_eq!(ins.op,op,"offset {offset}");
    }
}
#[test]
fn contextual_fixture_conditions_and_final_slot(){
    let (p,end)=thumb_decode::decode_context(BASE,&bytes(),Context::outside(BASE)).unwrap();
    for (i,a) in p.iter().enumerate(){
        let want=match i{14=>Some(0),15|17|18=>Some(1),_=>None};
        assert_eq!(a.it_condition,want);
        assert_eq!(a.last_in_it,i==15||i==18);
    }
    assert_eq!(end.next_address(),BASE+64);assert_eq!(end.pending_condition(),None);
}
#[test]
fn all_23_instruction_splits_match_contextual_whole(){
    let b=bytes();let (whole,end)=thumb_decode::decode_context(BASE,&b,Context::outside(BASE)).unwrap();
    for &offset in &OFFSETS[1..]{
        let (mut prefix,c)=thumb_decode::decode_context(BASE,&b[..offset as usize],Context::outside(BASE)).unwrap();
        let (tail,next)=thumb_decode::decode_context(BASE+offset,&b[offset as usize..],c).unwrap();
        prefix.extend(tail);assert_eq!(prefix,whole);assert_eq!(next,end);
    }
}
#[test]
fn every_non_boundary_cut_rejected(){
    let b=bytes();
    for cut in 1..b.len(){
        if cut%2!=0{assert_eq!(thumb_decode::decode(BASE,&b[..cut]),Err(Error::Length));}
        else if !OFFSETS.contains(&(cut as u32)){
            assert_eq!(thumb_decode::decode_context(BASE,&b[..cut],Context::outside(BASE)),Err(ContextError::Decode(Error::Truncated{offset:cut-2})));
        }
    }
}
#[test]
fn exact_file_window_with_independent_source_offset(){
    let b=bytes();let mut source=vec![0xaa;13];source.extend(&b);source.extend([0xbb;8]);
    let mut s=ReadSession::new(Cursor::new(source),85,64,Cancellation::default());
    assert_eq!(thumb_decode::read(&mut s,13,BASE,64).unwrap(),thumb_decode::decode(BASE,&b).unwrap());
    assert_eq!(s.remaining_budget(),0);
}
#[test]
fn cancelled_read_and_unknown_wide_boundaries(){
    let c=Cancellation::default();let mut s=ReadSession::new(Cursor::new(bytes()),64,64,c.clone());
    c.cancel();
    assert_eq!(thumb_decode::read(&mut s,0,BASE,64).unwrap_err().kind(),std::io::ErrorKind::Interrupted);
    assert_eq!(s.remaining_budget(),64);
    let p=thumb_decode::decode(BASE,&bytes()).unwrap();
    assert_eq!(p.iter().filter(|x|x.op==Op::Unknown).count(),1);
    assert_eq!(p[22].address,0x103a);assert_eq!(p[22].width(),4);
    assert_eq!(p[23].address,0x103e);assert_eq!(p[23].op,Op::StackList{pop:true,list:0x8003});
}
