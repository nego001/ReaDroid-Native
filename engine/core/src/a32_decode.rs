//! Selected little-endian A32 encodings, not Thumb or a full ISA validator.
//! No execution, memory dereference, instruction boundary inference or aliases.
use crate::ReadSession;
use std::io::{self,Read,Seek};
pub const MAX_INSTRUCTIONS:usize=1024;
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Target{Address(u32),Overflow}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum DataKind{And,Eor,Sub,Rsb,Add,Adc,Sbc,Rsc,Tst,Teq,Cmp,Cmn,Orr,Mov,Bic,Mvn}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Shift{Lsl(u8),Lsr(u8),Asr(u8),Ror(u8),Rrx}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Op{
    Unknown,Nop,
    DataRegister{kind:DataKind,set_flags:bool,destination:Option<u8>,source:Option<u8>,operand:u8,shift:Shift},
    Multiply{set_flags:bool,destination:u8,left:u8,right:u8,accumulator:Option<u8>},
    MemoryRegister{load:bool,byte:bool,base:u8,register:u8,offset:u8,add:bool,shift:Shift},
    MemoryWriteback{load:bool,byte:bool,base:u8,register:u8,pre:bool,displacement:i32},
    BlockTransfer{load:bool,pre:bool,increment:bool,writeback:bool,base:u8,list:u16},
    Branch{link:bool,target:Target},
    Exchange{link:bool,register:u8},
    DataImmediate{kind:DataKind,set_flags:bool,destination:Option<u8>,source:Option<u8>,imm8:u8,rotate:u8,value:u32},
    MemoryImmediate{load:bool,byte:bool,base:u8,register:u8,displacement:i32},
}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub struct Instruction{pub address:u32,pub word:u32,pub condition:u8,pub op:Op}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Error{Length,Alignment,AddressOverflow}
fn branch_target(pc:u32,w:u32)->Target{
    let signed=((i64::from(w&0xffffff)<<40)>>40)*4;
    // Checked coordinates, not wrapping CPU address arithmetic.
    let v=i64::from(pc)+8+signed;
    match u32::try_from(v){Ok(v)=>Target::Address(v),Err(_)=>Target::Overflow}
}
fn shift_immediate(x:u32)->Shift{
    let n=((x>>7)&31) as u8;
    match ((x>>5)&3,n){
        (0,n)=>Shift::Lsl(n),(1,0)=>Shift::Lsr(32),(1,n)=>Shift::Lsr(n),
        (2,0)=>Shift::Asr(32),(2,n)=>Shift::Asr(n),(3,0)=>Shift::Rrx,(_,n)=>Shift::Ror(n),
    }
}
fn data_kind(k:u32)->DataKind{
    [DataKind::And,DataKind::Eor,DataKind::Sub,DataKind::Rsb,DataKind::Add,DataKind::Adc,
        DataKind::Sbc,DataKind::Rsc,DataKind::Tst,DataKind::Teq,DataKind::Cmp,DataKind::Cmn,
        DataKind::Orr,DataKind::Mov,DataKind::Bic,DataKind::Mvn][k as usize]
}
fn op(pc:u32,w:u32)->Op{
    if w>>28==15{return Op::Unknown;}
    let x=w&0x0fffffff;
    if x==0x0320f000{return Op::Nop;}
    if x&0x0e000000==0x0a000000{
        return Op::Branch{link:x&(1<<24)!=0,target:branch_target(pc,w)};
    }
    match x&0x0ffffff0{
        0x012fff10=>return Op::Exchange{link:false,register:(x&15) as u8},
        0x012fff30=>return Op::Exchange{link:true,register:(x&15) as u8},
        _=>{}
    }
    if x&0x0e000000==0x02000000{
        let k=(x>>21)&15;let flags=x&(1<<20)!=0;
        let rn=((x>>16)&15) as u8;let rd=((x>>12)&15) as u8;
        let test=(8..=11).contains(&k);let unary=k==13||k==15;
        if (test&&(!flags||rd!=0))||(unary&&rn!=0){return Op::Unknown;}
        // Exclude PC operands and exception-return forms from this subset.
        if (!test&&rd==15)||(!unary&&rn==15){return Op::Unknown;}
        let kind=[DataKind::And,DataKind::Eor,DataKind::Sub,DataKind::Rsb,DataKind::Add,DataKind::Adc,
            DataKind::Sbc,DataKind::Rsc,DataKind::Tst,DataKind::Teq,DataKind::Cmp,DataKind::Cmn,
            DataKind::Orr,DataKind::Mov,DataKind::Bic,DataKind::Mvn][k as usize];
        let imm8=(x&255) as u8;let rotate=(((x>>8)&15)*2) as u8;
        return Op::DataImmediate{kind,set_flags:flags,destination:(!test).then_some(rd),
            source:(!unary).then_some(rn),imm8,rotate,value:u32::from(imm8).rotate_right(u32::from(rotate))};
    }
    // Immediate pre-indexed single transfers without writeback.
    if x&0x0f200000==0x05000000{
        let base=((x>>16)&15) as u8;let register=((x>>12)&15) as u8;
        // No PC literal/branch semantics in this initial memory subset.
        if base==15||register==15{return Op::Unknown;}
        let imm=(x&4095) as i32;
        return Op::MemoryImmediate{load:x&(1<<20)!=0,byte:x&(1<<22)!=0,base,register,
            displacement:if x&(1<<23)!=0{imm}else{-imm}};
    }
    // Classic data-processing register with immediate shift. Exclude
    // register-controlled shifts, miscellaneous opcodes and PC operands.
    if x&0x0e000010==0{
        let k=(x>>21)&15;let flags=x&(1<<20)!=0;
        let rn=((x>>16)&15) as u8;let rd=((x>>12)&15) as u8;let rm=(x&15) as u8;
        let test=(8..=11).contains(&k);let unary=k==13||k==15;
        if (test&&(!flags||rd!=0))||(unary&&rn!=0)||(!test&&rd==15)||(!unary&&rn==15)||rm==15{
            return Op::Unknown;
        }
        return Op::DataRegister{kind:data_kind(k),set_flags:flags,destination:(!test).then_some(rd),
            source:(!unary).then_some(rn),operand:rm,shift:shift_immediate(x)};
    }
    // MUL/MLA classic encoding, no widening, DSP or PC operands.
    if x&0x0fc000f0==0x00000090{
        let accumulate=x&(1<<21)!=0;let flags=x&(1<<20)!=0;
        let rd=((x>>16)&15) as u8;let ra=((x>>12)&15) as u8;
        let rs=((x>>8)&15) as u8;let rm=(x&15) as u8;
        if rd==15||rs==15||rm==15||(accumulate&&ra==15)||(!accumulate&&ra!=0){return Op::Unknown;}
        return Op::Multiply{set_flags:flags,destination:rd,left:rm,right:rs,accumulator:accumulate.then_some(ra)};
    }
    // Single-transfer register offset, pre-index without writeback.
    if x&0x0f200010==0x07000000{
        let base=((x>>16)&15) as u8;let register=((x>>12)&15) as u8;let offset=(x&15) as u8;
        if base==15||register==15||offset==15{return Op::Unknown;}
        return Op::MemoryRegister{load:x&(1<<20)!=0,byte:x&(1<<22)!=0,base,register,offset,
            add:x&(1<<23)!=0,shift:shift_immediate(x)};
    }
    // Immediate single-transfer writeback/post-index (not unprivileged).
    if x&0x0e000000==0x04000000{
        let pre=x&(1<<24)!=0;let wback=x&(1<<21)!=0;
        if pre!=wback{return Op::Unknown;} // pre without writeback handled above; P=0,W=1 unprivileged
        let base=((x>>16)&15) as u8;let register=((x>>12)&15) as u8;
        if base==15||register==15||base==register{return Op::Unknown;}
        let imm=(x&4095) as i32;
        return Op::MemoryWriteback{load:x&(1<<20)!=0,byte:x&(1<<22)!=0,base,register,
            pre,displacement:if x&(1<<23)!=0{imm}else{-imm}};
    }
    // Block transfer with ordinary register list, no user-bank/exception
    // return, PC in list or writeback with base in list.
    if x&0x0e400000==0x08000000{
        let base=((x>>16)&15) as u8;let list=(x&0xffff) as u16;let writeback=x&(1<<21)!=0;
        if base==15||list==0||list&0x8000!=0||(writeback&&list&(1u16<<base)!=0){return Op::Unknown;}
        return Op::BlockTransfer{load:x&(1<<20)!=0,pre:x&(1<<24)!=0,increment:x&(1<<23)!=0,
            writeback,base,list};
    }
    Op::Unknown
}
fn validate(address:u32,size:usize)->Result<(),Error>{
    if size==0||size%4!=0||size/4>MAX_INSTRUCTIONS{return Err(Error::Length);}
    if address%4!=0{return Err(Error::Alignment);}
    address.checked_add(size as u32).ok_or(Error::AddressOverflow)?;
    Ok(())
}
pub fn decode(address:u32,bytes:&[u8])->Result<Vec<Instruction>,Error>{
    validate(address,bytes.len())?;
    Ok(bytes.chunks_exact(4).enumerate().map(|(i,b)|{
        let address=address+4*i as u32;let word=u32::from_le_bytes(b.try_into().unwrap());
        Instruction{address,word,condition:(word>>28) as u8,op:op(address,word)}
    }).collect())
}
pub fn read<R:Read+Seek>(s:&mut ReadSession<R>,offset:u64,address:u32,count:usize)->io::Result<Vec<Instruction>>{
    s.cancellation.check()?;
    let size=count.checked_mul(4).ok_or_else(||io::Error::new(io::ErrorKind::InvalidInput,"A32 count overflow"))?;
    validate(address,size).map_err(|_|io::Error::new(io::ErrorKind::InvalidInput,"invalid A32 range"))?;
    let w=s.read_window(offset,size)?;
    let out=decode(address,&w.bytes).map_err(|_|io::Error::new(io::ErrorKind::InvalidData,"invalid A32 window"))?;
    s.cancellation.check()?;Ok(out)
}
