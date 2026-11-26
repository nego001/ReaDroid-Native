use negrodroid_core::x86_decode::{self,Mode,Op,XmmOperand,Base,Target,Stop,Segment,FloatFormat,SseKind,CpuFeature,LockKind};
fn one(mode:Mode,pc:u64,b:&[u8])->x86_decode::Instruction{
 let p=x86_decode::decode(mode,pc,b).unwrap();assert_eq!(p.stop,Stop::Complete);assert_eq!(p.consumed,b.len());assert_eq!(p.instructions.len(),1);assert_eq!(p.instructions[0].bytes,b);p.instructions.into_iter().next().unwrap()
}
#[test] fn arithmetic_register_matrix(){
 for (op,kind) in [(0x51,SseKind::Sqrt),(0x58,SseKind::Add),(0x59,SseKind::Mul),(0x5c,SseKind::Sub),(0x5d,SseKind::Min),(0x5e,SseKind::Div),(0x5f,SseKind::Max)]{
  for (pre,format) in [(&[][..],FloatFormat::PackedSingle),(&[0x66][..],FloatFormat::PackedDouble),(&[0xf3][..],FloatFormat::ScalarSingle),(&[0xf2][..],FloatFormat::ScalarDouble)]{
   for dst in 0..16u8{for src in 0..16u8{
    let mut b=pre.to_vec();b.extend([0x40|((dst>>3)<<2)|(src>>3),0x0f,op,0xc0|((dst&7)<<3)|(src&7)]);
    assert_eq!(one(Mode::X64,0,&b).op,Op::Sse{kind,format,destination:XmmOperand::Register(dst),source:XmmOperand::Register(src)});
   }}
  }
 }
}
#[test] fn move_direction_and_format(){
 for (prefix,format) in [(&[][..],FloatFormat::PackedSingle),(&[0x66][..],FloatFormat::PackedDouble),(&[0xf3][..],FloatFormat::ScalarSingle),(&[0xf2][..],FloatFormat::ScalarDouble)]{
  for opcode in [0x10,0x11]{let mut b=prefix.to_vec();b.extend([0x0f,opcode,0xc1]);let (destination,source)=if opcode==0x10{(0,1)}else{(1,0)};assert_eq!(one(Mode::X86,0,&b).op,Op::Sse{kind:SseKind::MoveUnaligned,format,destination:XmmOperand::Register(destination),source:XmmOperand::Register(source)});}
 }
}
#[test] fn aligned_move_memory_directions(){
 for (pre,format) in [(&[][..],FloatFormat::PackedSingle),(&[0x66][..],FloatFormat::PackedDouble)]{
  for op in [0x28,0x29]{let mut b=pre.to_vec();b.extend([0x0f,op,0x08]);let i=one(Mode::X64,0,&b);assert!(match i.op{Op::Sse{kind:SseKind::MoveAligned,format:f,destination:XmmOperand::Register(1),source:XmmOperand::Memory(m)} if op==0x28=>f==format&&m.base==Base::Register(0),Op::Sse{kind:SseKind::MoveAligned,format:f,destination:XmmOperand::Memory(m),source:XmmOperand::Register(1)} if op==0x29=>f==format&&m.base==Base::Register(0),_=>false});}
 }
}
#[test] fn packed_logic_only(){
 for (op,kind) in [(0x54,SseKind::And),(0x55,SseKind::AndNot),(0x56,SseKind::Or),(0x57,SseKind::Xor)]{
  for (prefix,format) in [(&[][..],FloatFormat::PackedSingle),(&[0x66][..],FloatFormat::PackedDouble)]{let mut b=prefix.to_vec();b.extend([0x0f,op,0xc1]);assert_eq!(one(Mode::X86,0,&b).op,Op::Sse{kind,format,destination:XmmOperand::Register(0),source:XmmOperand::Register(1)});}
 }
}
#[test] fn feature_metadata(){
 for (prefix,feature) in [(&[][..],CpuFeature::Sse),(&[0xf3][..],CpuFeature::Sse),(&[0x66][..],CpuFeature::Sse2),(&[0xf2][..],CpuFeature::Sse2)]{let mut b=prefix.to_vec();b.extend([0x0f,0x58,0xc0]);let i=one(Mode::X64,0,&b);assert_eq!(i.sse_feature(),Some(feature));assert_eq!(i.count_feature(),None);assert_eq!(i.lock_kind(),LockKind::None);}
 assert_eq!(one(Mode::X64,0,&[0x90]).sse_feature(),None);
}
#[test] fn rip_memory_and_segment(){
 let i=one(Mode::X64,0x1000,&[0x64,0xf3,0x44,0x0f,0x58,0x05,0,0,0,0]);assert_eq!(i.segment_override,Some(Segment::Fs));assert!(matches!(i.op,Op::Sse{format:FloatFormat::ScalarSingle,destination:XmmOperand::Register(8),source:XmmOperand::Memory(m),..} if m.base==Base::Rip&&m.rip_target==Some(Target::Address(0x100a))));
}
#[test] fn eip_and_legacy_address_size(){
 let i=one(Mode::X64,0x1_0000_1000,&[0xf2,0x67,0x0f,0x11,0x05,0,0,0,0]);assert_eq!(i.address_width,32);assert!(matches!(i.op,Op::Sse{format:FloatFormat::ScalarDouble,destination:XmmOperand::Memory(m),source:XmmOperand::Register(0),..} if m.base==Base::Eip&&m.rip_target==Some(Target::Address(0x1009))));
 let i=one(Mode::X86,0,&[0x67,0x66,0x0f,0x58,0x00]);assert_eq!(i.address_width,16);assert!(matches!(i.op,Op::Sse{source:XmmOperand::Memory(m),..} if m.base==Base::Register(3)&&m.index==Some(6)));
}
#[test] fn incompatible_prefixes_stop(){
 for b in [&[0xf0,0x0f,0x58,0x00][..],&[0x66,0xf3,0x0f,0x58,0xc0],&[0xf2,0xf3,0x0f,0x58,0xc0],&[0xf3,0x0f,0x28,0xc0],&[0xf2,0x0f,0x54,0xc0],&[0x48,0x0f,0x58,0xc0],&[0x64,0x0f,0x58,0xc0],&[0x67,0x0f,0x58,0xc0],&[0xf3,0x0f,0x2a,0xc0],&[0xc5,0xf8,0x58,0xc0]]{
  let mut stream=vec![0x90];stream.extend(b);let p=x86_decode::decode(Mode::X64,0,&stream).unwrap();assert_eq!(p.stop,Stop::Unsupported{offset:1});assert_eq!(p.consumed,1);
 }
}
#[test] fn truncated_sse_forms(){
 for b in [&[0x64,0xf3,0x44,0x0f,0x58,0x05,0,0,0,0][..],&[0x66,0x0f,0x29,0x44,0x24,0xff],&[0x0f,0x51,0xc0]]{for n in 1..b.len(){let p=x86_decode::decode(Mode::X64,0,&b[..n]).unwrap();assert_eq!(p.stop,Stop::Truncated{offset:0});assert_eq!(p.consumed,0);}}
}
#[test] fn independent_prefix_classes(){
 let p=x86_decode::decode(Mode::X64,0,&[0xf3,0x0f,0x58,0xc0,0xf3,0x0f,0xb8,0xc0,0xf3,0x90,0x0f,0x58,0xc0]).unwrap();
 assert_eq!(p.stop,Stop::Complete);assert_eq!(p.instructions.len(),4);assert_eq!(p.instructions[0].sse_feature(),Some(CpuFeature::Sse));assert!(p.instructions[1].count_feature().is_some());assert_eq!(p.instructions[2].op,Op::Pause);assert!(matches!(p.instructions[3].op,Op::Sse{format:FloatFormat::PackedSingle,..}));
}
