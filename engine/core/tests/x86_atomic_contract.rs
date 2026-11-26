use negrodroid_core::x86_decode::{self,Mode,Op,Operand,Base,Target,Stop,ExchangeKind,FenceKind,LockKind,Segment};
fn one(mode:Mode,pc:u64,b:&[u8])->x86_decode::Instruction{
 let p=x86_decode::decode(mode,pc,b).unwrap();assert_eq!(p.stop,Stop::Complete);assert_eq!(p.consumed,b.len());assert_eq!(p.instructions.len(),1);assert_eq!(p.instructions[0].bytes,b);p.instructions.into_iter().next().unwrap()
}
#[test] fn exchange_register_matrix(){
 for (op,kind) in [(&[0x87][..],ExchangeKind::Xchg),(&[0x0f,0xc1][..],ExchangeKind::Xadd),(&[0x0f,0xb1][..],ExchangeKind::Cmpxchg)]{
  for dst in 0..16u8{for src in 0..16u8{
   let mut b=vec![0x48|((src>>3)<<2)|(dst>>3)];b.extend(op);b.push(0xc0|((src&7)<<3)|(dst&7));
   let i=one(Mode::X64,0,&b);assert_eq!(i.lock_kind(),LockKind::None);assert_eq!(i.op,Op::Exchange{kind,width:64,destination:Operand::Register(dst),source:Operand::Register(src)});
  }}
 }
}
#[test] fn byte_register_rex_semantics(){
 for (pre,dest,src) in [(&[][..],Operand::HighByte(1),Operand::HighByte(0)),(&[0x40][..],Operand::Register(5),Operand::Register(4)),(&[0x45][..],Operand::Register(13),Operand::Register(12))]{
  for (op,kind) in [(&[0x86][..],ExchangeKind::Xchg),(&[0x0f,0xc0][..],ExchangeKind::Xadd),(&[0x0f,0xb0][..],ExchangeKind::Cmpxchg)]{
   let mut b=pre.to_vec();b.extend(op);b.push(0xe5);assert_eq!(one(Mode::X64,0,&b).op,Op::Exchange{kind,width:8,destination:dest,source:src});
  }
 }
}
#[test] fn accumulator_short_forms(){
 for reg in 1..8u8{
  for (mode,pre,width,source) in [(Mode::X86,&[][..],32,reg),(Mode::X86,&[0x66][..],16,reg),(Mode::X64,&[0x49][..],64,reg+8)]{
   let mut b=pre.to_vec();b.push(0x90|reg);assert_eq!(one(mode,0,&b).op,Op::Exchange{kind:ExchangeKind::Xchg,width,destination:Operand::Register(0),source:Operand::Register(source)});
  }
 }
}
#[test] fn implicit_vs_explicit_lock(){
 for (op,kind) in [(&[0x87][..],ExchangeKind::Xchg),(&[0x0f,0xc1][..],ExchangeKind::Xadd),(&[0x0f,0xb1][..],ExchangeKind::Cmpxchg)]{
  for explicit in [false,true]{
   let mut b=if explicit{vec![0xf0]}else{vec![]};b.extend(op);b.push(0);
   let i=one(Mode::X64,0,&b);assert_eq!(i.locked,explicit);assert_eq!(i.lock_kind(),if explicit{LockKind::Explicit}else if kind==ExchangeKind::Xchg{LockKind::Implicit}else{LockKind::None});
  }
 }
}
#[test] fn pair_widths_and_memory_only(){
 for (mode,pre,width) in [(Mode::X86,&[][..],64),(Mode::X64,&[][..],64),(Mode::X64,&[0x48][..],128)]{
  for locked in [false,true]{let mut b=if locked{vec![0xf0]}else{vec![]};b.extend(pre);b.extend([0x0f,0xc7,0x08]);let i=one(mode,0,&b);assert_eq!(i.lock_kind(),if locked{LockKind::Explicit}else{LockKind::None});assert!(matches!(i.op,Op::CompareExchangePair{width:w,memory} if w==width&&memory.base==Base::Register(0)));}
 }
}
#[test] fn pair_rip_and_segment_address(){
 let i=one(Mode::X64,0x1000,&[0xf0,0x48,0x0f,0xc7,0x0d,0,0,0,0]);assert!(matches!(i.op,Op::CompareExchangePair{width:128,memory} if memory.rip_target==Some(Target::Address(0x1009))));
 let i=one(Mode::X86,0,&[0x64,0x67,0x0f,0xc7,0x08]);assert_eq!(i.address_width,16);assert_eq!(i.segment_override,Some(Segment::Fs));assert!(matches!(i.op,Op::CompareExchangePair{width:64,memory} if memory.base==Base::Register(3)&&memory.index==Some(6)));
}
#[test] fn canonical_fences(){
 for mode in [Mode::X86,Mode::X64]{for (raw,kind) in [(0xe8,FenceKind::Load),(0xf0,FenceKind::Full),(0xf8,FenceKind::Store)]{let i=one(mode,0,&[0x0f,0xae,raw]);assert_eq!(i.op,Op::Fence{kind});assert_eq!(i.lock_kind(),LockKind::None);}}
}
#[test] fn rejects_unsupported_forms(){
 for b in [&[0xf0,0x87,0xc0][..],&[0xf0,0x91],&[0xf0,0x0f,0xc1,0xc0],&[0x0f,0xc7,0xc8],&[0x0f,0xc7,0x00],&[0x66,0x0f,0xc7,0x08],&[0x44,0x0f,0xc7,0x08],&[0xf0,0x0f,0xae,0xf0],&[0x0f,0xae,0xf1],&[0x66,0x0f,0xae,0xe8],&[0xf3,0x90],&[0x48,0x90]]{
  let mut stream=vec![0x90];stream.extend(b);let p=x86_decode::decode(Mode::X64,0,&stream).unwrap();assert_eq!(p.stop,Stop::Unsupported{offset:1});assert_eq!(p.consumed,1);
 }
}
#[test] fn truncation_all_boundaries(){
 for b in [&[0xf0,0x48,0x0f,0xc7,0x0d,0,0,0,0][..],&[0x48,0x0f,0xb1,0x44,0x24,0xff],&[0x0f,0xae,0xe8]]{for n in 1..b.len(){let p=x86_decode::decode(Mode::X64,0,&b[..n]).unwrap();assert_eq!(p.stop,Stop::Truncated{offset:0});assert_eq!(p.consumed,0);}}
}
#[test] fn lock_metadata_does_not_leak(){
 let p=x86_decode::decode(Mode::X64,0,&[0x87,0x00,0xf0,0x0f,0xc1,0x00,0x87,0xc0,0x0f,0xae,0xf8,0x90]).unwrap();assert_eq!(p.stop,Stop::Complete);assert_eq!(p.instructions.iter().map(|i|i.lock_kind()).collect::<Vec<_>>(),[LockKind::Implicit,LockKind::Explicit,LockKind::None,LockKind::None,LockKind::None]);
}
