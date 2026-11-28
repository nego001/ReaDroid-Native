use negrodroid_core::x86_decode::{self,Mode,Op,VectorOperand,VectorWidth,CryptoKind,CpuFeature,Avx512Requirements,Base,Target,Stop};
fn one(mode:Mode,pc:u64,b:&[u8])->x86_decode::Instruction{
 let p=x86_decode::decode(mode,pc,b).unwrap();assert_eq!(p.stop,Stop::Complete,"{:x?}",b);assert_eq!(p.consumed,b.len());assert_eq!(p.instructions.len(),1);assert_eq!(p.instructions[0].bytes,b);p.instructions.into_iter().next().unwrap()
}
fn width(ll:u8)->VectorWidth{match ll{0=>VectorWidth::Bits128,1=>VectorWidth::Bits256,_=>VectorWidth::Bits512}}
#[test] fn vex_register_matrix(){
 for ll in 0..2u8{for (map,opcode,kind) in [(2,0xdc,CryptoKind::AesEncrypt),(2,0xdd,CryptoKind::AesEncryptLast),(2,0xde,CryptoKind::AesDecrypt),(2,0xdf,CryptoKind::AesDecryptLast),(3,0x44,CryptoKind::CarrylessMultiply)]{
  for d in 0..16u8{for a in 0..16u8{for r in 0..16u8{
   let mut b=vec![0xc4,(0xe0|map)^((d>>3)<<7)^((r>>3)<<5),((!a&15)<<3)|(ll<<2)|1,opcode,0xc0|((d&7)<<3)|(r&7)];
   let control=if map==3{b.push(0x11);Some(0x11)}else{None};
   let i=one(Mode::X64,0,&b);assert_eq!(i.op,Op::VectorCrypto{kind,width:width(ll),evex:false,destination:d,source1:a,source2:VectorOperand::Register(r),control});assert_eq!(i.avx_feature(),Some(CpuFeature::Avx));assert_eq!(i.avx512_requirements(),None);
   assert_eq!(i.crypto_feature(),Some(match (map,ll){(2,0)=>CpuFeature::Aes,(2,_)=>CpuFeature::Vaes,(3,0)=>CpuFeature::Pclmulqdq,_=>CpuFeature::Vpclmulqdq}));
  }}}
 }}
}
#[test] fn evex_register_matrix(){
 for ll in 0..3u8{for (map,opcode,kind) in [(2,0xdc,CryptoKind::AesEncrypt),(3,0x44,CryptoKind::CarrylessMultiply)]{
  for d in 0..32u8{for a in 0..32u8{for r in 0..32u8{
   let p0=(0xf0|map)^(((d>>3)&1)<<7)^(((d>>4)&1)<<4)^(((r>>3)&1)<<5)^(((r>>4)&1)<<6);
   let mut b=vec![0x62,p0,((!a&15)<<3)|5,(ll<<5)|((!(a>>4)&1)<<3),opcode,0xc0|((d&7)<<3)|(r&7)];
   let control=if map==3{b.push(0x10);Some(0x10)}else{None};
   let i=one(Mode::X64,0,&b);assert_eq!(i.op,Op::VectorCrypto{kind,width:width(ll),evex:true,destination:d,source1:a,source2:VectorOperand::Register(r),control});
   let feature=if map==3{CpuFeature::Vpclmulqdq}else{CpuFeature::Vaes};assert_eq!(i.crypto_feature(),Some(feature));assert_eq!(i.avx512_requirements(),Some(Avx512Requirements{extension:feature,vl:ll!=2}));
  }}}
 }}
}
#[test] fn pclmul_all_controls(){
 for ll in 0..2u8{for imm in 0..=255u8{assert!(matches!(one(Mode::X86,0,&[0xc4,0xe3,0x69|(ll<<2),0x44,0xcb,imm]).op,Op::VectorCrypto{control:Some(c),evex:false,..} if c==imm));}}
 for ll in 0..3u8{for imm in 0..=255u8{assert!(matches!(one(Mode::X64,0,&[0x62,0xf3,0x6d,(ll<<5)|8,0x44,0xcb,imm]).op,Op::VectorCrypto{control:Some(c),evex:true,..} if c==imm));}}
}
#[test] fn evex_tuple_displacements(){
 for ll in 0..3u8{for disp in 0..=255u8{let i=one(Mode::X64,0,&[0x62,0xf2,0x6d,(ll<<5)|8,0xdc,0x48,disp]);assert!(matches!(i.op,Op::VectorCrypto{source2:VectorOperand::Memory(m),..} if m.displacement==i64::from(disp as i8)*(16i64<<ll)));}}
}
#[test] fn assembler_aes_fixtures(){
 for (b,w,d,a,r,kind,evex) in [(&[0xc4,0xe2,0x69,0xdc,0xcb][..],0,1,2,3,CryptoKind::AesEncrypt,false),(&[0xc4,0x42,0x0d,0xdc,0xfd],1,15,14,13,CryptoKind::AesEncrypt,false),(&[0x62,0x02,0x0d,0x40,0xde,0xfd],2,31,30,29,CryptoKind::AesDecrypt,true),(&[0x62,0x02,0x0d,0x00,0xdc,0xfd],0,31,30,29,CryptoKind::AesEncrypt,true),(&[0x62,0x02,0x0d,0x20,0xdc,0xfd],1,31,30,29,CryptoKind::AesEncrypt,true)]{
  assert_eq!(one(Mode::X64,0,b).op,Op::VectorCrypto{kind,width:width(w),evex,destination:d,source1:a,source2:VectorOperand::Register(r),control:None});
 }
 for (b,kind,disp) in [(&[0x62,0xf2,0x6d,0x48,0xdd,0x48,0x7f][..],CryptoKind::AesEncryptLast,8128),(&[0x62,0xf2,0x6d,0x48,0xdf,0x48,0x80],CryptoKind::AesDecryptLast,-8192)]{assert!(matches!(one(Mode::X64,0,b).op,Op::VectorCrypto{kind:k,source2:VectorOperand::Memory(m),..} if k==kind&&m.displacement==disp));}
}
#[test] fn assembler_pclmul_fixtures(){
 for (b,w,d,a,r,evex,control) in [(&[0xc4,0xe3,0x69,0x44,0xcb,0x11][..],0,1,2,3,false,0x11),(&[0x62,0x03,0x0d,0x40,0x44,0xfd,0x10],2,31,30,29,true,0x10),(&[0x62,0x03,0x0d,0x00,0x44,0xfd,0x11],0,31,30,29,true,0x11),(&[0x62,0x03,0x0d,0x20,0x44,0xfd,0x11],1,31,30,29,true,0x11)]{
  assert_eq!(one(Mode::X64,0,b).op,Op::VectorCrypto{kind:CryptoKind::CarrylessMultiply,width:width(w),evex,destination:d,source1:a,source2:VectorOperand::Register(r),control:Some(control)});
 }
 assert!(matches!(one(Mode::X64,0,&[0xc4,0xe3,0x6d,0x44,0x48,0x20,1]).op,Op::VectorCrypto{source2:VectorOperand::Memory(m),control:Some(1),..} if m.displacement==32));
 assert!(matches!(one(Mode::X64,0x1000,&[0x62,0xf3,0x6d,0x48,0x44,0x0d,1,0,0,0,0x11]).op,Op::VectorCrypto{source2:VectorOperand::Memory(m),control:Some(0x11),..} if m.base==Base::Rip&&m.rip_target==Some(Target::Address(0x100c))));
}
#[test] fn memory_and_final_length(){
 let i=one(Mode::X64,0x1_0000_1000,&[0x64,0x67,0x62,0xf3,0x6d,0x28,0x44,0x0d,1,0,0,0,3]);assert_eq!(i.address_width,32);assert!(i.segment_override.is_some());assert!(matches!(i.op,Op::VectorCrypto{source2:VectorOperand::Memory(m),..} if m.base==Base::Eip&&m.rip_target==Some(Target::Address(0x100e))));
 let i=one(Mode::X64,0,&[0x62,0xf2,0x6d,0x48,0xdc,0x88,1,0,0,0]);assert!(matches!(i.op,Op::VectorCrypto{source2:VectorOperand::Memory(m),..} if m.displacement==1));
}
#[test] fn reserved_and_excluded(){
 for (mode,b) in [(Mode::X64,&[0x62,0xf2,0x6d,0x49,0xdc,0xc0][..]),(Mode::X64,&[0x62,0xf2,0x6d,0xc9,0xdc,0xc0]),(Mode::X64,&[0x62,0xf2,0x6d,0x58,0xdc,0x00]),(Mode::X64,&[0x62,0xf2,0x6d,0x68,0xdc,0xc0]),(Mode::X64,&[0x62,0xf2,0xed,0x48,0xdc,0xc0]),(Mode::X64,&[0x62,0xf3,0x6c,0x48,0x44,0xc0,0]),(Mode::X64,&[0x62,0xf2,0x6d,0x48,0xdb,0xc0]),(Mode::X64,&[0xc4,0xe2,0xe9,0xdc,0xc0]),(Mode::X86,&[0x62,0xf2,0x6d,0x48,0xdc,0xc0]),(Mode::X64,&[0x64,0xc4,0xe2,0x69,0xdc,0xc0])]{let p=x86_decode::decode(mode,0,b).unwrap();assert_eq!(p.stop,Stop::Unsupported{offset:0},"{:x?}",b);assert_eq!(p.consumed,0);}
}
#[test] fn truncation(){
 for b in [&[0xc4,0xe3,0x6d,0x44,0x48,0x20,1][..],&[0x62,0xf3,0x6d,0x48,0x44,0x0d,1,0,0,0,0x11],&[0x62,0x02,0x0d,0x40,0xde,0xfd]]{for n in 1..b.len(){let p=x86_decode::decode(Mode::X64,0,&b[..n]).unwrap();assert_eq!(p.stop,Stop::Truncated{offset:0},"{:x?}",&b[..n]);}}
}
#[test] fn feature_stream(){
 let p=x86_decode::decode(Mode::X64,0,&[0x66,0x0f,0x38,0xdc,0xc0,0xc4,0xe2,0x69,0xdc,0xcb,0xc4,0xe2,0x6d,0xdc,0xcb,0x62,0xf3,0x6d,0x48,0x44,0xcb,0,0x90]).unwrap();assert_eq!(p.stop,Stop::Complete);
 assert_eq!(p.instructions.iter().map(|i|i.crypto_feature()).collect::<Vec<_>>(),[Some(CpuFeature::Aes),Some(CpuFeature::Aes),Some(CpuFeature::Vaes),Some(CpuFeature::Vpclmulqdq),None]);
 assert_eq!(p.instructions.iter().map(|i|i.avx_feature()).collect::<Vec<_>>(),[None,Some(CpuFeature::Avx),Some(CpuFeature::Avx),Some(CpuFeature::Avx512F),None]);
}
