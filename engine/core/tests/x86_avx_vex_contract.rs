use negrodroid_core::x86_decode::{self,Mode,Op,VectorOperand,VectorWidth,VectorZero,FloatFormat,SseKind,CpuFeature,Base,Target,Segment,Stop};
fn one(mode:Mode,pc:u64,b:&[u8])->x86_decode::Instruction{
 let p=x86_decode::decode(mode,pc,b).unwrap();assert_eq!(p.stop,Stop::Complete,"{:x?}",b);assert_eq!(p.consumed,b.len());assert_eq!(p.instructions.len(),1);assert_eq!(p.instructions[0].bytes,b);p.instructions.into_iter().next().unwrap()
}
#[test] fn vex3_arithmetic_register_matrix(){
 for (opcode,kind) in [(0x58,SseKind::Add),(0x59,SseKind::Mul),(0x5c,SseKind::Sub),(0x5e,SseKind::Div)]{
  for (l,width) in [(0,VectorWidth::Bits128),(4,VectorWidth::Bits256)]{for dst in 0..16u8{for src1 in 0..16u8{for src2 in 0..16u8{
   let ext=0xe1^((dst>>3)<<7)^((src2>>3)<<5);
   let fields=((!src1&15)<<3)|l;
   let b=[0xc4,ext,fields,opcode,0xc0|((dst&7)<<3)|(src2&7)];
   let i=one(Mode::X64,0,&b);assert_eq!(i.avx_feature(),Some(CpuFeature::Avx));assert_eq!(i.op,Op::AvxFloat{kind,format:FloatFormat::PackedSingle,width,destination:VectorOperand::Register(dst),source1:Some(src1),source2:VectorOperand::Register(src2)});
  }}}}
 }
}
#[test] fn vex2_format_and_width(){
 for (pp,format) in [(0,FloatFormat::PackedSingle),(1,FloatFormat::PackedDouble),(2,FloatFormat::ScalarSingle),(3,FloatFormat::ScalarDouble)]{
  for dst in 0..16u8{for src1 in 0..16u8{for src2 in 0..8u8{
   let b=[0xc5,((!(dst>>3)&1)<<7)|((!src1&15)<<3)|pp,0x58,0xc0|((dst&7)<<3)|src2];
   assert_eq!(one(Mode::X64,0,&b).op,Op::AvxFloat{kind:SseKind::Add,format,width:VectorWidth::Bits128,destination:VectorOperand::Register(dst),source1:Some(src1),source2:VectorOperand::Register(src2)});
  }}}
 }
}
#[test] fn packed_moves_and_sqrt_reserved_vvvv(){
 for (op,kind) in [(0x10,SseKind::MoveUnaligned),(0x11,SseKind::MoveUnaligned),(0x28,SseKind::MoveAligned),(0x29,SseKind::MoveAligned),(0x51,SseKind::Sqrt)]{
  let (dst,src)=if matches!(op,0x11|0x29){(1,0)}else{(0,1)};
  assert_eq!(one(Mode::X64,0,&[0xc5,0xfd,op,0xc1]).op,Op::AvxFloat{kind,format:FloatFormat::PackedDouble,width:VectorWidth::Bits256,destination:VectorOperand::Register(dst),source1:None,source2:VectorOperand::Register(src)});
 }
}
#[test] fn scalar_sqrt_has_merge_source(){
 assert_eq!(one(Mode::X64,0,&[0xc5,0xea,0x51,0xc1]).op,Op::AvxFloat{kind:SseKind::Sqrt,format:FloatFormat::ScalarSingle,width:VectorWidth::Bits128,destination:VectorOperand::Register(0),source1:Some(2),source2:VectorOperand::Register(1)});
}
#[test] fn zero_upper_and_all(){
 for mode in [Mode::X86,Mode::X64]{for (p,kind) in [(0xf8,VectorZero::Upper),(0xfc,VectorZero::All)]{
  assert_eq!(one(mode,0,&[0xc5,p,0x77]).op,Op::AvxZero{kind});assert_eq!(one(mode,0,&[0xc4,0xe1,p&0x7f,0x77]).op,Op::AvxZero{kind});
 }}
}
#[test] fn rip_and_eip_memory(){
 let i=one(Mode::X64,0x1000,&[0x64,0xc5,0xfc,0x58,0x05,0,0,0,0]);assert_eq!(i.segment_override,Some(Segment::Fs));assert!(matches!(i.op,Op::AvxFloat{source2:VectorOperand::Memory(m),width:VectorWidth::Bits256,..} if m.base==Base::Rip&&m.rip_target==Some(Target::Address(0x1009))));
 let i=one(Mode::X64,0x1_0000_1000,&[0x67,0xc5,0xfc,0x11,0x05,0,0,0,0]);assert_eq!(i.address_width,32);assert!(matches!(i.op,Op::AvxFloat{destination:VectorOperand::Memory(m),source1:None,..} if m.base==Base::Eip&&m.rip_target==Some(Target::Address(0x1009))));
}
#[test] fn vex_sib_and_x86_address_override(){
 let i=one(Mode::X64,0,&[0xc4,0x01,0x7c,0x58,0x04,0x48]);assert!(matches!(i.op,Op::AvxFloat{destination:VectorOperand::Register(8),source2:VectorOperand::Memory(m),..} if m.base==Base::Register(8)&&m.index==Some(9)&&m.scale==2));
 let i=one(Mode::X86,0,&[0x67,0xc5,0xf8,0x58,0x00]);assert_eq!(i.address_width,16);assert!(matches!(i.op,Op::AvxFloat{source2:VectorOperand::Memory(m),..} if m.base==Base::Register(3)&&m.index==Some(6)));
}
#[test] fn unsupported_vex_forms(){
 for (mode,b) in [(Mode::X64,&[0x66,0xc5,0xf8,0x58,0xc0][..]),(Mode::X64,&[0x48,0xc5,0xf8,0x58,0xc0]),(Mode::X64,&[0xf0,0xc5,0xf8,0x58,0x00]),(Mode::X64,&[0xc4,0xe2,0x78,0x58,0xc0]),(Mode::X64,&[0xc4,0xe1,0xf8,0x58,0xc0]),(Mode::X64,&[0xc5,0xfe,0x58,0xc0]),(Mode::X64,&[0xc5,0xea,0x10,0xc0]),(Mode::X64,&[0xc5,0xe8,0x28,0xc0]),(Mode::X64,&[0xc5,0xe8,0x77]),(Mode::X64,&[0x67,0xc5,0xf8,0x77]),(Mode::X64,&[0x64,0xc5,0xf8,0x58,0xc0]),(Mode::X86,&[0xc5,0x78,0x58,0xc0]),(Mode::X86,&[0xc4,0xc1,0x78,0x58,0xc0]),(Mode::X64,&[0x62,0xf1,0x7c,0x48,0x58,0xc0])]{let mut stream=vec![0x90];stream.extend(b);let p=x86_decode::decode(mode,0,&stream).unwrap();assert_eq!(p.stop,Stop::Unsupported{offset:1},"{:x?}",b);assert_eq!(p.consumed,1);}
}
#[test] fn truncate_every_boundary(){
 for b in [&[0xc5,0xf8,0x77][..],&[0x64,0xc5,0xfc,0x58,0x05,0,0,0,0],&[0xc4,0xe1,0x78,0x58,0x44,0x24,0xff]]{for n in 1..b.len(){let p=x86_decode::decode(Mode::X64,0,&b[..n]).unwrap();assert_eq!(p.stop,Stop::Truncated{offset:0},"{:x?}",&b[..n]);assert_eq!(p.consumed,0);}}
}
#[test] fn mixed_vector_prefix_stream(){
 let p=x86_decode::decode(Mode::X64,0,&[0xc5,0xfc,0x58,0xc0,0x0f,0x58,0xc0,0xc5,0xf8,0x77,0x90]).unwrap();assert_eq!(p.stop,Stop::Complete);assert_eq!(p.instructions.iter().map(|i|i.avx_feature()).collect::<Vec<_>>(),[Some(CpuFeature::Avx),None,Some(CpuFeature::Avx),None]);assert_eq!(p.instructions[1].sse_feature(),Some(CpuFeature::Sse));
}
