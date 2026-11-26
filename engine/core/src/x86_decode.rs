//! Deliberately limited x86 legacy/long-mode decoder. An unsupported opcode
//! or prefix stops the window at its starting byte; no guessed length or
//! resynchronization. Static metadata only, not execution or full ISA proof.
use crate::ReadSession;
use std::io::{self,Read,Seek};
pub const MAX_BYTES:usize=4096;
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Mode{X86,X64}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Target{Address(u64),Overflow}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Op{
    Nop,Return,Breakpoint,
    PushPop{pop:bool,register:u8,width:u8},
    IncDec{decrement:bool,register:u8},
    MoveImmediate{register:u8,width:u8,value:u64},
    Branch{call:bool,condition:Option<u8>,target:Target},
}
#[derive(Debug,Clone,PartialEq,Eq)]
pub struct Instruction{pub address:u64,pub bytes:Vec<u8>,pub op:Op}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Stop{Complete,Unsupported{offset:usize},Truncated{offset:usize}}
#[derive(Debug,Clone,PartialEq,Eq)]
pub struct Page{pub instructions:Vec<Instruction>,pub consumed:usize,pub stop:Stop}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Error{Length,AddressOverflow}
fn validate(mode:Mode,pc:u64,n:usize)->Result<(),Error>{
    if n==0||n>MAX_BYTES{return Err(Error::Length);}
    let end=pc.checked_add(n as u64).ok_or(Error::AddressOverflow)?;
    if mode==Mode::X86&&end>u64::from(u32::MAX)+1{return Err(Error::AddressOverflow);}
    Ok(())
}
fn target(mode:Mode,next:u64,delta:i64)->Target{
    let v=i128::from(next)+i128::from(delta);
    let max=if mode==Mode::X86{i128::from(u32::MAX)}else{i128::from(u64::MAX)};
    if v<0||v>max{Target::Overflow}else{Target::Address(v as u64)}
}
#[derive(Debug,Clone,Copy)]
enum Local{Unsupported,Truncated}
fn take(b:&[u8],start:usize,n:usize)->Result<&[u8],Local>{
    b.get(start..start+n).ok_or(Local::Truncated)
}
fn one(mode:Mode,pc:u64,b:&[u8])->Result<(usize,Op),Local>{
    let mut i=0;
    let mut rex=0u8;
    if mode==Mode::X64&&(0x40..=0x4f).contains(&b[0]){
        rex=b[0];i=1;
    }
    let opcode=*b.get(i).ok_or(Local::Truncated)?;i+=1;
    // Only one REX and only on the forms explicitly supported below.
    // No legacy prefixes, VEX/EVEX, ModRM or SIB in this first subset.
    if (0xb8..=0xbf).contains(&opcode){
        let width=if rex&8!=0{64}else{32};
        let n=if width==64{8}else{4};
        let raw=take(b,i,n)?;
        let mut padded=[0u8;8];padded[..n].copy_from_slice(raw);
        return Ok((i+n,Op::MoveImmediate{register:(opcode&7)|((rex&1)<<3),width,value:u64::from_le_bytes(padded)}));
    }
    if (0x50..=0x5f).contains(&opcode){
        return Ok((i,Op::PushPop{pop:opcode>=0x58,register:(opcode&7)|((rex&1)<<3),width:if mode==Mode::X64{64}else{32}}));
    }
    if rex!=0{return Err(Local::Unsupported);}
    match opcode{
        0x90=>Ok((i,Op::Nop)),
        0xc3=>Ok((i,Op::Return)),
        0xcc=>Ok((i,Op::Breakpoint)),
        0x40..=0x4f if mode==Mode::X86=>Ok((i,Op::IncDec{decrement:opcode>=0x48,register:opcode&7})),
        0xe8|0xe9=>{
            let d=i32::from_le_bytes(take(b,i,4)?.try_into().unwrap());
            let n=i+4;
            Ok((n,Op::Branch{call:opcode==0xe8,condition:None,target:target(mode,pc+n as u64,i64::from(d))}))
        },
        0xeb|0x70..=0x7f=>{
            let d=take(b,i,1)?[0] as i8;
            let n=i+1;
            Ok((n,Op::Branch{call:false,condition:if opcode==0xeb{None}else{Some(opcode&15)},target:target(mode,pc+n as u64,i64::from(d))}))
        },
        0x0f=>{
            let next=take(b,i,1)?[0];i+=1;
            if !(0x80..=0x8f).contains(&next){return Err(Local::Unsupported);}
            let d=i32::from_le_bytes(take(b,i,4)?.try_into().unwrap());
            let n=i+4;
            Ok((n,Op::Branch{call:false,condition:Some(next&15),target:target(mode,pc+n as u64,i64::from(d))}))
        },
        _=>Err(Local::Unsupported)
    }
}
/// Return the verified prefix only, with exact stopping offset. A partial
/// window is never represented as complete. All reads are bounded.
pub fn decode(mode:Mode,pc:u64,bytes:&[u8])->Result<Page,Error>{
    validate(mode,pc,bytes.len())?;
    let mut instructions=Vec::new();let mut i=0;
    while i<bytes.len(){
        match one(mode,pc+i as u64,&bytes[i..]){
            Ok((n,op))=>{
                instructions.push(Instruction{address:pc+i as u64,bytes:bytes[i..i+n].to_vec(),op});
                i+=n;
            },
            Err(Local::Unsupported)=>return Ok(Page{instructions,consumed:i,stop:Stop::Unsupported{offset:i}}),
            Err(Local::Truncated)=>return Ok(Page{instructions,consumed:i,stop:Stop::Truncated{offset:i}}),
        }
    }
    Ok(Page{instructions,consumed:i,stop:Stop::Complete})
}
pub fn read<R:Read+Seek>(s:&mut ReadSession<R>,offset:u64,mode:Mode,pc:u64,size:usize)->io::Result<Page>{
    s.cancellation.check()?;
    validate(mode,pc,size).map_err(|_|io::Error::new(io::ErrorKind::InvalidInput,"invalid x86 window"))?;
    let w=s.read_window(offset,size)?;
    let p=decode(mode,pc,&w.bytes).map_err(|_|io::Error::new(io::ErrorKind::InvalidData,"invalid x86 window"))?;
    s.cancellation.check()?;Ok(p)
}
