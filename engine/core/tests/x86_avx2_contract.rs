use negrodroid_core::x86_decode::{self,Mode,Op,VectorOperand,VectorWidth,AvxIntegerKind,PackedKind,ExtendedPackedKind,CpuFeature,Base,Target,Segment,Stop};
fn one(mode:Mode,pc:u64,b:&[u8])->x86_decode::Instruction{
 let p=x86_decode::decode(mode,pc,b).unwrap();assert_eq!(p.stop,Stop::Complete,"{:x?}",b);assert_eq!(p.consumed,b.len());assert_eq!(p.instructions.len(),1);assert_eq!(p.instructions[0].bytes,b);p.instructions.into_iter().next().unwrap()
}
#[test] fn packed_three_register_matrix(){
 for (op,kind,lane_bits) in [(0xfc,PackedKind::Add,Some(8)),(0xd4,PackedKind::Add,Some(64)),(0xfa,PackedKind::Sub,Some(32)),(0xef,PackedKind::Xor,None)]{
  for (l,width,feature) in [(0,VectorWidth::Bits128,CpuFeature::Avx),(4,VectorWidth::Bits256,CpuFeature::Avx2)]{for dst in 0..16u8{for src1 in 0..16u8{for src2 in 0..16u8{
   let b=[0xc4,0xe1^((dst>>3)<<7)^((src2>>3)<<5),((!src1&15)<<3)|l|1,op,0xc0|((dst&7)<<3)|(src2&7)];
   let i=one(Mode::X64,0,&b);assert_eq!(i.avx_feature(),Some(feature));assert_eq!(i.op,Op::AvxInteger{kind:AvxIntegerKind::Packed(kind),width,lane_bits,destination:VectorOperand::Register(dst),source1:Some(src1),source2:VectorOperand::Register(src2),control:None,feature});
  }}}}
 }
}
#[test] fn packed_moves_both_widths_require_avx(){
 for (pp,kind) in [(1,PackedKind::MoveAligned),(2,PackedKind::MoveUnaligned)]{for (l,width) in [(0,VectorWidth::Bits128),(4,VectorWidth::Bits256)]{for op in [0x6f,0x7f]{
  let (dst,src)=if op==0x6f{(0,1)}else{(1,0)};
  let i=one(Mode::X86,0,&[0xc5,0xf8|l|pp,op,0xc1]);assert_eq!(i.avx_feature(),Some(CpuFeature::Avx));assert_eq!(i.op,Op::AvxInteger{kind:AvxIntegerKind::Packed(kind),width,lane_bits:None,destination:VectorOperand::Register(dst),source1:None,source2:VectorOperand::Register(src),control:None,feature:CpuFeature::Avx});
 }}}
}
#[test] fn extended_permute_register_matrix(){
 for (op,kind,lane_bits) in [(0x36,AvxIntegerKind::PermuteDwords,Some(32)),(0x00,AvxIntegerKind::Extended(ExtendedPackedKind::ShuffleBytes),Some(8))]{
  for dst in 0..16u8{for src1 in 0..16u8{for src2 in 0..16u8{
   let b=[0xc4,0xe2^((dst>>3)<<7)^((src2>>3)<<5),((!src1&15)<<3)|5,op,0xc0|((dst&7)<<3)|(src2&7)];
   assert_eq!(one(Mode::X64,0,&b).op,Op::AvxInteger{kind,width:VectorWidth::Bits256,lane_bits,destination:VectorOperand::Register(dst),source1:Some(src1),source2:VectorOperand::Register(src2),control:None,feature:CpuFeature::Avx2});
  }}}
 }
}
#[test] fn unary_abs_reserved_vvvv(){
 for (opcode,lane_bits) in [(0x1c,8),(0x1d,16),(0x1e,32)]{
  assert_eq!(one(Mode::X64,0,&[0xc4,0xe2,0x7d,opcode,0xc1]).op,Op::AvxInteger{kind:AvxIntegerKind::Extended(ExtendedPackedKind::Abs),width:VectorWidth::Bits256,lane_bits:Some(lane_bits),destination:VectorOperand::Register(0),source1:None,source2:VectorOperand::Register(1),control:None,feature:CpuFeature::Avx2});
 }
}
#[test] fn blend_all_control_values(){
 for (l,width) in [(0,VectorWidth::Bits128),(4,VectorWidth::Bits256)]{for control in 0..=255u8{
  assert_eq!(one(Mode::X64,0,&[0xc4,0xe3,0x69|l,0x02,0xc1,control]).op,Op::AvxInteger{kind:AvxIntegerKind::BlendDwords,width,lane_bits:Some(32),destination:VectorOperand::Register(0),source1:Some(2),source2:VectorOperand::Register(1),control:Some(control),feature:CpuFeature::Avx2});
 }}
}
#[test] fn blend_rip_eip_include_immediate(){
 for (pc,pre,base,target) in [(0x1000,&[][..],Base::Rip,0x100a),(0x1_0000_1000,&[0x67][..],Base::Eip,0x100b)]{
  let mut b=pre.to_vec();b.extend([0xc4,0xe3,0x6d,0x02,0x05,0,0,0,0,0x55]);
  let i=one(Mode::X64,pc,&b);assert!(matches!(i.op,Op::AvxInteger{kind:AvxIntegerKind::BlendDwords,source2:VectorOperand::Memory(m),control:Some(0x55),..} if m.base==base&&m.rip_target==Some(Target::Address(target))));
 }
}
#[test] fn memory_store_and_segment(){
 let i=one(Mode::X86,0,&[0x64,0x67,0xc5,0xfe,0x7f,0]);assert_eq!(i.address_width,16);assert_eq!(i.segment_override,Some(Segment::Fs));assert!(matches!(i.op,Op::AvxInteger{destination:VectorOperand::Memory(m),source2:VectorOperand::Register(0),feature:CpuFeature::Avx,..} if m.base==Base::Register(3)&&m.index==Some(6)));
}
#[test] fn exclusions(){
 for b in [&[0xc5,0xfc,0xfc,0xc0][..],&[0xc5,0xed,0x6f,0xc0],&[0xc4,0xe2,0x79,0x36,0xc0],&[0xc4,0xe2,0x6d,0x1c,0xc0],&[0xc4,0xe2,0x7c,0x36,0xc0],&[0xc4,0xe3,0x7d,0xff,0xc0,0],&[0xc4,0xe3,0xfd,0x02,0xc0,0],&[0xf0,0xc5,0xfd,0xfc,0],&[0x64,0xc5,0xfd,0xfc,0xc0]]{
  let mut stream=vec![0x90];stream.extend(b);let p=x86_decode::decode(Mode::X64,0,&stream).unwrap();assert_eq!(p.stop,Stop::Unsupported{offset:1},"{:x?}",b);assert_eq!(p.consumed,1);
 }
}
#[test] fn truncate_every_boundary(){
 for b in [&[0xc4,0xe3,0x6d,0x02,0x05,0,0,0,0,0x55][..],&[0xc4,0xe2,0x7d,0x36,0x44,0x24,0xff],&[0xc5,0xfd,0xfc,0xc0]]{
  for n in 1..b.len(){let p=x86_decode::decode(Mode::X64,0,&b[..n]).unwrap();assert_eq!(p.stop,Stop::Truncated{offset:0},"{:x?}",&b[..n]);assert_eq!(p.consumed,0);}
 }
}
#[test] fn mixed_feature_state(){
 let p=x86_decode::decode(Mode::X64,0,&[0xc5,0xf9,0xfc,0xc0,0xc5,0xfd,0xfc,0xc0,0xc5,0xfd,0x6f,0xc0,0xc5,0xfc,0x58,0xc0,0x90]).unwrap();assert_eq!(p.stop,Stop::Complete);assert_eq!(p.instructions.iter().map(|i|i.avx_feature()).collect::<Vec<_>>(),[Some(CpuFeature::Avx),Some(CpuFeature::Avx2),Some(CpuFeature::Avx),Some(CpuFeature::Avx),None]);
}
