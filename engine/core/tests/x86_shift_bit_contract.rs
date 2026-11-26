use negrodroid_core::x86_decode::{self,Mode,Op,Operand,Base,Target,Stop,ShiftKind,ShiftCount,BitKind,BitIndex,Segment};
fn one(mode:Mode,pc:u64,b:&[u8])->x86_decode::Instruction{
 let p=x86_decode::decode(mode,pc,b).unwrap();assert_eq!(p.stop,Stop::Complete);assert_eq!(p.consumed,b.len());assert_eq!(p.instructions.len(),1);assert_eq!(p.instructions[0].bytes,b);p.instructions.into_iter().next().unwrap()
}
#[test] fn shift_all_selectors_counts(){
 for (sel,kind) in [(0,ShiftKind::Rol),(1,ShiftKind::Ror),(2,ShiftKind::Rcl),(3,ShiftKind::Rcr),(4,ShiftKind::Shl),(5,ShiftKind::Shr),(7,ShiftKind::Sar)]{
  for raw in 0..=255u8{
   for (mode,pre,width) in [(Mode::X86,&[][..],32),(Mode::X86,&[0x66][..],16),(Mode::X64,&[0x48][..],64)]{
    let mut b=pre.to_vec();b.extend([0xc1,0xc0|(sel<<3),raw]);assert_eq!(one(mode,0,&b).op,Op::Shift{kind,width,operand:Operand::Register(0),count:ShiftCount::Immediate(raw)});
   }
  }
  assert_eq!(one(Mode::X86,0,&[0xd1,0xc0|(sel<<3)]).op,Op::Shift{kind,width:32,operand:Operand::Register(0),count:ShiftCount::One});
  assert_eq!(one(Mode::X86,0,&[0xd3,0xc0|(sel<<3)]).op,Op::Shift{kind,width:32,operand:Operand::Register(0),count:ShiftCount::Cl});
 }
}
#[test] fn shift_byte_registers(){
 for (pre,operand) in [(&[][..],Operand::HighByte(0)),(&[0x40][..],Operand::Register(4)),(&[0x41][..],Operand::Register(12))]{
  let mut b=pre.to_vec();b.extend([0xc0,0xe4,0xff]);assert_eq!(one(Mode::X64,0,&b).op,Op::Shift{kind:ShiftKind::Shl,width:8,operand,count:ShiftCount::Immediate(255)});
 }
 assert_eq!(one(Mode::X64,0,&[0xd0,0xe8]).op,Op::Shift{kind:ShiftKind::Shr,width:8,operand:Operand::Register(0),count:ShiftCount::One});
 assert_eq!(one(Mode::X64,0,&[0xd2,0xf8]).op,Op::Shift{kind:ShiftKind::Sar,width:8,operand:Operand::Register(0),count:ShiftCount::Cl});
}
#[test] fn shift_rip_uses_final_length(){
 assert!(matches!(one(Mode::X64,0x1000,&[0x48,0xc1,0x25,0,0,0,0,3]).op,Op::Shift{operand:Operand::Memory(m),count:ShiftCount::Immediate(3),..} if m.base==Base::Rip&&m.rip_target==Some(Target::Address(0x1008))));
}
#[test] fn double_shift_register_forms(){
 for (opcode,right,count) in [(0xa4,false,ShiftCount::Immediate(200)),(0xa5,false,ShiftCount::Cl),(0xac,true,ShiftCount::Immediate(200)),(0xad,true,ShiftCount::Cl)]{
  let mut b=vec![0x4d,0x0f,opcode,0xc1];if opcode&1==0{b.push(200);}
  assert_eq!(one(Mode::X64,0,&b).op,Op::DoubleShift{right,width:64,destination:Operand::Register(9),source:8,count});
 }
}
#[test] fn double_shift_memory_address_size(){
 let i=one(Mode::X86,0,&[0x64,0x67,0x66,0x0f,0xa4,0x00,0x10]);assert_eq!(i.address_width,16);assert_eq!(i.segment_override,Some(Segment::Fs));
 assert!(matches!(i.op,Op::DoubleShift{width:16,destination:Operand::Memory(m),count:ShiftCount::Immediate(16),..} if m.base==Base::Register(3)&&m.index==Some(6)));
}
#[test] fn bit_register_and_immediate_forms(){
 for (op,sel,kind) in [(0xa3,4,BitKind::Test),(0xab,5,BitKind::Set),(0xb3,6,BitKind::Reset),(0xbb,7,BitKind::Complement)]{
  assert_eq!(one(Mode::X64,0,&[0x4d,0x0f,op,0xc1]).op,Op::Bit{kind,width:64,operand:Operand::Register(9),index:BitIndex::Register(8)});
  for raw in 0..=255u8{assert_eq!(one(Mode::X86,0,&[0x66,0x0f,0xba,0xc0|(sel<<3),raw]).op,Op::Bit{kind,width:16,operand:Operand::Register(0),index:BitIndex::Immediate(raw)});}
 }
}
#[test] fn bit_lock_only_mutating_memory(){
 for op in [0xab,0xb3,0xbb]{let i=one(Mode::X64,0,&[0xf0,0x0f,op,0x00]);assert!(i.locked);assert!(matches!(i.op,Op::Bit{operand:Operand::Memory(_),..}));}
 let i=one(Mode::X64,0x1000,&[0xf0,0x0f,0xba,0x2d,0,0,0,0,31]);assert!(i.locked);
 assert!(matches!(i.op,Op::Bit{operand:Operand::Memory(m),index:BitIndex::Immediate(31),..} if m.rip_target==Some(Target::Address(0x1009))));
}
#[test] fn bit_scan_widths(){
 for (opcode,reverse) in [(0xbc,false),(0xbd,true)]{
  assert_eq!(one(Mode::X86,0,&[0x66,0x0f,opcode,0xc1]).op,Op::BitScan{reverse,width:16,destination:0,source:Operand::Register(1)});
  assert_eq!(one(Mode::X64,0,&[0x4d,0x0f,opcode,0xc1]).op,Op::BitScan{reverse,width:64,destination:8,source:Operand::Register(9)});
 }
}
#[test] fn reject_invalid_prefix_and_selectors(){
 for b in [&[0xc1,0xf0,1][..],&[0x44,0xd1,0xe0],&[0x0f,0xba,0xd8,1],&[0x44,0x0f,0xba,0xe8,1],&[0xf0,0xd1,0x20],&[0xf0,0x0f,0xa3,0],&[0xf0,0x0f,0xab,0xc0],&[0xf3,0x0f,0xbc,0xc0],&[0xf3,0x0f,0xbd,0xc0]]{
  let mut stream=vec![0x90];stream.extend(b);let p=x86_decode::decode(Mode::X64,0,&stream).unwrap();assert_eq!(p.stop,Stop::Unsupported{offset:1});assert_eq!(p.consumed,1);
 }
}
#[test] fn truncation_at_every_boundary(){
 for b in [&[0x48,0xc1,0x25,0,0,0,0,3][..],&[0x48,0x0f,0xa4,0x05,0,0,0,0,1],&[0xf0,0x0f,0xba,0x2d,0,0,0,0,31]]{
  for n in 1..b.len(){let p=x86_decode::decode(Mode::X64,0,&b[..n]).unwrap();assert_eq!(p.stop,Stop::Truncated{offset:0});assert_eq!(p.consumed,0);}
 }
}
