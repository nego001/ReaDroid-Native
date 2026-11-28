use negrodroid_core::thumb_decode::{self,Op,Context,ContextError,Error};
fn bytes(h:&[u16])->Vec<u8>{h.iter().flat_map(|v|v.to_le_bytes()).collect()}
fn run(h:&[u16])->Result<(Vec<thumb_decode::Annotated>,Context),ContextError>{
    thumb_decode::decode_context(0x1000,&bytes(h),Context::outside(0x1000))
}
#[test]
fn raw_it_and_hint_distinction(){
    let p=thumb_decode::decode(0,&bytes(&[0xbf08,0xbf00,0xbf10,0xbfe8,0xbff8])).unwrap();
    assert_eq!(p[0].op,Op::It{condition:0,mask:8});
    assert_eq!(p[1].op,Op::Nop);assert_eq!(p[2].op,Op::Unknown);
    assert_eq!(p[3].op,Op::Unknown);assert_eq!(p[4].op,Op::Unknown);
}
#[test]
fn exhaustive_supported_it_conditions_and_masks(){
    // Independent bit-position oracle: trailing one marks the final slot;
    // each earlier mask bit supplies the next condition's low bit.
    for cond in 0..14u16{for mask in 1..16u16{
        let count=4-mask.trailing_zeros() as usize;
        let mut h=vec![0xbf00|(cond<<4)|mask];h.extend(vec![0x2001;count]);h.push(0x2002);
        let (p,c)=run(&h).unwrap();
        assert_eq!(p[0].it_condition,None);
        for slot in 0..count{
            let want=if slot==0{cond}else{(cond&14)|((mask>>(4-slot))&1)};
            assert_eq!(p[slot+1].it_condition,Some(want as u8));
            assert_eq!(p[slot+1].last_in_it,slot+1==count);
        }
        assert_eq!(p[count+1].it_condition,None);assert_eq!(c.pending_condition(),None);
    }}
}
#[test]
fn then_else_known_sequences(){
    let (p,_)=run(&[0xbf0c,0x2001,0x2002]).unwrap();
    assert_eq!(p[1].it_condition,Some(0));assert_eq!(p[2].it_condition,Some(1));
    let (p,_)=run(&[0xbf14,0x2001,0x2002]).unwrap();
    assert_eq!(p[1].it_condition,Some(1));assert_eq!(p[2].it_condition,Some(0));
}
#[test]
fn mixed_width_consumes_one_slot(){
    let (p,c)=run(&[0xbf04,0xf241,0x2034,0x2001,0x2002]).unwrap();
    assert_eq!(p[1].instruction.width(),4);assert_eq!(p[1].it_condition,Some(0));
    assert_eq!(p[2].instruction.address,0x1006);assert!(p[2].last_in_it);
    assert_eq!(p[3].it_condition,None);assert_eq!(c.next_address(),0x100a);
}
#[test]
fn continuation_matches_whole_window(){
    let h=[0xbf07,0x2001,0xf241,0x2034,0x2002,0x2003,0x2004];
    let (whole,end)=run(&h).unwrap();
    for split in [1,2,4,5,6]{
        let (mut p,c)=run(&h[..split]).unwrap();
        let (tail,next)=thumb_decode::decode_context(c.next_address(),&bytes(&h[split..]),c).unwrap();
        p.extend(tail);assert_eq!(p,whole);assert_eq!(next,end);
    }
}
#[test]
fn context_rejects_discontinuity_and_truncation(){
    let (_,c)=run(&[0xbf04]).unwrap();assert_eq!(c.pending_condition(),Some(0));
    assert_eq!(thumb_decode::decode_context(0x1004,&bytes(&[0x2001]),c),Err(ContextError::Discontinuous));
    assert_eq!(thumb_decode::decode_context(0x1002,&bytes(&[0xf241]),c),Err(ContextError::Decode(Error::Truncated{offset:0})));
    assert_eq!(c.pending_condition(),Some(0));
}
#[test]
fn nested_and_excluded_it_rejected(){
    assert_eq!(run(&[0xbf04,0xbf18]),Err(ContextError::NestedIt{address:0x1002}));
    for h in [0xbfe8,0xbff8]{assert_eq!(run(&[h]),Err(ContextError::UnsupportedIt{address:0x1000}));}
}
#[test]
fn known_control_flow_only_last(){
    for h in [0xe000,0x4770,0xbd00]{
        assert_eq!(run(&[0xbf04,h,0x2001]),Err(ContextError::ControlFlowBeforeLast{address:0x1002}));
        let (p,c)=run(&[0xbf08,h]).unwrap();assert!(p[1].last_in_it);assert_eq!(c.pending_condition(),None);
    }
}
#[test]
fn explicitly_conditional_branches_excluded_even_last(){
    assert_eq!(run(&[0xbf08,0xd000]),Err(ContextError::ConditionalBranchInIt{address:0x1002}));
    assert_eq!(run(&[0xbf08,0xf000,0x8000]),Err(ContextError::ConditionalBranchInIt{address:0x1002}));
}
#[test]
fn unknown_wide_consumes_slot_without_validation_claim(){
    let (p,c)=run(&[0xbf04,0xe800,0xbf08,0x2001]).unwrap();
    assert_eq!(p[1].instruction.op,Op::Unknown);assert_eq!(p[1].it_condition,Some(0));
    assert!(p[2].last_in_it);assert_eq!(c.pending_condition(),None);
}
