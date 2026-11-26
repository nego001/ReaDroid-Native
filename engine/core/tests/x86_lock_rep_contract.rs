use negrodroid_core::x86_decode::{self,Mode,Op,Operand,Base,Target,Stop,Segment,StringKind,Repeat,BinaryKind};
fn one(mode:Mode,pc:u64,b:&[u8],aw:u8,seg:Option<Segment>,locked:bool)->Op{
 let p=x86_decode::decode(mode,pc,b).unwrap();assert_eq!(p.stop,Stop::Complete);assert_eq!(p.consumed,b.len());assert_eq!(p.instructions.len(),1);let i=&p.instructions[0];assert_eq!(i.bytes,b);assert_eq!(i.address_width,aw);assert_eq!(i.segment_override,seg);assert_eq!(i.locked,locked);i.op
}
#[test] fn string_kinds_and_widths(){
 for (opcode,kind) in [(0xa4,StringKind::Movs),(0xa6,StringKind::Cmps),(0xaa,StringKind::Stos),(0xac,StringKind::Lods),(0xae,StringKind::Scas)]{
  for (mode,aw) in [(Mode::X86,32),(Mode::X64,64)]{
   assert_eq!(one(mode,0,&[opcode],aw,None,false),Op::String{kind,width:8,repeat:Repeat::None});
   assert_eq!(one(mode,0,&[opcode+1],aw,None,false),Op::String{kind,width:32,repeat:Repeat::None});
   assert_eq!(one(mode,0,&[0x66,opcode+1],aw,None,false),Op::String{kind,width:16,repeat:Repeat::None});
  }
  assert_eq!(one(Mode::X64,0,&[0x48,opcode+1],64,None,false),Op::String{kind,width:64,repeat:Repeat::None});
 }
}
#[test] fn repeat_semantics(){
 for (op,kind) in [(0xa4,StringKind::Movs),(0xaa,StringKind::Stos),(0xac,StringKind::Lods)]{
  assert_eq!(one(Mode::X64,0,&[0xf3,op],64,None,false),Op::String{kind,width:8,repeat:Repeat::Rep});
 }
 for (op,kind) in [(0xa6,StringKind::Cmps),(0xae,StringKind::Scas)]{
  for (p,repeat) in [(0xf3,Repeat::Repe),(0xf2,Repeat::Repne)]{
   assert_eq!(one(Mode::X86,0,&[p,op+1],32,None,false),Op::String{kind,width:32,repeat});
  }
 }
}
#[test] fn address_width_independent_of_element_width(){
 assert_eq!(one(Mode::X86,0,&[0x67,0xf3,0xa5],16,None,false),Op::String{kind:StringKind::Movs,width:32,repeat:Repeat::Rep});
 assert_eq!(one(Mode::X64,0,&[0xf3,0x67,0x48,0xab],32,None,false),Op::String{kind:StringKind::Stos,width:64,repeat:Repeat::Rep});
}
#[test] fn source_segment_override(){
 assert_eq!(one(Mode::X64,0,&[0x64,0xf3,0x67,0xa4],32,Some(Segment::Fs),false),Op::String{kind:StringKind::Movs,width:8,repeat:Repeat::Rep});
 assert_eq!(one(Mode::X86,0,&[0x2e,0xf2,0xa7],32,Some(Segment::Cs),false),Op::String{kind:StringKind::Cmps,width:32,repeat:Repeat::Repne});
}
#[test] fn lock_memory_alu_matrix(){
 for (op,kind) in [(0x00,BinaryKind::Add),(0x08,BinaryKind::Or),(0x10,BinaryKind::Adc),(0x18,BinaryKind::Sbb),(0x20,BinaryKind::And),(0x28,BinaryKind::Sub),(0x30,BinaryKind::Xor)]{
  for reg in 0..8u8{for rm in [0,1,2,3,6,7]{
   assert!(matches!(one(Mode::X64,0,&[0xf0,op,reg<<3|rm],64,None,true),Op::Binary{kind:k,width:8,destination:Operand::Memory(_),..} if k==kind));
   assert!(matches!(one(Mode::X86,0,&[0xf0,op+1,reg<<3|rm],32,None,true),Op::Binary{kind:k,width:32,destination:Operand::Memory(_),..} if k==kind));
  }}
 }
}
#[test] fn lock_unary_and_immediate(){
 for m in [0x00,0x08]{assert!(matches!(one(Mode::X64,0,&[0xf0,0xff,m],64,None,true),Op::Unary{operand:Operand::Memory(_),..}));}
 for m in [0x10,0x18]{assert!(matches!(one(Mode::X64,0,&[0xf0,0xf6,m],64,None,true),Op::Unary{operand:Operand::Memory(_),..}));}
 assert!(matches!(one(Mode::X64,0x1000,&[0xf0,0x83,0x05,0,0,0,0,1],64,None,true),Op::BinaryImmediate{operand:Operand::Memory(m),..} if m.base==Base::Rip&&m.rip_target==Some(Target::Address(0x1008))));
}
#[test] fn lock_with_other_legacy_prefixes(){
 assert!(matches!(one(Mode::X64,0,&[0x65,0x67,0xf0,0x66,0x01,0x00],32,Some(Segment::Gs),true),Op::Binary{width:16,destination:Operand::Memory(_),..}));
}
#[test] fn invalid_prefix_combinations_stop(){
 for b in [&[0xf0,0x01,0xc0][..],&[0xf0,0x03,0x00],&[0xf0,0x39,0x00],&[0xf0,0x89,0x00],&[0xf0,0x85,0x00],&[0xf0,0xf7,0x20],&[0xf0,0xa4],&[0xf2,0xa4],&[0xf3,0x90],&[0xf2,0xf3,0xa6],&[0xf0,0xf0,0x01,0],&[0x64,0xf3,0xab],&[0x65,0xae],&[0x41,0xa5]]{
  let mut stream=vec![0x90];stream.extend(b);let p=x86_decode::decode(Mode::X64,0,&stream).unwrap();assert_eq!(p.stop,Stop::Unsupported{offset:1});assert_eq!(p.consumed,1);
 }
}
#[test] fn truncated_prefixes_and_lock_forms(){
 for b in [&[0xf3,0x67,0x48,0xa5][..],&[0xf0,0x48,0x83,0x05,0,0,0,0,1]]{
  for n in 1..b.len(){let p=x86_decode::decode(Mode::X64,0,&b[..n]).unwrap();assert_eq!(p.stop,Stop::Truncated{offset:0});assert_eq!(p.consumed,0);}
 }
}
#[test] fn no_prefix_leak(){
 let p=x86_decode::decode(Mode::X64,0,&[0xf0,0x01,0x00,0xf3,0xa4,0xa4,0x90]).unwrap();assert_eq!(p.stop,Stop::Complete);assert_eq!(p.instructions.iter().map(|i|i.locked).collect::<Vec<_>>(),[true,false,false,false]);assert_eq!(p.instructions[2].op,Op::String{kind:StringKind::Movs,width:8,repeat:Repeat::None});
}
