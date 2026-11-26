use negrodroid_core::x86_decode::{self,Mode,Op,Operand,Base,Target,Stop,Segment};
fn one(mode:Mode,pc:u64,b:&[u8],width:u8,segment:Option<Segment>)->Op{
    let p=x86_decode::decode(mode,pc,b).unwrap();assert_eq!(p.stop,Stop::Complete);assert_eq!(p.consumed,b.len());assert_eq!(p.instructions.len(),1);assert_eq!(p.instructions[0].bytes,b);assert_eq!(p.instructions[0].address_width,width);assert_eq!(p.instructions[0].segment_override,segment);p.instructions[0].op
}
#[test] fn all_six_segments_in_legacy_mode(){
    for (prefix,seg) in [(0x26,Segment::Es),(0x2e,Segment::Cs),(0x36,Segment::Ss),(0x3e,Segment::Ds),(0x64,Segment::Fs),(0x65,Segment::Gs)]{
        for form in 0..3u8{for r in 0..8u8{for reg in 0..8u8{
            let mut b=vec![prefix,0x8b,(form<<6)|(reg<<3)|r];
            if r==4{b.push(0x24);}
            if form==2||form==0&&r==5{b.extend([0,0,0,0]);}else if form==1{b.push(0);}
            assert!(matches!(one(Mode::X86,0,&b,32,Some(seg)),Op::Binary{source:Operand::Memory(_),..}));
        }}}
    }
}
#[test] fn fs_gs_and_rex_in_long_mode(){
    for (prefix,seg) in [(0x64,Segment::Fs),(0x65,Segment::Gs)]{
        assert!(matches!(one(Mode::X64,0,&[prefix,0x4d,0x8b,0x01],64,Some(seg)),Op::Binary{width:64,destination:Operand::Register(8),source:Operand::Memory(m),..} if m.base==Base::Register(9)));
    }
}
#[test] fn segment_and_width_prefix_permutations(){
    for p in [[0x64,0x66,0x67],[0x64,0x67,0x66],[0x66,0x64,0x67],[0x66,0x67,0x64],[0x67,0x64,0x66],[0x67,0x66,0x64]]{
        let mut b=p.to_vec();b.extend([0x8b,0x00]);
        assert!(matches!(one(Mode::X86,0,&b,16,Some(Segment::Fs)),Op::Binary{width:16,source:Operand::Memory(m),..} if m.base==Base::Register(3)&&m.index==Some(6)));
    }
}
#[test] fn fs_rip_offset_is_not_linear_address(){
    assert!(matches!(one(Mode::X64,0x1000,&[0x64,0x48,0x8b,0x05,0,0,0,0],64,Some(Segment::Fs)),Op::Binary{source:Operand::Memory(m),..} if m.base==Base::Rip&&m.rip_target==Some(Target::Address(0x1008))));
}
#[test] fn gs_eip_immediate_includes_all_prefixes(){
    assert!(matches!(one(Mode::X64,0x1_0000_1000,&[0x65,0x67,0x83,0x05,0,0,0,0,1],32,Some(Segment::Gs)),Op::BinaryImmediate{operand:Operand::Memory(m),..} if m.base==Base::Eip&&m.rip_target==Some(Target::Address(0x1009))));
}
#[test] fn memory_destination_and_extended_map(){
    assert!(matches!(one(Mode::X64,0,&[0x64,0x89,0x00],64,Some(Segment::Fs)),Op::Binary{destination:Operand::Memory(_),..}));
    assert!(matches!(one(Mode::X64,0,&[0x65,0x0f,0xb6,0x00],64,Some(Segment::Gs)),Op::ExtendMove{source:Operand::Memory(_),..}));
}
#[test] fn no_segment_state_leaks_to_following_instruction(){
    let p=x86_decode::decode(Mode::X64,0,&[0x64,0x8b,0x00,0x8b,0x00,0x90]).unwrap();
    assert_eq!(p.stop,Stop::Complete);assert_eq!(p.instructions.iter().map(|x|x.segment_override).collect::<Vec<_>>(),[Some(Segment::Fs),None,None]);
}
#[test] fn all_truncation_boundaries(){
    let b=[0x65,0x67,0x48,0x69,0x05,0,0,0,0,1,2,3,4];
    for n in 1..b.len(){let p=x86_decode::decode(Mode::X64,0,&b[..n]).unwrap();assert_eq!(p.stop,Stop::Truncated{offset:0});assert!(p.instructions.is_empty());}
}
#[test] fn excluded_segments_and_forms(){
    for b in [&[0x26,0x8b,0x00][..],&[0x2e,0x8b,0x00],&[0x36,0x8b,0x00],&[0x3e,0x8b,0x00],&[0x64,0x65,0x8b,0x00],&[0x64,0x64,0x8b,0x00],&[0x64,0x8b,0xc0],&[0x64,0x8d,0x00],&[0x64,0x90],&[0x48,0x64,0x8b,0x00],&[0x64,0xf3,0x90]]{
        let mut stream=vec![0x90];stream.extend(b);let p=x86_decode::decode(Mode::X64,0,&stream).unwrap();assert_eq!(p.stop,Stop::Unsupported{offset:1});assert_eq!(p.consumed,1);
    }
}
#[test] fn unprefixed_memory_metadata_unchanged(){
    assert!(matches!(one(Mode::X64,0,&[0x8b,0x00],64,None),Op::Binary{source:Operand::Memory(_),..}));
}
