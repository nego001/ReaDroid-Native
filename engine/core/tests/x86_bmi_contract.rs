use negrodroid_core::x86_decode::{self,Mode,Op,Operand,BmiKind,BmiUnaryKind,CpuFeature,Base,Target,Stop};
fn one(mode:Mode,pc:u64,b:&[u8])->x86_decode::Instruction{
 let p=x86_decode::decode(mode,pc,b).unwrap();assert_eq!(p.stop,Stop::Complete,"{:x?}",b);assert_eq!(p.consumed,b.len());assert_eq!(p.instructions.len(),1);assert_eq!(p.instructions[0].bytes,b);p.instructions.into_iter().next().unwrap()
}
#[test] fn bmi_binary_matrix(){
 for (opcode,pp,kind,v_first,feature) in [(0xf2,0,BmiKind::AndNot,true,CpuFeature::Bmi1),(0xf7,0,BmiKind::Extract,false,CpuFeature::Bmi1),(0xf5,0,BmiKind::ZeroHigh,false,CpuFeature::Bmi2),(0xf5,3,BmiKind::Deposit,true,CpuFeature::Bmi2),(0xf5,2,BmiKind::ExtractParallel,true,CpuFeature::Bmi2),(0xf7,1,BmiKind::ShiftLeft,false,CpuFeature::Bmi2),(0xf7,3,BmiKind::ShiftRight,false,CpuFeature::Bmi2),(0xf7,2,BmiKind::ShiftArithmetic,false,CpuFeature::Bmi2)]{
  for (w,width) in [(0,32),(0x80,64)]{for d in 0..16u8{for v in 0..16u8{for rm in 0..16u8{
   let b=[0xc4,0xe2^((d>>3)<<7)^((rm>>3)<<5),w|((!v&15)<<3)|pp,opcode,0xc0|((d&7)<<3)|(rm&7)];
   let i=one(Mode::X64,0,&b);let (a,b)=if v_first{(v,rm)}else{(rm,v)};
   assert_eq!(i.op,Op::BmiBinary{kind,width,destination:d,source1:Operand::Register(a),source2:Operand::Register(b)});
   assert_eq!(i.bmi_feature(),Some(feature));assert_eq!(i.avx_feature(),None);
  }}}}
 }
}
#[test] fn unary_register_matrix(){
 for (g,kind) in [(1,BmiUnaryKind::ResetLowest),(2,BmiUnaryKind::MaskLowest),(3,BmiUnaryKind::IsolateLowest)]{for (w,width) in [(0,32),(0x80,64)]{for d in 0..16u8{for r in 0..16u8{
  let i=one(Mode::X64,0,&[0xc4,0xe2^((r>>3)<<5),w|((!d&15)<<3),0xf3,0xc0|(g<<3)|(r&7)]);
  assert_eq!(i.op,Op::BmiUnary{kind,width,destination:d,source:Operand::Register(r)});assert_eq!(i.bmi_feature(),Some(CpuFeature::Bmi1));
 }}}}
}
#[test] fn rotate_all_immediate_values(){
 for (w,width) in [(0,32),(0x80,64)]{for count in 0..=255u8{
  let i=one(Mode::X64,0,&[0xc4,0xe3,w|0x7b,0xf0,0xc1,count]);assert_eq!(i.op,Op::RotateRightImmediate{width,destination:0,source:Operand::Register(1),count});assert_eq!(i.bmi_feature(),Some(CpuFeature::Bmi2));
 }}
}
#[test] fn independent_assembler_binary(){
 for (b,kind,width,d,a,r) in [(&[0xc4,0x42,0x88,0xf2,0xfd][..],BmiKind::AndNot,64,15,14,13),(&[0xc4,0xe2,0xf0,0xf7,0xc3],BmiKind::Extract,64,0,3,1),(&[0xc4,0xe2,0x70,0xf5,0xc3],BmiKind::ZeroHigh,32,0,3,1),(&[0xc4,0xe2,0xe3,0xf5,0xc1],BmiKind::Deposit,64,0,3,1),(&[0xc4,0xe2,0xe2,0xf5,0xc1],BmiKind::ExtractParallel,64,0,3,1),(&[0xc4,0xe2,0xf1,0xf7,0xc3],BmiKind::ShiftLeft,64,0,3,1),(&[0xc4,0xe2,0xf3,0xf7,0xc3],BmiKind::ShiftRight,64,0,3,1),(&[0xc4,0xe2,0xf2,0xf7,0xc3],BmiKind::ShiftArithmetic,64,0,3,1)]{
  assert_eq!(one(Mode::X64,0,b).op,Op::BmiBinary{kind,width,destination:d,source1:Operand::Register(a),source2:Operand::Register(r)});
 }
}
#[test] fn independent_assembler_unary(){
 for (raw,kind) in [(0xca,BmiUnaryKind::ResetLowest),(0xd2,BmiUnaryKind::MaskLowest),(0xda,BmiUnaryKind::IsolateLowest)]{
  assert_eq!(one(Mode::X64,0,&[0xc4,0xc2,0xb0,0xf3,raw]).op,Op::BmiUnary{kind,width:64,destination:9,source:Operand::Register(10)});
 }
}
#[test] fn rotate_rip_uses_full_length(){
 let i=one(Mode::X64,0x1000,&[0xc4,0xe3,0xfb,0xf0,0x05,1,0,0,0,17]);assert!(matches!(i.op,Op::RotateRightImmediate{width:64,destination:0,source:Operand::Memory(m),count:17} if m.base==Base::Rip&&m.rip_target==Some(Target::Address(0x100b))));
}
#[test] fn legacy_memory_and_segment(){
 let i=one(Mode::X86,0,&[0x64,0x67,0xc4,0xe2,0x70,0xf7,0x00]);assert_eq!(i.address_width,16);assert!(i.segment_override.is_some());assert!(matches!(i.op,Op::BmiBinary{kind:BmiKind::Extract,source1:Operand::Memory(m),source2:Operand::Register(1),..} if m.base==Base::Register(3)&&m.index==Some(6)));
}
#[test] fn exclusions(){
 for (mode,b) in [(Mode::X64,&[0xc4,0xe2,0x74,0xf2,0xc0][..]),(Mode::X64,&[0xc4,0xe2,0x71,0xf2,0xc0]),(Mode::X64,&[0xc4,0x62,0x70,0xf3,0xc8]),(Mode::X64,&[0xc4,0xe2,0x70,0xf3,0xc0]),(Mode::X64,&[0xc4,0xe3,0x73,0xf0,0xc0,1]),(Mode::X64,&[0xc4,0xe3,0x7f,0xf0,0xc0,1]),(Mode::X86,&[0xc4,0xe2,0xf0,0xf7,0xc3]),(Mode::X64,&[0x64,0xc4,0xe2,0x70,0xf7,0xc3]),(Mode::X64,&[0xf0,0xc4,0xe2,0x70,0xf7,0x03])]{let p=x86_decode::decode(mode,0,b).unwrap();assert_eq!(p.stop,Stop::Unsupported{offset:0},"{:x?}",b);}
}
#[test] fn truncate_every_boundary(){
 for b in [&[0xc4,0xe3,0xfb,0xf0,0x05,1,0,0,0,17][..],&[0xc4,0xe2,0x70,0xf7,0x44,0x24,0xff],&[0xc4,0xc2,0xb0,0xf3,0xca]]{for n in 1..b.len(){let p=x86_decode::decode(Mode::X64,0,&b[..n]).unwrap();assert_eq!(p.stop,Stop::Truncated{offset:0},"{:x?}",&b[..n]);}}
}
#[test] fn feature_state(){
 let p=x86_decode::decode(Mode::X64,0,&[0xc4,0xe2,0x70,0xf7,0xc3,0xc4,0xe3,0x7b,0xf0,0xc1,7,0xc5,0xfc,0x58,0xc0,0x90]).unwrap();assert_eq!(p.stop,Stop::Complete);assert_eq!(p.instructions.iter().map(|i|i.bmi_feature()).collect::<Vec<_>>(),[Some(CpuFeature::Bmi1),Some(CpuFeature::Bmi2),None,None]);assert_eq!(p.instructions[2].avx_feature(),Some(CpuFeature::Avx));
}
