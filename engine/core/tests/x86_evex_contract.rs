use negrodroid_core::x86_decode::{self,Mode,Op,VectorOperand,VectorWidth,WriteMask,FloatFormat,SseKind,CpuFeature,Base,Target,Segment,Stop};
fn one(pc:u64,b:&[u8])->x86_decode::Instruction{
 let p=x86_decode::decode(Mode::X64,pc,b).unwrap();assert_eq!(p.stop,Stop::Complete,"{:x?}",b);assert_eq!(p.consumed,b.len());assert_eq!(p.instructions.len(),1);assert_eq!(p.instructions[0].bytes,b);p.instructions.into_iter().next().unwrap()
}
#[test] fn all_zmm_register_combinations(){
 for (opcode,kind) in [(0x58,SseKind::Add),(0x59,SseKind::Mul),(0x5c,SseKind::Sub),(0x5e,SseKind::Div)]{
  for dst in 0..32u8{for src1 in 0..32u8{for src2 in 0..32u8{
   let p0=0xf1^(((dst>>3)&1)<<7)^(((dst>>4)&1)<<4)^(((src2>>3)&1)<<5)^(((src2>>4)&1)<<6);
   let p1=((!src1&15)<<3)|4;let p2=0x40|((!(src1>>4)&1)<<3);
   let b=[0x62,p0,p1,p2,opcode,0xc0|((dst&7)<<3)|(src2&7)];
   let i=one(0,&b);assert_eq!(i.avx_feature(),Some(CpuFeature::Avx512F));assert_eq!(i.op,Op::EvexFloat{kind,format:FloatFormat::PackedSingle,width:VectorWidth::Bits512,destination:VectorOperand::Register(dst),source1:Some(src1),source2:VectorOperand::Register(src2),mask:WriteMask::None});
  }}}
 }
}
#[test] fn independent_assembler_fixtures(){
 for (b,dst,src1,src2,mask) in [(&[0x62,0x11,0x7c,0x40,0x58,0xc0][..],8,16,24,WriteMask::None),(&[0x62,0xe1,0x3c,0x48,0x58,0xc1][..],16,8,1,WriteMask::None),(&[0x62,0x01,0x0c,0xc7,0x58,0xfd][..],31,30,29,WriteMask::Zero(7))]{
  assert_eq!(one(0,b).op,Op::EvexFloat{kind:SseKind::Add,format:FloatFormat::PackedSingle,width:VectorWidth::Bits512,destination:VectorOperand::Register(dst),source1:Some(src1),source2:VectorOperand::Register(src2),mask});
 }
}
#[test] fn mask_all_registers(){
 for k in 1..8u8{for (z,mask) in [(0,WriteMask::Merge(k)),(0x80,WriteMask::Zero(k))]{assert!(matches!(one(0,&[0x62,0xf1,0x7c,0x48|z|k,0x58,0xc0]).op,Op::EvexFloat{mask:m,..} if m==mask));}}
}
#[test] fn compressed_displacement_every_value(){
 for disp in 0..=255u8{
  let i=one(0,&[0x62,0xd1,0xed,0x4a,0x58,0x49,disp]);
  assert!(matches!(i.op,Op::EvexFloat{format:FloatFormat::PackedDouble,mask:WriteMask::Merge(2),destination:VectorOperand::Register(1),source1:Some(2),source2:VectorOperand::Memory(m),..} if m.base==Base::Register(9)&&m.displacement==i64::from(disp as i8)*64));
 }
}
#[test] fn disp32_not_scaled_and_rip(){
 let i=one(0x1000,&[0x62,0xf1,0x7c,0x48,0x58,0x05,1,0,0,0]);assert!(matches!(i.op,Op::EvexFloat{source2:VectorOperand::Memory(m),..} if m.base==Base::Rip&&m.displacement==1&&m.rip_target==Some(Target::Address(0x100b))));
 let i=one(0,&[0x62,0xf1,0x7c,0x48,0x58,0x80,1,0,0,0]);assert!(matches!(i.op,Op::EvexFloat{source2:VectorOperand::Memory(m),..} if m.displacement==1));
}
#[test] fn eip_and_segment(){
 let i=one(0x1_0000_1000,&[0x64,0x67,0x62,0xf1,0x7c,0x48,0x58,0x05,0,0,0,0]);assert_eq!(i.address_width,32);assert_eq!(i.segment_override,Some(Segment::Fs));assert!(matches!(i.op,Op::EvexFloat{source2:VectorOperand::Memory(m),..} if m.base==Base::Eip&&m.rip_target==Some(Target::Address(0x100c))));
}
#[test] fn masked_store_and_sqrt(){
 let i=one(0,&[0x62,0xe1,0x7c,0x49,0x11,0x40,1]);assert!(matches!(i.op,Op::EvexFloat{kind:SseKind::MoveUnaligned,destination:VectorOperand::Memory(m),source1:None,source2:VectorOperand::Register(16),mask:WriteMask::Merge(1),..} if m.displacement==64));
 assert!(matches!(one(0,&[0x62,0xf1,0xfd,0x48,0x51,0xc1]).op,Op::EvexFloat{kind:SseKind::Sqrt,format:FloatFormat::PackedDouble,source1:None,..}));
}
#[test] fn excluded_forms_stop(){
 for b in [&[0x62,0xf1,0x7c,0x58,0x58,0xc0][..],&[0x62,0xf1,0x7c,0x28,0x58,0xc0],&[0x62,0xf1,0x7c,0xc8,0x58,0xc0],&[0x62,0xf1,0x7c,0xc9,0x11,0x00],&[0x62,0xf1,0x74,0x48,0x10,0xc0],&[0x62,0xf1,0x7c,0x40,0x10,0xc0],&[0x62,0xf1,0x7c,0x48,0x54,0xc0],&[0x62,0xf1,0x78,0x48,0x58,0xc0],&[0x62,0xf1,0x7d,0x48,0x58,0xc0],&[0x62,0xf2,0x7c,0x48,0x58,0xc0],&[0x66,0x62,0xf1,0x7c,0x48,0x58,0xc0],&[0x64,0x62,0xf1,0x7c,0x48,0x58,0xc0]]{
  let mut stream=vec![0x90];stream.extend(b);let p=x86_decode::decode(Mode::X64,0,&stream).unwrap();assert_eq!(p.stop,Stop::Unsupported{offset:1},"{:x?}",b);assert_eq!(p.consumed,1);
 }
 assert_eq!(x86_decode::decode(Mode::X86,0,&[0x62,0xf1,0x7c,0x48,0x58,0xc0]).unwrap().stop,Stop::Unsupported{offset:0});
}
#[test] fn truncate_all_boundaries(){
 for b in [&[0x62,0xf1,0x7c,0x48,0x58,0xc0][..],&[0x64,0x67,0x62,0xf1,0x7c,0x48,0x58,0x05,0,0,0,0],&[0x62,0xd1,0xed,0x4a,0x58,0x49,1]]{
  for n in 1..b.len(){let p=x86_decode::decode(Mode::X64,0,&b[..n]).unwrap();assert_eq!(p.stop,Stop::Truncated{offset:0},"{:x?}",&b[..n]);assert_eq!(p.consumed,0);}
 }
}
#[test] fn mixed_avx_feature_state(){
 let p=x86_decode::decode(Mode::X64,0,&[0x62,0xf1,0x7c,0x49,0x58,0xc0,0xc5,0xfd,0xfc,0xc0,0xc5,0xfc,0x58,0xc0,0x90]).unwrap();assert_eq!(p.stop,Stop::Complete);assert_eq!(p.instructions.iter().map(|i|i.avx_feature()).collect::<Vec<_>>(),[Some(CpuFeature::Avx512F),Some(CpuFeature::Avx2),Some(CpuFeature::Avx),None]);
}
