use negrodroid_core::x86_decode::{self,Mode,Op,Operand,Base,Target,Stop,Segment,CountKind,CpuFeature,WithoutFeature,FeatureRequirement,Repeat,StringKind,LockKind};
fn one(mode:Mode,pc:u64,b:&[u8])->x86_decode::Instruction{
 let p=x86_decode::decode(mode,pc,b).unwrap();assert_eq!(p.stop,Stop::Complete);assert_eq!(p.consumed,b.len());assert_eq!(p.instructions.len(),1);assert_eq!(p.instructions[0].bytes,b);p.instructions.into_iter().next().unwrap()
}
#[test] fn count_register_matrix(){
 for (opcode,kind) in [(0xb8,CountKind::Population),(0xbc,CountKind::TrailingZeros),(0xbd,CountKind::LeadingZeros)]{
  for dst in 0..16u8{for src in 0..16u8{
   let rex=0x48|((dst>>3)<<2)|(src>>3);
   assert_eq!(one(Mode::X64,0,&[0xf3,rex,0x0f,opcode,0xc0|((dst&7)<<3)|(src&7)]).op,Op::CountBits{kind,width:64,destination:dst,source:Operand::Register(src)});
  }}
 }
}
#[test] fn count_widths_and_prefix_order(){
 for (opcode,kind) in [(0xb8,CountKind::Population),(0xbc,CountKind::TrailingZeros),(0xbd,CountKind::LeadingZeros)]{
  for (mode,pre,width) in [(Mode::X86,&[0xf3][..],32),(Mode::X64,&[0xf3][..],32),(Mode::X86,&[0x66,0xf3][..],16),(Mode::X64,&[0xf3,0x66][..],16),(Mode::X64,&[0x66,0xf3,0x48][..],64)]{
   let mut b=pre.to_vec();b.extend([0x0f,opcode,0xc1]);assert_eq!(one(mode,0,&b).op,Op::CountBits{kind,width,destination:0,source:Operand::Register(1)});
  }
 }
}
#[test] fn feature_requirements_and_fallbacks(){
 for (opcode,feature,without) in [(0xb8,CpuFeature::Popcnt,WithoutFeature::InvalidOpcode),(0xbc,CpuFeature::Bmi1,WithoutFeature::BitScan{reverse:false}),(0xbd,CpuFeature::Lzcnt,WithoutFeature::BitScan{reverse:true})]{
  assert_eq!(one(Mode::X64,0,&[0xf3,0x0f,opcode,0xc0]).count_feature(),Some(FeatureRequirement{feature,without}));
 }
}
#[test] fn unprefixed_scan_not_count(){
 for (opcode,reverse) in [(0xbc,false),(0xbd,true)]{
  let i=one(Mode::X64,0,&[0x0f,opcode,0xc1]);assert_eq!(i.count_feature(),None);assert_eq!(i.op,Op::BitScan{reverse,width:32,destination:0,source:Operand::Register(1)});
 }
 assert_eq!(x86_decode::decode(Mode::X64,0,&[0x0f,0xb8,0xc1]).unwrap().stop,Stop::Unsupported{offset:0});
}
#[test] fn count_memory_relative_and_segment(){
 let i=one(Mode::X64,0x1000,&[0x64,0xf3,0x48,0x0f,0xb8,0x05,0,0,0,0]);assert_eq!(i.segment_override,Some(Segment::Fs));assert!(matches!(i.op,Op::CountBits{width:64,source:Operand::Memory(m),..} if m.base==Base::Rip&&m.rip_target==Some(Target::Address(0x100a))));
 let i=one(Mode::X86,0,&[0xf3,0x67,0x0f,0xbc,0x00]);assert_eq!(i.address_width,16);assert!(matches!(i.op,Op::CountBits{source:Operand::Memory(m),..} if m.base==Base::Register(3)&&m.index==Some(6)));
}
#[test] fn count_eip_relative(){
 let i=one(Mode::X64,0x1_0000_1000,&[0xf3,0x67,0x0f,0xbd,0x05,0,0,0,0]);assert_eq!(i.address_width,32);assert!(matches!(i.op,Op::CountBits{source:Operand::Memory(m),..} if m.base==Base::Eip&&m.rip_target==Some(Target::Address(0x1009))));
}
#[test] fn canonical_pause_is_not_rep_or_nop(){
 for mode in [Mode::X86,Mode::X64]{let i=one(mode,0,&[0xf3,0x90]);assert_eq!(i.op,Op::Pause);assert_eq!(i.count_feature(),None);assert_eq!(i.lock_kind(),LockKind::None);assert_eq!(one(mode,0,&[0x90]).op,Op::Nop);}
}
#[test] fn prefix_class_exclusions(){
 for b in [&[0xf2,0x0f,0xb8,0xc0][..],&[0xf0,0x0f,0xb8,0x00],&[0xf3,0xf0,0x0f,0xbc,0],&[0xf3,0xf3,0x90],&[0xf3,0x41,0x90],&[0xf3,0x66,0x90],&[0x64,0xf3,0x90],&[0x64,0xf3,0x0f,0xbc,0xc0],&[0x67,0xf3,0x0f,0xbd,0xc0],&[0xf3,0x0f,0x2a,0xc0]]{
  let mut stream=vec![0x90];stream.extend(b);let p=x86_decode::decode(Mode::X64,0,&stream).unwrap();assert_eq!(p.stop,Stop::Unsupported{offset:1});assert_eq!(p.consumed,1);
 }
}
#[test] fn truncation_at_every_boundary(){
 for b in [&[0xf3,0x90][..],&[0x64,0xf3,0x48,0x0f,0xb8,0x05,0,0,0,0],&[0xf3,0x67,0x0f,0xbd,0x44,0x24,0xff]]{
  for n in 1..b.len(){let p=x86_decode::decode(Mode::X64,0,&b[..n]).unwrap();assert_eq!(p.stop,Stop::Truncated{offset:0});assert_eq!(p.consumed,0);}
 }
}
#[test] fn prefix_state_does_not_leak(){
 let p=x86_decode::decode(Mode::X64,0,&[0xf3,0x90,0xf3,0xa4,0xf3,0x0f,0xbc,0xc0,0x0f,0xbc,0xc0,0x90]).unwrap();assert_eq!(p.stop,Stop::Complete);assert_eq!(p.instructions.len(),5);assert_eq!(p.instructions[0].op,Op::Pause);assert_eq!(p.instructions[1].op,Op::String{kind:StringKind::Movs,width:8,repeat:Repeat::Rep});assert!(p.instructions[2].count_feature().is_some());assert!(p.instructions[3].count_feature().is_none());assert_eq!(p.instructions[4].op,Op::Nop);
}
