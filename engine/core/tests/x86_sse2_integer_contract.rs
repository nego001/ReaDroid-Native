use negrodroid_core::x86_decode::{self,Mode,Op,XmmOperand,ConversionOperand,ConversionKind,PackedKind,CpuFeature,Base,Target,Segment,Stop};
fn one(mode:Mode,pc:u64,b:&[u8])->x86_decode::Instruction{
 let p=x86_decode::decode(mode,pc,b).unwrap();assert_eq!(p.stop,Stop::Complete);assert_eq!(p.consumed,b.len());assert_eq!(p.instructions.len(),1);assert_eq!(p.instructions[0].bytes,b);p.instructions.into_iter().next().unwrap()
}
#[test] fn packed_register_matrix(){
 use PackedKind::*;
 for (op,kind,lane_bits) in [(0xfc,Add,Some(8)),(0xfd,Add,Some(16)),(0xfe,Add,Some(32)),(0xd4,Add,Some(64)),(0xf8,Sub,Some(8)),(0xf9,Sub,Some(16)),(0xfa,Sub,Some(32)),(0xfb,Sub,Some(64)),(0x74,Equal,Some(8)),(0x75,Equal,Some(16)),(0x76,Equal,Some(32)),(0x64,GreaterSigned,Some(8)),(0x65,GreaterSigned,Some(16)),(0x66,GreaterSigned,Some(32)),(0xdb,And,None),(0xdf,AndNot,None),(0xeb,Or,None),(0xef,Xor,None)]{
  for dst in 0..16u8{for src in 0..16u8{
   let b=[0x66,0x40|((dst>>3)<<2)|(src>>3),0x0f,op,0xc0|((dst&7)<<3)|(src&7)];
   let i=one(Mode::X64,0,&b);assert_eq!(i.sse_feature(),Some(CpuFeature::Sse2));assert_eq!(i.op,Op::PackedInteger{kind,lane_bits,destination:XmmOperand::Register(dst),source:XmmOperand::Register(src)});
  }}
 }
}
#[test] fn integer_move_prefix_and_direction(){
 for (prefix,kind) in [(0x66,PackedKind::MoveAligned),(0xf3,PackedKind::MoveUnaligned)]{
  for op in [0x6f,0x7f]{let (dst,src)=if op==0x6f{(0,1)}else{(1,0)};assert_eq!(one(Mode::X86,0,&[prefix,0x0f,op,0xc1]).op,Op::PackedInteger{kind,lane_bits:None,destination:XmmOperand::Register(dst),source:XmmOperand::Register(src)});}
 }
}
#[test] fn packed_memory_segment_eip(){
 let i=one(Mode::X64,0x1_0000_1000,&[0x64,0x67,0x66,0x0f,0xfc,0x05,0,0,0,0]);assert_eq!(i.address_width,32);assert_eq!(i.segment_override,Some(Segment::Fs));assert!(matches!(i.op,Op::PackedInteger{lane_bits:Some(8),source:XmmOperand::Memory(m),..} if m.base==Base::Eip&&m.rip_target==Some(Target::Address(0x100a))));
}
#[test] fn packed_move_memory_store(){
 assert!(matches!(one(Mode::X86,0,&[0xf3,0x67,0x0f,0x7f,0x00]).op,Op::PackedInteger{kind:PackedKind::MoveUnaligned,destination:XmmOperand::Memory(m),source:XmmOperand::Register(0),..} if m.base==Base::Register(3)&&m.index==Some(6)));
}
#[test] fn scalar_conversion_register_matrix(){
 for (op,kind) in [(0x2a,ConversionKind::IntToFloat),(0x2c,ConversionKind::FloatToIntTruncated),(0x2d,ConversionKind::FloatToIntRounded)]{
  for (prefix,float_bits) in [(0xf3,32),(0xf2,64)]{for (w,int_bits) in [(0,32),(8,64)]{for dst in 0..16u8{for src in 0..16u8{
   let b=[prefix,0x40|w|((dst>>3)<<2)|(src>>3),0x0f,op,0xc0|((dst&7)<<3)|(src&7)];
   let (destination,source)=if op==0x2a{(ConversionOperand::Xmm(dst),ConversionOperand::Gpr(src))}else{(ConversionOperand::Gpr(dst),ConversionOperand::Xmm(src))};
   let i=one(Mode::X64,0,&b);assert_eq!(i.op,Op::ScalarConvert{kind,float_bits,int_bits,destination,source});assert_eq!(i.sse_feature(),Some(if float_bits==32{CpuFeature::Sse}else{CpuFeature::Sse2}));
  }}}}
 }
}
#[test] fn conversion_memory_rip_and_width(){
 let i=one(Mode::X64,0x1000,&[0xf2,0x48,0x0f,0x2a,0x05,0,0,0,0]);
 assert!(matches!(i.op,Op::ScalarConvert{kind:ConversionKind::IntToFloat,float_bits:64,int_bits:64,destination:ConversionOperand::Xmm(0),source:ConversionOperand::Memory(m)} if m.rip_target==Some(Target::Address(0x1009))));
 assert_eq!(one(Mode::X86,0,&[0xf3,0x0f,0x2c,0xc1]).op,Op::ScalarConvert{kind:ConversionKind::FloatToIntTruncated,float_bits:32,int_bits:32,destination:ConversionOperand::Gpr(0),source:ConversionOperand::Xmm(1)});
}
#[test] fn conversion_memory_legacy_segment(){
 let i=one(Mode::X86,0,&[0x64,0xf2,0x67,0x0f,0x2d,0x00]);assert_eq!(i.segment_override,Some(Segment::Fs));assert_eq!(i.address_width,16);
 assert!(matches!(i.op,Op::ScalarConvert{kind:ConversionKind::FloatToIntRounded,float_bits:64,int_bits:32,destination:ConversionOperand::Gpr(0),source:ConversionOperand::Memory(m)} if m.base==Base::Register(3)&&m.index==Some(6)));
}
#[test] fn excluded_mmx_and_prefix_conflicts(){
 for b in [&[0x0f,0xfc,0xc0][..],&[0xf3,0x0f,0xfc,0xc0],&[0xf2,0x0f,0x6f,0xc0],&[0x66,0xf3,0x0f,0x6f,0xc0],&[0x66,0x48,0x0f,0xfc,0xc0],&[0xf0,0x66,0x0f,0xfc,0x00],&[0x0f,0x2a,0xc0],&[0x66,0xf3,0x0f,0x2a,0xc0],&[0x64,0xf2,0x0f,0x2d,0xc0],&[0xf3,0x67,0x0f,0x2c,0xc0],&[0x66,0x0f,0x38,0x00,0xc0]]{
  let mut stream=vec![0x90];stream.extend(b);let p=x86_decode::decode(Mode::X64,0,&stream).unwrap();assert_eq!(p.stop,Stop::Unsupported{offset:1});assert_eq!(p.consumed,1);
 }
}
#[test] fn truncation_every_boundary(){
 for b in [&[0x64,0x67,0x66,0x0f,0xfc,0x05,0,0,0,0][..],&[0xf2,0x48,0x0f,0x2a,0x05,0,0,0,0],&[0xf3,0x0f,0x7f,0x44,0x24,0xff]]{for n in 1..b.len(){let p=x86_decode::decode(Mode::X64,0,&b[..n]).unwrap();assert_eq!(p.stop,Stop::Truncated{offset:0});assert_eq!(p.consumed,0);}}
}
#[test] fn mixed_scalar_and_packed_stream(){
 let p=x86_decode::decode(Mode::X64,0,&[0x66,0x0f,0xfc,0xc0,0xf3,0x0f,0x2a,0xc0,0xf2,0x0f,0x58,0xc0,0x90]).unwrap();assert_eq!(p.stop,Stop::Complete);assert_eq!(p.instructions.len(),4);assert!(matches!(p.instructions[0].op,Op::PackedInteger{..}));assert!(matches!(p.instructions[1].op,Op::ScalarConvert{..}));assert!(matches!(p.instructions[2].op,Op::Sse{..}));assert_eq!(p.instructions[3].op,Op::Nop);
}
