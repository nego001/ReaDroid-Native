use negrodroid_core::x86_decode::{self,Mode,Op,VectorOperand,WriteMask,FloatFormat,SseKind,PackedKind,MaskLogic,CpuFeature,Base,Target,Stop};
fn one(pc:u64,b:&[u8])->x86_decode::Instruction{
 let p=x86_decode::decode(Mode::X64,pc,b).unwrap();assert_eq!(p.stop,Stop::Complete,"{:x?}",b);assert_eq!(p.consumed,b.len());assert_eq!(p.instructions.len(),1);assert_eq!(p.instructions[0].bytes,b);p.instructions.into_iter().next().unwrap()
}
#[test] fn broadcast_displacement_matrix(){
 for (p1,scale,format) in [(0x6c,4,FloatFormat::PackedSingle),(0xed,8,FloatFormat::PackedDouble)]{
  for disp in 0..=255u8{let i=one(0,&[0x62,0xf1,p1,0xda,0x58,0x48,disp]);assert_eq!(i.avx_feature(),Some(CpuFeature::Avx512F));assert!(matches!(i.op,Op::EvexBroadcast{kind:SseKind::Add,format:f,destination:1,source1:2,memory:m,mask:WriteMask::Zero(2)} if f==format&&m.base==Base::Register(0)&&m.displacement==i64::from(disp as i8)*scale));}
 }
}
#[test] fn broadcast_disp32_not_scaled(){
 for (p1,scale) in [(0x6c,4i32),(0xed,8)]{for d in [-129*scale,128*scale,1,-1]{let mut b=vec![0x62,0xf1,p1,0xda,0x58,0x88];b.extend(d.to_le_bytes());assert!(matches!(one(0,&b).op,Op::EvexBroadcast{memory:m,..} if m.displacement==i64::from(d)));}}
}
#[test] fn integer_register_matrix(){
 for (opcode,w,kind,lane_bits) in [(0xfe,0,PackedKind::Add,32),(0xd4,0x80,PackedKind::Add,64),(0xfa,0,PackedKind::Sub,32),(0xfb,0x80,PackedKind::Sub,64),(0xdb,0,PackedKind::And,32),(0xef,0x80,PackedKind::Xor,64)]{
  for dst in 0..32u8{for a in 0..32u8{for b in 0..32u8{
   let p0=0xf1^(((dst>>3)&1)<<7)^(((dst>>4)&1)<<4)^(((b>>3)&1)<<5)^(((b>>4)&1)<<6);
   let p1=w|((!a&15)<<3)|5;let p2=0x40|((!(a>>4)&1)<<3);
   let i=one(0,&[0x62,p0,p1,p2,opcode,0xc0|((dst&7)<<3)|(b&7)]);assert_eq!(i.op,Op::EvexInteger{kind,lane_bits,destination:dst,source1:a,source2:VectorOperand::Register(b),mask:WriteMask::None,broadcast:false});
  }}}
 }
}
#[test] fn assembler_integer_examples(){
 assert_eq!(one(0,&[0x62,0x01,0x0d,0xc7,0xfe,0xfd]).op,Op::EvexInteger{kind:PackedKind::Add,lane_bits:32,destination:31,source1:30,source2:VectorOperand::Register(29),mask:WriteMask::Zero(7),broadcast:false});
 assert!(matches!(one(0,&[0x62,0xd1,0xed,0x5a,0xd4,0x49,1]).op,Op::EvexInteger{kind:PackedKind::Add,lane_bits:64,destination:1,source1:2,source2:VectorOperand::Memory(m),mask:WriteMask::Merge(2),broadcast:true} if m.base==Base::Register(9)&&m.displacement==8));
 assert!(matches!(one(0,&[0x62,0xf1,0x6d,0x48,0xfa,0x48,1]).op,Op::EvexInteger{kind:PackedKind::Sub,lane_bits:32,source2:VectorOperand::Memory(m),broadcast:false,..} if m.displacement==64));
}
#[test] fn mask_ternary_matrix(){
 for (op,kind) in [(0x41,MaskLogic::And),(0x45,MaskLogic::Or),(0x47,MaskLogic::Xor)]{for d in 0..8u8{for a in 0..8u8{for b in 0..8u8{let i=one(0,&[0xc5,0x84|((!a&15)<<3),op,0xc0|(d<<3)|b]);assert_eq!(i.avx_feature(),Some(CpuFeature::Avx512F));assert_eq!(i.op,Op::MaskWord{kind,destination:d,source1:Some(a),source2:b});}}}}
}
#[test] fn mask_unary_matrix(){
 for d in 0..8u8{for a in 0..8u8{assert_eq!(one(0,&[0xc5,0xf8,0x44,0xc0|(d<<3)|a]).op,Op::MaskWord{kind:MaskLogic::Not,destination:d,source1:None,source2:a});}}
}
#[test] fn broadcast_rip_and_segment(){
 let i=one(0x1000,&[0x64,0x62,0xf1,0x6c,0xda,0x58,0x0d,1,0,0,0]);assert!(matches!(i.op,Op::EvexBroadcast{memory:m,..} if m.base==Base::Rip&&m.rip_target==Some(Target::Address(0x100c))));
}
#[test] fn excluded_forms(){
 for b in [&[0x62,0xf1,0x6c,0xda,0x58,0xc0][..],&[0x62,0xf1,0x7c,0x58,0x10,0],&[0x62,0xf1,0x7c,0x58,0x51,0],&[0x62,0xf1,0xed,0x48,0xfe,0xc0],&[0xc5,0xe8,0x41,0xcb],&[0xc5,0xfc,0x44,0xca],&[0xc5,0xac,0x41,0xcb],&[0xc5,0xec,0x41,0x0b],&[0x67,0xc5,0xec,0x41,0xcb]]{let p=x86_decode::decode(Mode::X64,0,b).unwrap();assert_eq!(p.stop,Stop::Unsupported{offset:0},"{:x?}",b);}
}
#[test] fn truncation(){
 for b in [&[0x62,0xf1,0x6c,0xda,0x58,0x48,1][..],&[0xc5,0xec,0x41,0xcb],&[0x62,0x01,0x0d,0xc7,0xfe,0xfd]]{for n in 1..b.len(){let p=x86_decode::decode(Mode::X64,0,&b[..n]).unwrap();assert_eq!(p.stop,Stop::Truncated{offset:0},"{:x?}",&b[..n]);}}
}
#[test] fn mask_and_vector_stream(){
 let p=x86_decode::decode(Mode::X64,0,&[0xc5,0xec,0x41,0xcb,0x62,0xf1,0x6c,0xda,0x58,0x48,1,0x90]).unwrap();assert_eq!(p.stop,Stop::Complete);assert_eq!(p.instructions.len(),3);assert_eq!(p.instructions[0].avx_feature(),Some(CpuFeature::Avx512F));assert_eq!(p.instructions[2].avx_feature(),None);
}
