use negrodroid_core::x86_decode::{self,Mode,Op,XmmOperand,FloatFormat,HorizontalKind,ExtendedPackedKind,RoundFormat,CpuFeature,Base,Target,Segment,Stop};
fn one(mode:Mode,pc:u64,b:&[u8])->x86_decode::Instruction{
 let p=x86_decode::decode(mode,pc,b).unwrap();assert_eq!(p.stop,Stop::Complete,"{:x?}",b);assert_eq!(p.consumed,b.len());assert_eq!(p.instructions.len(),1);assert_eq!(p.instructions[0].bytes,b);p.instructions.into_iter().next().unwrap()
}
#[test] fn sse3_horizontal_register_matrix(){
 for (opcode,kind) in [(0x7c,HorizontalKind::Add),(0x7d,HorizontalKind::Sub),(0xd0,HorizontalKind::AddSub)]{
  for (prefix,format) in [(0x66,FloatFormat::PackedDouble),(0xf2,FloatFormat::PackedSingle)]{for dst in 0..16u8{for src in 0..16u8{
   let b=[prefix,0x40|((dst>>3)<<2)|(src>>3),0x0f,opcode,0xc0|((dst&7)<<3)|(src&7)];
   let i=one(Mode::X64,0,&b);assert_eq!(i.sse_feature(),Some(CpuFeature::Sse3));assert_eq!(i.op,Op::HorizontalFloat{kind,format,destination:XmmOperand::Register(dst),source:XmmOperand::Register(src)});
  }}}
 }
}
#[test] fn extended_packed_register_matrix(){
 use ExtendedPackedKind::*;
 for (opcode,kind,lane_bits,feature) in [(0x00,ShuffleBytes,Some(8),CpuFeature::Ssse3),(0x01,HorizontalAdd,Some(16),CpuFeature::Ssse3),(0x02,HorizontalAdd,Some(32),CpuFeature::Ssse3),(0x05,HorizontalSub,Some(16),CpuFeature::Ssse3),(0x06,HorizontalSub,Some(32),CpuFeature::Ssse3),(0x1c,Abs,Some(8),CpuFeature::Ssse3),(0x1d,Abs,Some(16),CpuFeature::Ssse3),(0x1e,Abs,Some(32),CpuFeature::Ssse3),(0x17,Test,None,CpuFeature::Sse41),(0x29,Equal,Some(64),CpuFeature::Sse41),(0x40,MultiplyLow,Some(32),CpuFeature::Sse41),(0x37,GreaterSigned,Some(64),CpuFeature::Sse42)]{
  for dst in 0..16u8{for src in 0..16u8{
   let b=[0x66,0x40|((dst>>3)<<2)|(src>>3),0x0f,0x38,opcode,0xc0|((dst&7)<<3)|(src&7)];
   let i=one(Mode::X64,0,&b);assert_eq!(i.sse_feature(),Some(feature));assert_eq!(i.op,Op::ExtendedPacked{kind,lane_bits,feature,destination:XmmOperand::Register(dst),source:XmmOperand::Register(src)});
  }}
 }
}
#[test] fn round_control_all_values(){
 for (opcode,format) in [(8,RoundFormat::PackedSingle),(9,RoundFormat::PackedDouble),(10,RoundFormat::ScalarSingle),(11,RoundFormat::ScalarDouble)]{
  for control in 0..=255u8{let i=one(Mode::X86,0,&[0x66,0x0f,0x3a,opcode,0xc1,control]);assert_eq!(i.sse_feature(),Some(CpuFeature::Sse41));assert_eq!(i.op,Op::RoundFloat{format,destination:XmmOperand::Register(0),source:XmmOperand::Register(1),control});}
 }
}
#[test] fn round_rip_includes_control(){
 let i=one(Mode::X64,0x1000,&[0x66,0x44,0x0f,0x3a,0x0a,0x05,0,0,0,0,3]);
 assert!(matches!(i.op,Op::RoundFloat{format:RoundFormat::ScalarSingle,destination:XmmOperand::Register(8),source:XmmOperand::Memory(m),control:3} if m.base==Base::Rip&&m.rip_target==Some(Target::Address(0x100b))));
}
#[test] fn round_eip_includes_control(){
 let i=one(Mode::X64,0x1_0000_1000,&[0x67,0x66,0x0f,0x3a,0x09,0x05,0,0,0,0,4]);assert_eq!(i.address_width,32);assert!(matches!(i.op,Op::RoundFloat{source:XmmOperand::Memory(m),control:4,..} if m.base==Base::Eip&&m.rip_target==Some(Target::Address(0x100b))));
}
#[test] fn extended_memory_legacy_segment(){
 let i=one(Mode::X86,0,&[0x64,0x67,0x66,0x0f,0x38,0x37,0]);assert_eq!(i.segment_override,Some(Segment::Fs));assert_eq!(i.address_width,16);assert!(matches!(i.op,Op::ExtendedPacked{kind:ExtendedPackedKind::GreaterSigned,lane_bits:Some(64),source:XmmOperand::Memory(m),..} if m.base==Base::Register(3)&&m.index==Some(6)));
}
#[test] fn horizontal_memory_relative(){
 let i=one(Mode::X64,0x1000,&[0xf2,0x0f,0x7c,0x05,0,0,0,0]);assert!(matches!(i.op,Op::HorizontalFloat{format:FloatFormat::PackedSingle,source:XmmOperand::Memory(m),..} if m.rip_target==Some(Target::Address(0x1008))));
}
#[test] fn excluded_maps_and_prefixes(){
 for b in [&[0x0f,0x38,0x00,0xc0][..],&[0xf2,0x0f,0x38,0xf0,0xc0],&[0x66,0x0f,0x38,0xff,0xc0],&[0x66,0x0f,0x3a,0xff,0xc0,0],&[0x66,0x48,0x0f,0x38,0x00,0xc0],&[0xf0,0x66,0x0f,0x38,0x00,0],&[0xf3,0x0f,0x7c,0xc0],&[0x66,0xf2,0x0f,0x7c,0xc0],&[0x64,0x66,0x0f,0x38,0x00,0xc0],&[0x67,0x66,0x0f,0x3a,0x08,0xc0,0]]{
  let mut stream=vec![0x90];stream.extend(b);let p=x86_decode::decode(Mode::X64,0,&stream).unwrap();assert_eq!(p.stop,Stop::Unsupported{offset:1},"{:x?}",b);assert_eq!(p.consumed,1);
 }
}
#[test] fn truncate_every_boundary(){
 for b in [&[0x64,0x66,0x0f,0x38,0x00,0x05,0,0,0,0][..],&[0x66,0x44,0x0f,0x3a,0x0a,0x05,0,0,0,0,3],&[0xf2,0x0f,0x7c,0x44,0x24,0xff]]{for n in 1..b.len(){let p=x86_decode::decode(Mode::X64,0,&b[..n]).unwrap();assert_eq!(p.stop,Stop::Truncated{offset:0},"{:x?}",&b[..n]);assert_eq!(p.consumed,0);}}
}
#[test] fn feature_state_is_local(){
 let p=x86_decode::decode(Mode::X64,0,&[0x66,0x0f,0x7c,0xc0,0x66,0x0f,0x38,0x00,0xc0,0x66,0x0f,0x3a,0x08,0xc0,0,0x66,0x0f,0x38,0x37,0xc0,0x90]).unwrap();assert_eq!(p.stop,Stop::Complete);assert_eq!(p.instructions.iter().map(|i|i.sse_feature()).collect::<Vec<_>>(),[Some(CpuFeature::Sse3),Some(CpuFeature::Ssse3),Some(CpuFeature::Sse41),Some(CpuFeature::Sse42),None]);
}
