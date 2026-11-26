//! Selected A64 instruction encodings, not a full ISA validator or emulator.
//! A64 instruction words use little-endian byte encoding. Addresses are
//! caller-supplied virtual coordinates, independent of the source offset.
//! Unknown means outside this decoder subset, not necessarily invalid.
use crate::ReadSession;
use std::io::{self,Read,Seek};
pub const MAX_INSTRUCTIONS:usize=1024;
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Target{Address(u64),Overflow}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum WideKind{Movn,Movz,Movk}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Op{
    Unknown,Nop,
    Branch{link:bool,target:Target},
    Conditional{condition:u8,target:Target},
    CompareBranch{wide:bool,nonzero:bool,register:u8,target:Target},
    TestBranch{nonzero:bool,register:u8,bit:u8,target:Target},
    RegisterBranch{link:bool,register:u8},
    Return{register:u8},
    WideMove{kind:WideKind,wide:bool,register:u8,immediate:u16,shift:u8},
    AddSubImmediate{wide:bool,subtract:bool,set_flags:bool,destination:u8,source:u8,immediate:u16,shift:u8},
}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub struct Instruction{pub address:u64,pub word:u32,pub op:Op}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Error{Length,Alignment,AddressOverflow}
fn target(pc:u64,field:u32,bits:u32)->Target{
    let signed=((i64::from(field)<<(64-bits))>>(64-bits))*4;
    let value=if signed<0{pc.checked_sub(signed.unsigned_abs())}else{pc.checked_add(signed as u64)};
    match value{Some(v)=>Target::Address(v),None=>Target::Overflow}
}
fn op(pc:u64,w:u32)->Op{
    if w==0xd503201f{return Op::Nop;}
    if w&0x7c000000==0x14000000{
        return Op::Branch{link:w>>31!=0,target:target(pc,w&0x03ffffff,26)};
    }
    if w&0xff000010==0x54000000{
        return Op::Conditional{condition:(w&15) as u8,target:target(pc,(w>>5)&0x7ffff,19)};
    }
    if w&0x7e000000==0x34000000{
        return Op::CompareBranch{wide:w>>31!=0,nonzero:w&(1<<24)!=0,register:(w&31) as u8,
            target:target(pc,(w>>5)&0x7ffff,19)};
    }
    if w&0x7e000000==0x36000000{
        return Op::TestBranch{nonzero:w&(1<<24)!=0,register:(w&31) as u8,
            bit:(((w>>31)<<5)|((w>>19)&31)) as u8,target:target(pc,(w>>5)&0x3fff,14)};
    }
    let register=((w>>5)&31) as u8;
    match w&0xfffffc1f{
        0xd61f0000=>return Op::RegisterBranch{link:false,register},
        0xd63f0000=>return Op::RegisterBranch{link:true,register},
        0xd65f0000=>return Op::Return{register},
        _=>{}
    }
    if w&0x1f800000==0x12800000{
        let wide=w>>31!=0;
        let hw=((w>>21)&3) as u8;
        if !wide&&hw>=2{return Op::Unknown;}
        let kind=match (w>>29)&3{0=>WideKind::Movn,2=>WideKind::Movz,3=>WideKind::Movk,_=>return Op::Unknown};
        return Op::WideMove{kind,wide,register:(w&31) as u8,immediate:((w>>5)&0xffff) as u16,shift:hw*16};
    }
    if w&0x1f800000==0x11000000{
        return Op::AddSubImmediate{wide:w>>31!=0,subtract:w&(1<<30)!=0,set_flags:w&(1<<29)!=0,
            destination:(w&31) as u8,source:((w>>5)&31) as u8,
            immediate:((w>>10)&0xfff) as u16,shift:if w&(1<<22)!=0{12}else{0}};
    }
    Op::Unknown
}
fn validate(address:u64,size:usize)->Result<(),Error>{
    if size==0||size%4!=0||size/4>MAX_INSTRUCTIONS{return Err(Error::Length);}
    if address%4!=0{return Err(Error::Alignment);}
    address.checked_add(size as u64).ok_or(Error::AddressOverflow)?;
    Ok(())
}
/// Decode exact complete words. No resynchronization, execution, memory
/// access emulation, operand alias expansion or inference of code boundaries.
pub fn decode(address:u64,bytes:&[u8])->Result<Vec<Instruction>,Error>{
    validate(address,bytes.len())?;
    Ok(bytes.chunks_exact(4).enumerate().map(|(i,b)|{
        let address=address+4*i as u64;
        let word=u32::from_le_bytes(b.try_into().unwrap());
        Instruction{address,word,op:op(address,word)}
    }).collect())
}
/// One bounded read, charged against the caller's source budget.
pub fn read<R:Read+Seek>(session:&mut ReadSession<R>,offset:u64,address:u64,count:usize)->io::Result<Vec<Instruction>>{
    session.cancellation.check()?;
    let size=count.checked_mul(4).ok_or_else(||io::Error::new(io::ErrorKind::InvalidInput,"A64 count overflow"))?;
    validate(address,size).map_err(|_|io::Error::new(io::ErrorKind::InvalidInput,"invalid A64 range"))?;
    let w=session.read_window(offset,size)?;
    let out=decode(address,&w.bytes).map_err(|_|io::Error::new(io::ErrorKind::InvalidData,"invalid A64 window"))?;
    session.cancellation.check()?;
    Ok(out)
}
