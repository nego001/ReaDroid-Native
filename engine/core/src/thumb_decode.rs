//! Selected little-endian Thumb/Thumb-2 static instruction encodings.
//! Width is inferred only from the first halfword at a caller-supplied
//! instruction boundary. No resynchronization, IT-state tracking or execution.
use crate::ReadSession;
use std::io::{self,Read,Seek};
pub const MAX_BYTES:usize=4096;
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Target{Address(u32),Overflow}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum ImmKind{Mov,Cmp,Add,Sub}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Op{
    Unknown,Nop,
    Branch{link:bool,condition:Option<u8>,target:Target},
    Exchange{link:bool,register:u8},
    Immediate{kind:ImmKind,register:u8,value:u8},
    LiteralLoad{register:u8,target:Target},
    MemoryWord{load:bool,base:u8,register:u8,displacement:u16},
}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub struct Instruction{pub address:u32,pub first:u16,pub second:Option<u16>,pub op:Op}
impl Instruction{pub fn width(&self)->u8{if self.second.is_some(){4}else{2}}}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Error{Length,Alignment,AddressOverflow,Truncated{offset:usize}}
fn sign(x:u32,bits:u32)->i64{(i64::from(x)<<(64-bits))>>(64-bits)}
fn address(base:i64,delta:i64)->Target{
    match u32::try_from(base+delta){Ok(x)=>Target::Address(x),Err(_)=>Target::Overflow}
}
pub fn is_wide(first:u16)->bool{matches!(first>>11,0b11101..=0b11111)}
fn short(pc:u32,h:u16)->Op{
    if h==0xbf00{return Op::Nop;}
    let base=i64::from(pc)+4;
    if h&0xf800==0xe000{return Op::Branch{link:false,condition:None,target:address(base,sign(u32::from(h&0x7ff)<<1,12))};}
    if h&0xf000==0xd000{
        let cond=((h>>8)&15) as u8;
        if cond>=14{return Op::Unknown;}
        return Op::Branch{link:false,condition:Some(cond),target:address(base,sign(u32::from(h&255)<<1,9))};
    }
    if h&0xff07==0x4700{
        let register=((h>>3)&15) as u8;
        if register==15{return Op::Unknown;}
        return Op::Exchange{link:h&(1<<7)!=0,register};
    }
    if h&0xe000==0x2000{
        let kind=match (h>>11)&3{0=>ImmKind::Mov,1=>ImmKind::Cmp,2=>ImmKind::Add,_=>ImmKind::Sub};
        return Op::Immediate{kind,register:((h>>8)&7) as u8,value:(h&255) as u8};
    }
    if h&0xf800==0x4800{
        return Op::LiteralLoad{register:((h>>8)&7) as u8,target:address(base&!3,i64::from(h&255)*4)};
    }
    if h&0xf000==0x6000{
        return Op::MemoryWord{load:h&(1<<11)!=0,base:((h>>3)&7) as u8,register:(h&7) as u8,displacement:((h>>6)&31)*4};
    }
    Op::Unknown
}
fn wide(pc:u32,a:u16,b:u16)->Op{
    // T4 B.W and T1 BL, with inverted J1/J2 encoding; no BLX or
    // conditional wide branches in this initial subset.
    if a&0xf800==0xf000{
        let link=match b&0xd000{0x9000=>false,0xd000=>true,_=>return Op::Unknown};
        let s=u32::from((a>>10)&1);
        let i1=1^(u32::from((b>>13)&1)^s);let i2=1^(u32::from((b>>11)&1)^s);
        let field=(s<<24)|(i1<<23)|(i2<<22)|(u32::from(a&0x3ff)<<12)|(u32::from(b&0x7ff)<<1);
        return Op::Branch{link,condition:None,target:address(i64::from(pc)+4,sign(field,25))};
    }
    Op::Unknown
}
fn validate(pc:u32,size:usize)->Result<(),Error>{
    if size==0||size>MAX_BYTES||size%2!=0{return Err(Error::Length);}
    if pc%2!=0{return Err(Error::Alignment);}
    pc.checked_add(size as u32).ok_or(Error::AddressOverflow)?;Ok(())
}
/// Decode a complete exact window. Unknown wide words retain both halfwords.
/// A truncated final wide instruction rejects the entire window.
pub fn decode(pc:u32,bytes:&[u8])->Result<Vec<Instruction>,Error>{
    validate(pc,bytes.len())?;
    let mut out=Vec::new();let mut i=0;
    while i<bytes.len(){
        let a=u16::from_le_bytes(bytes[i..i+2].try_into().unwrap());
        let at=pc+i as u32;
        let (second,op,width)=if is_wide(a){
            if i+4>bytes.len(){return Err(Error::Truncated{offset:i});}
            let b=u16::from_le_bytes(bytes[i+2..i+4].try_into().unwrap());
            (Some(b),wide(at,a,b),4)
        }else{(None,short(at,a),2)};
        out.push(Instruction{address:at,first:a,second,op});i+=width;
    }
    Ok(out)
}
pub fn read<R:Read+Seek>(s:&mut ReadSession<R>,offset:u64,pc:u32,size:usize)->io::Result<Vec<Instruction>>{
    s.cancellation.check()?;
    validate(pc,size).map_err(|_|io::Error::new(io::ErrorKind::InvalidInput,"invalid Thumb window"))?;
    let w=s.read_window(offset,size)?;
    let result=decode(pc,&w.bytes).map_err(|_|io::Error::new(io::ErrorKind::InvalidData,"incomplete Thumb instruction window"))?;
    s.cancellation.check()?;Ok(result)
}
