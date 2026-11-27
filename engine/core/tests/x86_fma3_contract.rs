use negrodroid_core::x86_decode::{self,Mode,Op,VectorOperand,VectorWidth,FloatFormat,FmaOrder,FmaKind,CpuFeature,Base,Target,Stop};
fn one(mode:Mode,pc:u64,b:&[u8])->x86_decode::Instruction{
 let p=x86_decode::decode(mode,pc,b).unwrap();assert_eq!(p.stop,Stop::Complete,"{:x?}",b);assert_eq!(p.consumed,b.len());assert_eq!(p.instructions.len(),1);assert_eq!(p.instructions[0].bytes,b);p.instructions.into_iter().next().unwrap()
}
#[test] fn packed_register_matrix(){
 for (op,order) in [(0x98,FmaOrder::Order132),(0xa8,FmaOrder::Order213),(0xb8,FmaOrder::Order231)]{
  for (w,format) in [(0,FloatFormat::PackedSingle),(0x80,FloatFormat::PackedDouble)]{for (l,width) in [(0,VectorWidth::Bits128),(4,VectorWidth::Bits256)]{
   for d in 0..16u8{for a in 0..16u8{for b in 0..16u8{
    let bytes=[0xc4,0xe2^((d>>3)<<7)^((b>>3)<<5),w|((!a&15)<<3)|l|1,op,0xc0|((d&7)<<3)|(b&7)];
    let i=one(Mode::X64,0,&bytes);assert_eq!(i.avx_feature(),Some(CpuFeature::Fma));assert_eq!(i.op,Op::FusedFloat{kind:FmaKind::Add,order,format,width,destination:d,source1:a,source2:VectorOperand::Register(b)});
   }}}
  }}
 }
}
#[test] fn scalar_register_matrix(){
 for (op,order) in [(0x99,FmaOrder::Order132),(0xa9,FmaOrder::Order213),(0xb9,FmaOrder::Order231)]{for (w,format) in [(0,FloatFormat::ScalarSingle),(0x80,FloatFormat::ScalarDouble)]{
  for d in 0..16u8{for a in 0..16u8{for b in 0..16u8{
   let bytes=[0xc4,0xe2^((d>>3)<<7)^((b>>3)<<5),w|((!a&15)<<3)|1,op,0xc0|((d&7)<<3)|(b&7)];
   assert_eq!(one(Mode::X64,0,&bytes).op,Op::FusedFloat{kind:FmaKind::Add,order,format,width:VectorWidth::Bits128,destination:d,source1:a,source2:VectorOperand::Register(b)});
  }}}
 }}
}
#[test] fn all_opcode_families(){
 for (hi,order) in [(0x90,FmaOrder::Order132),(0xa0,FmaOrder::Order213),(0xb0,FmaOrder::Order231)]{
  for (lo,kind,scalar) in [(6,FmaKind::AddSub,false),(7,FmaKind::SubAdd,false),(8,FmaKind::Add,false),(9,FmaKind::Add,true),(10,FmaKind::Sub,false),(11,FmaKind::Sub,true),(12,FmaKind::NegAdd,false),(13,FmaKind::NegAdd,true),(14,FmaKind::NegSub,false),(15,FmaKind::NegSub,true)]{
   for (w,format) in [(0,if scalar{FloatFormat::ScalarSingle}else{FloatFormat::PackedSingle}),(0x80,if scalar{FloatFormat::ScalarDouble}else{FloatFormat::PackedDouble})]{
    assert_eq!(one(Mode::X86,0,&[0xc4,0xe2,w|0x69,hi|lo,0xc1]).op,Op::FusedFloat{kind,order,format,width:VectorWidth::Bits128,destination:0,source1:2,source2:VectorOperand::Register(1)});
   }
  }
 }
}
#[test] fn extended_register_order(){
 let i=one(Mode::X64,0,&[0xc4,0x42,0x0d,0xb8,0xfd]);assert_eq!(i.op,Op::FusedFloat{kind:FmaKind::Add,order:FmaOrder::Order231,format:FloatFormat::PackedSingle,width:VectorWidth::Bits256,destination:15,source1:14,source2:VectorOperand::Register(13)});
}
#[test] fn rip_memory(){
 let i=one(Mode::X64,0x1000,&[0xc4,0xe2,0xe9,0xab,0x05,1,0,0,0]);assert!(matches!(i.op,Op::FusedFloat{kind:FmaKind::Sub,order:FmaOrder::Order213,format:FloatFormat::ScalarDouble,source2:VectorOperand::Memory(m),..} if m.base==Base::Rip&&m.rip_target==Some(Target::Address(0x100a))));
}
#[test] fn legacy_address_override(){
 let i=one(Mode::X86,0,&[0x67,0xc4,0xe2,0x69,0x98,0x00]);assert_eq!(i.address_width,16);assert!(matches!(i.op,Op::FusedFloat{source2:VectorOperand::Memory(m),..} if m.base==Base::Register(3)&&m.index==Some(6)));
}
#[test] fn memory_segment(){
 let i=one(Mode::X64,0,&[0x64,0xc4,0xe2,0x6d,0x9c,0x40,0x80]);assert!(matches!(i.op,Op::FusedFloat{kind:FmaKind::NegAdd,source2:VectorOperand::Memory(m),..} if m.displacement == -128));assert!(i.segment_override.is_some());
}
#[test] fn exclusions(){
 for b in [&[0xc4,0xe2,0x68,0x98,0xc0][..],&[0xc4,0xe2,0x6d,0x99,0xc0],&[0xc4,0xe2,0x69,0x95,0xc0],&[0xc4,0xe1,0xe9,0x58,0xc0],&[0xc4,0xe2,0xfd,0x36,0xc0],&[0xf0,0xc4,0xe2,0x69,0x98,0x00],&[0x64,0xc4,0xe2,0x69,0x98,0xc0]]{let p=x86_decode::decode(Mode::X64,0,b).unwrap();assert_eq!(p.stop,Stop::Unsupported{offset:0},"{:x?}",b);}
}
#[test] fn truncate_all_boundaries(){
 for b in [&[0xc4,0xe2,0xe9,0xab,0x05,1,0,0,0][..],&[0x64,0xc4,0xe2,0x6d,0x9c,0x40,0x80]]{for n in 1..b.len(){let p=x86_decode::decode(Mode::X64,0,&b[..n]).unwrap();assert_eq!(p.stop,Stop::Truncated{offset:0},"{:x?}",&b[..n]);}}
}
#[test] fn feature_state(){
 let p=x86_decode::decode(Mode::X64,0,&[0xc4,0xe2,0x69,0x98,0xc0,0xc5,0xfc,0x58,0xc0,0x90]).unwrap();assert_eq!(p.stop,Stop::Complete);assert_eq!(p.instructions.iter().map(|i|i.avx_feature()).collect::<Vec<_>>(),[Some(CpuFeature::Fma),Some(CpuFeature::Avx),None]);
}
