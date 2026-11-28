use negrodroid_core::x86_decode::{self,Mode,Op,VectorOperand,VectorWidth,WriteMask,EvexExtensionKind,Avx512Requirements,SseKind,PackedKind,CpuFeature,Base,Target,Stop};
fn one(pc:u64,b:&[u8])->x86_decode::Instruction{
 let p=x86_decode::decode(Mode::X64,pc,b).unwrap();assert_eq!(p.stop,Stop::Complete,"{:x?}",b);assert_eq!(p.consumed,b.len());assert_eq!(p.instructions.len(),1);assert_eq!(p.instructions[0].bytes,b);p.instructions.into_iter().next().unwrap()
}
fn width(ll:u8)->VectorWidth{match ll{0=>VectorWidth::Bits128,1=>VectorWidth::Bits256,_=>VectorWidth::Bits512}}
#[test] fn bw_register_matrix(){
 for ll in 0..3u8{for d in 0..32u8{for a in 0..32u8{for b in 0..32u8{
  let p0=0xf1^(((d>>3)&1)<<7)^(((d>>4)&1)<<4)^(((b>>3)&1)<<5)^(((b>>4)&1)<<6);
  let p1=((!a&15)<<3)|5;let p2=(ll<<5)|((!(a>>4)&1)<<3);
  let i=one(0,&[0x62,p0,p1,p2,0xfc,0xc0|((d&7)<<3)|(b&7)]);
  assert_eq!(i.op,Op::EvexExtension{kind:EvexExtensionKind::Integer(PackedKind::Add),width:width(ll),lane_bits:8,destination:d,source1:a,source2:VectorOperand::Register(b),mask:WriteMask::None,feature:CpuFeature::Avx512Bw});
  assert_eq!(i.avx512_requirements(),Some(Avx512Requirements{extension:CpuFeature::Avx512Bw,vl:ll!=2}));
 }}}}
}
#[test] fn dq_register_matrix(){
 for ll in 0..3u8{for (w,pp,bits) in [(0,0,32),(0x80,1,64)]{for (opcode,kind) in [(0x54,SseKind::And),(0x57,SseKind::Xor)]{for d in 0..32u8{for b in 0..32u8{
  let a=19u8;let p0=0xf1^(((d>>3)&1)<<7)^(((d>>4)&1)<<4)^(((b>>3)&1)<<5)^(((b>>4)&1)<<6);
  let i=one(0,&[0x62,p0,w|((!a&15)<<3)|4|pp,(ll<<5)|3,opcode,0xc0|((d&7)<<3)|(b&7)]);
  assert_eq!(i.op,Op::EvexExtension{kind:EvexExtensionKind::Float(kind),width:width(ll),lane_bits:bits,destination:d,source1:a,source2:VectorOperand::Register(b),mask:WriteMask::Merge(3),feature:CpuFeature::Avx512Dq});
  assert_eq!(i.avx512_requirements(),Some(Avx512Requirements{extension:CpuFeature::Avx512Dq,vl:ll!=2}));
 }}}}}
}
#[test] fn vl_register_matrix(){
 for ll in 0..2u8{for (w,pp,bits) in [(0,0,32),(0x80,1,64)]{for d in 0..32u8{for b in 0..32u8{
  let p0=0xf1^(((d>>3)&1)<<7)^(((d>>4)&1)<<4)^(((b>>3)&1)<<5)^(((b>>4)&1)<<6);
  let i=one(0,&[0x62,p0,w|0x6c|pp,(ll<<5)|8,0x58,0xc0|((d&7)<<3)|(b&7)]);
  assert_eq!(i.op,Op::EvexExtension{kind:EvexExtensionKind::Float(SseKind::Add),width:width(ll),lane_bits:bits,destination:d,source1:2,source2:VectorOperand::Register(b),mask:WriteMask::None,feature:CpuFeature::Avx512F});
  assert_eq!(i.avx512_requirements(),Some(Avx512Requirements{extension:CpuFeature::Avx512F,vl:true}));
 }}}}
}
#[test] fn bw_assembler_examples(){
 assert_eq!(one(0,&[0x62,0x01,0x0d,0xc7,0xfc,0xfd]).op,Op::EvexExtension{kind:EvexExtensionKind::Integer(PackedKind::Add),width:VectorWidth::Bits512,lane_bits:8,destination:31,source1:30,source2:VectorOperand::Register(29),mask:WriteMask::Zero(7),feature:CpuFeature::Avx512Bw});
 for (b,bits,k,w,d) in [(&[0x62,0xf1,0x6d,0x2a,0xfd,0x48,0x80][..],16,PackedKind::Add,VectorWidth::Bits256,-4096),(&[0x62,0xf1,0x6d,0x8a,0xf8,0x48,0x7f],8,PackedKind::Sub,VectorWidth::Bits128,2032)]{
  assert!(matches!(one(0,b).op,Op::EvexExtension{kind:EvexExtensionKind::Integer(kk),width:ww,lane_bits:bb,source2:VectorOperand::Memory(m),..} if kk==k&&ww==w&&bb==bits&&m.displacement==d));
 }
 assert!(matches!(one(0,&[0x62,0xf1,0x6d,0x48,0xf9,0xcb]).op,Op::EvexExtension{kind:EvexExtensionKind::Integer(PackedKind::Sub),lane_bits:16,..}));
}
#[test] fn dq_vl_assembler_examples(){
 for (b,feature,w,d) in [(&[0x62,0xf1,0xed,0x2a,0x54,0x48,0x7f][..],CpuFeature::Avx512Dq,VectorWidth::Bits256,4064),(&[0x62,0xf1,0x6c,0x2a,0x58,0x48,0x80],CpuFeature::Avx512F,VectorWidth::Bits256,-4096),(&[0x62,0xf1,0xed,0x0a,0x58,0x48,0x7f],CpuFeature::Avx512F,VectorWidth::Bits128,2032)]{
  assert!(matches!(one(0,b).op,Op::EvexExtension{feature:f,width:ww,source2:VectorOperand::Memory(m),..} if f==feature&&ww==w&&m.displacement==d));
 }
 assert!(matches!(one(0,&[0x62,0xf1,0x6c,0x4a,0x54,0xcb]).op,Op::EvexExtension{kind:EvexExtensionKind::Float(SseKind::And),feature:CpuFeature::Avx512Dq,width:VectorWidth::Bits512,..}));
 assert!(matches!(one(0,&[0x62,0xf1,0x6c,0x8a,0x57,0xcb]).op,Op::EvexExtension{kind:EvexExtensionKind::Float(SseKind::Xor),mask:WriteMask::Zero(2),..}));
}
#[test] fn tuple_scale_matrix(){
 for ll in 0..3u8{for disp in 0..=255u8{
  let i=one(0,&[0x62,0xf1,0x6d,(ll<<5)|8,0xfc,0x48,disp]);assert!(matches!(i.op,Op::EvexExtension{source2:VectorOperand::Memory(m),..} if m.displacement==i64::from(disp as i8)*(16i64<<ll)));
 }}
}
#[test] fn rip_disp32_unscaled(){
 let i=one(0x1000,&[0x62,0xf1,0x6d,0x2a,0xfd,0x0d,1,0,0,0]);assert!(matches!(i.op,Op::EvexExtension{source2:VectorOperand::Memory(m),..} if m.base==Base::Rip&&m.displacement==1&&m.rip_target==Some(Target::Address(0x100b))));
}
#[test] fn excluded_forms(){
 for b in [&[0x62,0xf1,0x6d,0x68,0xfc,0xc0][..],&[0x62,0xf1,0x6d,0x58,0xfc,0x00],&[0x62,0xf1,0xed,0x48,0xfc,0xc0],&[0x62,0xf1,0x6d,0x48,0x54,0xc0],&[0x62,0xf1,0x6c,0x38,0x58,0x00],&[0x62,0xf1,0x6c,0x28,0x10,0xc0],&[0x62,0xf1,0x6d,0x88,0xfc,0xc0]]{
  let p=x86_decode::decode(Mode::X64,0,b).unwrap();assert_eq!(p.stop,Stop::Unsupported{offset:0},"{:x?}",b);
 }
}
#[test] fn truncation(){
 for b in [&[0x62,0xf1,0x6d,0x2a,0xfd,0x48,0x80][..],&[0x62,0xf1,0x6c,0x8a,0x57,0xcb],&[0x62,0xf1,0x6c,0x2a,0x58,0x0d,1,0,0,0]]{for n in 1..b.len(){let p=x86_decode::decode(Mode::X64,0,&b[..n]).unwrap();assert_eq!(p.stop,Stop::Truncated{offset:0},"{:x?}",&b[..n]);}}
}
#[test] fn feature_metadata_distinct(){
 let p=x86_decode::decode(Mode::X64,0,&[0x62,0xf1,0x6d,0x28,0xfc,0xc0,0x62,0xf1,0x6c,0x48,0x54,0xc0,0x62,0xf1,0x6c,0x08,0x58,0xc0,0x62,0xf1,0x6c,0x48,0x58,0xc0,0x90]).unwrap();assert_eq!(p.stop,Stop::Complete);
 assert_eq!(p.instructions.iter().map(|i|i.avx512_requirements()).collect::<Vec<_>>(),[Some(Avx512Requirements{extension:CpuFeature::Avx512Bw,vl:true}),Some(Avx512Requirements{extension:CpuFeature::Avx512Dq,vl:false}),Some(Avx512Requirements{extension:CpuFeature::Avx512F,vl:true}),Some(Avx512Requirements{extension:CpuFeature::Avx512F,vl:false}),None]);
}
