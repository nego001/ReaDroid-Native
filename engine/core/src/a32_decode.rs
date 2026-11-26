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
pub enum Op{
    Unknown,Nop,
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
