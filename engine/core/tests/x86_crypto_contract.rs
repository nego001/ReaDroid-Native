use negrodroid_core::x86_decode::{self,Mode,Op,XmmOperand,CryptoKind,CpuFeature,Base,Target,Stop};
fn one(mode:Mode,pc:u64,b:&[u8])->x86_decode::Instruction{
 let p=x86_decode::decode(mode,pc,b).unwrap();assert_eq!(p.stop,Stop::Complete,"{:x?}",b);assert_eq!(p.consumed,b.len());assert_eq!(p.instructions.len(),1);assert_eq!(p.instructions[0].bytes,b);p.instructions.into_iter().next().unwrap()
}
#[test] fn aes_register_matrix(){
 for (opcode,kind) in [(0xdb,CryptoKind::AesInverseMix),(0xdc,CryptoKind::AesEncrypt),(0xdd,CryptoKind::AesEncryptLast),(0xde,CryptoKind::AesDecrypt),(0xdf,CryptoKind::AesDecryptLast)]{for d in 0..16u8{for r in 0..16u8{
  let b=[0x66,0x40|((d>>3)<<2)|(r>>3),0x0f,0x38,opcode,0xc0|((d&7)<<3)|(r&7)];
  let i=one(Mode::X64,0,&b);assert_eq!(i.op,Op::CryptoXmm{kind,destination:d,source:XmmOperand::Register(r),control:None,implicit_xmm0:false});assert_eq!(i.crypto_feature(),Some(CpuFeature::Aes));assert_eq!(i.sse_feature(),None);
 }}}
}
#[test] fn sha_register_matrix(){
 for (opcode,kind) in [(0xc8,CryptoKind::Sha1NextE),(0xc9,CryptoKind::Sha1Message1),(0xca,CryptoKind::Sha1Message2),(0xcb,CryptoKind::Sha256Rounds2),(0xcc,CryptoKind::Sha256Message1),(0xcd,CryptoKind::Sha256Message2)]{for d in 0..16u8{for r in 0..16u8{
  let b=[0x40|((d>>3)<<2)|(r>>3),0x0f,0x38,opcode,0xc0|((d&7)<<3)|(r&7)];
  let i=one(Mode::X64,0,&b);assert_eq!(i.op,Op::CryptoXmm{kind,destination:d,source:XmmOperand::Register(r),control:None,implicit_xmm0:opcode==0xcb});assert_eq!(i.crypto_feature(),Some(CpuFeature::Sha));
 }}}
}
#[test] fn all_encoded_controls(){
 for (opcode,kind,feature) in [(0xdf,CryptoKind::AesKeygen,CpuFeature::Aes),(0x44,CryptoKind::CarrylessMultiply,CpuFeature::Pclmulqdq),(0xcc,CryptoKind::Sha1Rounds4,CpuFeature::Sha)]{for control in 0..=255u8{
  let mut b=vec![];if opcode!=0xcc{b.push(0x66);}b.extend([0x0f,0x3a,opcode,0xca,control]);
  let i=one(Mode::X86,0,&b);assert_eq!(i.op,Op::CryptoXmm{kind,destination:1,source:XmmOperand::Register(2),control:Some(control),implicit_xmm0:false});assert_eq!(i.crypto_feature(),Some(feature));
 }}
}
#[test] fn assembler_aes_and_pclmul(){
 for (b,kind,d,r,control) in [(&[0x66,0x45,0x0f,0x38,0xdc,0xfd][..],CryptoKind::AesEncrypt,15,13,None),(&[0x66,0x45,0x0f,0x38,0xdb,0xc1],CryptoKind::AesInverseMix,8,9,None),(&[0x66,0x0f,0x3a,0xdf,0xca,0x1b],CryptoKind::AesKeygen,1,2,Some(0x1b)),(&[0x66,0x0f,0x3a,0x44,0xdc,0x11],CryptoKind::CarrylessMultiply,3,4,Some(0x11))]{
  assert_eq!(one(Mode::X64,0,b).op,Op::CryptoXmm{kind,destination:d,source:XmmOperand::Register(r),control,implicit_xmm0:false});
 }
}
#[test] fn assembler_sha(){
 assert_eq!(one(Mode::X64,0,&[0x45,0x0f,0x38,0xcb,0xfd]).op,Op::CryptoXmm{kind:CryptoKind::Sha256Rounds2,destination:15,source:XmmOperand::Register(13),control:None,implicit_xmm0:true});
 assert_eq!(one(Mode::X64,0,&[0x0f,0x3a,0xcc,0xca,3]).op,Op::CryptoXmm{kind:CryptoKind::Sha1Rounds4,destination:1,source:XmmOperand::Register(2),control:Some(3),implicit_xmm0:false});
 assert!(matches!(one(Mode::X64,0,&[0x0f,0x38,0xc8,0x50,0x10]).op,Op::CryptoXmm{kind:CryptoKind::Sha1NextE,destination:2,source:XmmOperand::Memory(m),..} if m.base==Base::Register(0)&&m.displacement==16));
}
#[test] fn immediate_rip_and_eip(){
 let i=one(Mode::X64,0x1000,&[0x66,0x0f,0x3a,0x44,0x05,1,0,0,0,0x11]);assert!(matches!(i.op,Op::CryptoXmm{source:XmmOperand::Memory(m),control:Some(0x11),..} if m.base==Base::Rip&&m.rip_target==Some(Target::Address(0x100b))));
 let i=one(Mode::X64,0x1_0000_1000,&[0x67,0x0f,0x3a,0xcc,0x05,1,0,0,0,3]);assert!(matches!(i.op,Op::CryptoXmm{source:XmmOperand::Memory(m),control:Some(3),..} if m.base==Base::Eip&&m.rip_target==Some(Target::Address(0x100b))));
}
#[test] fn legacy_address_and_segment(){
 let i=one(Mode::X86,0,&[0x64,0x67,0x0f,0x38,0xcb,0x00]);assert_eq!(i.address_width,16);assert!(i.segment_override.is_some());assert!(matches!(i.op,Op::CryptoXmm{source:XmmOperand::Memory(m),implicit_xmm0:true,..} if m.base==Base::Register(3)&&m.index==Some(6)));
}
#[test] fn excluded_forms(){
 for b in [&[0x0f,0x38,0xdc,0xc0][..],&[0x66,0x0f,0x38,0xcb,0xc0],&[0xf3,0x0f,0x38,0xcb,0xc0],&[0x66,0x48,0x0f,0x38,0xdc,0xc0],&[0xf0,0x66,0x0f,0x38,0xdc,0x00],&[0x64,0x0f,0x38,0xcb,0xc0],&[0x66,0x0f,0x3a,0xcc,0xc0,1],&[0xc4,0xe2,0x68,0xdc,0xc0]]{let p=x86_decode::decode(Mode::X64,0,b).unwrap();assert_eq!(p.stop,Stop::Unsupported{offset:0},"{:x?}",b);assert_eq!(p.consumed,0);}
}
#[test] fn truncate_every_boundary(){
 for b in [&[0x66,0x0f,0x3a,0x44,0x05,1,0,0,0,0x11][..],&[0x0f,0x3a,0xcc,0xca,3],&[0x45,0x0f,0x38,0xcb,0xfd]]{for n in 1..b.len(){let p=x86_decode::decode(Mode::X64,0,&b[..n]).unwrap();assert_eq!(p.stop,Stop::Truncated{offset:0},"{:x?}",&b[..n]);}}
}
#[test] fn mixed_feature_metadata(){
 let p=x86_decode::decode(Mode::X64,0,&[0x66,0x0f,0x38,0xdc,0xc0,0x66,0x0f,0x3a,0x44,0xc0,0,0x0f,0x38,0xcb,0xc0,0x90]).unwrap();assert_eq!(p.stop,Stop::Complete);assert_eq!(p.instructions.iter().map(|i|i.crypto_feature()).collect::<Vec<_>>(),[Some(CpuFeature::Aes),Some(CpuFeature::Pclmulqdq),Some(CpuFeature::Sha),None]);
}
