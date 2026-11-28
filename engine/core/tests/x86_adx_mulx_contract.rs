use negrodroid_core::x86_decode::{self,Mode,Op,Operand,CarryChain,CpuFeature,Base,Target,Stop};
fn one(mode:Mode,pc:u64,b:&[u8])->x86_decode::Instruction{
 let p=x86_decode::decode(mode,pc,b).unwrap();assert_eq!(p.stop,Stop::Complete,"{:x?}",b);assert_eq!(p.consumed,b.len());assert_eq!(p.instructions.len(),1);assert_eq!(p.instructions[0].bytes,b);p.instructions.into_iter().next().unwrap()
}
#[test] fn mulx_register_matrix(){
 for (w,width) in [(0,32),(0x80,64)]{for hi in 0..16u8{for lo in 0..16u8{for r in 0..16u8{
  let b=[0xc4,0xe2^((hi>>3)<<7)^((r>>3)<<5),w|((!lo&15)<<3)|3,0xf6,0xc0|((hi&7)<<3)|(r&7)];
  let i=one(Mode::X64,0,&b);assert_eq!(i.op,Op::MultiplyUnsignedDouble{width,high_destination:hi,low_destination:lo,source:Operand::Register(r),implicit_source:2});assert_eq!(i.bmi_feature(),Some(CpuFeature::Bmi2));assert_eq!(i.avx_feature(),None);assert_eq!(i.adx_feature(),None);
 }}}}
}
#[test] fn adx_register_matrix(){
 for (prefix,chain) in [(0x66,CarryChain::Carry),(0xf3,CarryChain::Overflow)]{for (w,width) in [(0,32),(8,64)]{for d in 0..16u8{for r in 0..16u8{
  let rex=0x40|w|((d>>3)<<2)|(r>>3);let b=[prefix,rex,0x0f,0x38,0xf6,0xc0|((d&7)<<3)|(r&7)];
  let i=one(Mode::X64,0,&b);assert_eq!(i.op,Op::AddCarryChain{chain,width,destination:d,source:Operand::Register(r)});assert_eq!(i.adx_feature(),Some(CpuFeature::Adx));assert_eq!(i.bmi_feature(),None);
 }}}}
}
#[test] fn independent_mulx_register_examples(){
 for (b,width,hi,lo,r) in [(&[0xc4,0x42,0x8b,0xf6,0xfd][..],64,15,14,13),(&[0xc4,0xe2,0x73,0xf6,0xc3],32,0,1,3)]{
  assert_eq!(one(Mode::X64,0,b).op,Op::MultiplyUnsignedDouble{width,high_destination:hi,low_destination:lo,source:Operand::Register(r),implicit_source:2});
 }
}
#[test] fn independent_adx_examples(){
 for (b,chain,width,d,r) in [(&[0x66,0x4d,0x0f,0x38,0xf6,0xfd][..],CarryChain::Carry,64,15,13),(&[0xf3,0x4d,0x0f,0x38,0xf6,0xf4],CarryChain::Overflow,64,14,12),(&[0x66,0x0f,0x38,0xf6,0xc3],CarryChain::Carry,32,0,3)]{
  assert_eq!(one(Mode::X64,0,b).op,Op::AddCarryChain{chain,width,destination:d,source:Operand::Register(r)});
 }
 assert!(matches!(one(Mode::X64,0,&[0xf3,0x0f,0x38,0xf6,0x48,4]).op,Op::AddCarryChain{chain:CarryChain::Overflow,width:32,destination:1,source:Operand::Memory(m)} if m.base==Base::Register(0)&&m.displacement==4));
}
#[test] fn mulx_rip_assembler_fixture(){
 let i=one(Mode::X64,0x1000,&[0xc4,0x62,0xb3,0xf6,0x05,1,0,0,0]);assert!(matches!(i.op,Op::MultiplyUnsignedDouble{width:64,high_destination:8,low_destination:9,implicit_source:2,source:Operand::Memory(m)} if m.base==Base::Rip&&m.rip_target==Some(Target::Address(0x100a))));
}
#[test] fn adx_rip_and_eip(){
 let i=one(Mode::X64,0x1000,&[0x66,0x48,0x0f,0x38,0xf6,0x05,1,0,0,0]);assert!(matches!(i.op,Op::AddCarryChain{chain:CarryChain::Carry,width:64,source:Operand::Memory(m),..} if m.base==Base::Rip&&m.rip_target==Some(Target::Address(0x100b))));
 let i=one(Mode::X64,0x1_0000_1000,&[0x67,0xf3,0x0f,0x38,0xf6,0x05,1,0,0,0]);assert!(matches!(i.op,Op::AddCarryChain{chain:CarryChain::Overflow,width:32,source:Operand::Memory(m),..} if m.base==Base::Eip&&m.rip_target==Some(Target::Address(0x100b))));
}
#[test] fn legacy_segment_address(){
 let i=one(Mode::X86,0,&[0x64,0x67,0x66,0x0f,0x38,0xf6,0x00]);assert_eq!(i.address_width,16);assert!(i.segment_override.is_some());assert!(matches!(i.op,Op::AddCarryChain{width:32,source:Operand::Memory(m),..} if m.base==Base::Register(3)&&m.index==Some(6)));
 let i=one(Mode::X86,0,&[0x67,0xc4,0xe2,0x73,0xf6,0x00]);assert!(matches!(i.op,Op::MultiplyUnsignedDouble{width:32,source:Operand::Memory(m),..} if m.base==Base::Register(3)&&m.index==Some(6)));
}
#[test] fn excluded_forms(){
 for (mode,b) in [(Mode::X64,&[0xc4,0xe2,0x71,0xf6,0xc0][..]),(Mode::X64,&[0xc4,0xe2,0x77,0xf6,0xc0]),(Mode::X86,&[0xc4,0xe2,0xf3,0xf6,0xc0]),(Mode::X64,&[0x0f,0x38,0xf6,0xc0]),(Mode::X64,&[0xf2,0x0f,0x38,0xf6,0xc0]),(Mode::X64,&[0x66,0xf3,0x0f,0x38,0xf6,0xc0]),(Mode::X64,&[0xf0,0x66,0x0f,0x38,0xf6,0x00]),(Mode::X64,&[0x64,0xf3,0x0f,0x38,0xf6,0xc0]),(Mode::X64,&[0xf3,0xc4,0xe2,0x73,0xf6,0xc0])]{let p=x86_decode::decode(mode,0,b).unwrap();assert_eq!(p.stop,Stop::Unsupported{offset:0},"{:x?}",b);assert_eq!(p.consumed,0);}
}
#[test] fn truncate_every_boundary(){
 for b in [&[0xc4,0x62,0xb3,0xf6,0x05,1,0,0,0][..],&[0xf3,0x4d,0x0f,0x38,0xf6,0xf4],&[0x66,0x48,0x0f,0x38,0xf6,0x44,0x24,0x80]]{for n in 1..b.len(){let p=x86_decode::decode(Mode::X64,0,&b[..n]).unwrap();assert_eq!(p.stop,Stop::Truncated{offset:0},"{:x?}",&b[..n]);}}
}
#[test] fn mixed_feature_metadata(){
 let p=x86_decode::decode(Mode::X64,0,&[0xc4,0xe2,0x73,0xf6,0xc3,0x66,0x0f,0x38,0xf6,0xc3,0xf3,0x0f,0x38,0xf6,0xc3,0x90]).unwrap();assert_eq!(p.stop,Stop::Complete);assert_eq!(p.instructions.iter().map(|i|(i.bmi_feature(),i.adx_feature())).collect::<Vec<_>>(),[(Some(CpuFeature::Bmi2),None),(None,Some(CpuFeature::Adx)),(None,Some(CpuFeature::Adx)),(None,None)]);
}
