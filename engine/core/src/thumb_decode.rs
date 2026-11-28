//! Selected little-endian Thumb/Thumb-2 static instruction encodings.
//! Width is inferred only from the first halfword at a caller-supplied
//! instruction boundary. No resynchronization or execution; contextual IT annotation is explicit.
use crate::ReadSession;
use std::io::{self,Read,Seek};
pub const MAX_BYTES:usize=4096;
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Target{Address(u32),Overflow}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum ImmKind{Mov,Cmp,Add,Sub}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum ShiftKind{Lsl,Lsr,Asr}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Operand{Register(u8),Immediate(u8)}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum AluKind{And,Eor,Lsl,Lsr,Asr,Adc,Sbc,Ror,Tst,Rsb,Cmp,Cmn,Orr,Mul,Bic,Mvn}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum HighKind{Add,Cmp,Mov}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum MemKind{Word,Half,Byte,SignedByte,SignedHalf}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Op{
    Unknown,Nop,
    It{condition:u8,mask:u8},
    WideMove{top:bool,destination:u8,value:u16},
    WideAddSub{subtract:bool,destination:u8,source:u8,value:u16},
    ShiftImmediate{kind:ShiftKind,amount:u8,destination:u8,source:u8},
    AddSub{subtract:bool,destination:u8,source:u8,operand:Operand},
    Alu{kind:AluKind,rdn:u8,source:u8},
    HighRegister{kind:HighKind,destination:u8,source:u8},
    MemoryRegister{load:bool,kind:MemKind,base:u8,register:u8,offset:u8},
    MemoryImmediate{load:bool,kind:MemKind,base:u8,register:u8,displacement:u16},
    StackList{pop:bool,list:u16},
    BlockTransfer{load:bool,base:u8,list:u8},
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
    if h&0xff00==0xbf00&&h&15!=0{
        let condition=((h>>4)&15) as u8;
        if condition>=14{return Op::Unknown;}
        return Op::It{condition,mask:(h&15) as u8};
    }
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
    // T1 immediate shifts. Zero encodes 32 for LSR and ASR.
    if h&0xe000==0&&h&0x1800!=0x1800{
        let kind=match (h>>11)&3{0=>ShiftKind::Lsl,1=>ShiftKind::Lsr,_=>ShiftKind::Asr};
        let mut amount=((h>>6)&31) as u8;
        if amount==0&&kind!=ShiftKind::Lsl{amount=32;}
        return Op::ShiftImmediate{kind,amount,destination:(h&7) as u8,source:((h>>3)&7) as u8};
    }
    if h&0xf800==0x1800{
        let field=((h>>6)&7) as u8;
        return Op::AddSub{subtract:h&0x0200!=0,destination:(h&7) as u8,source:((h>>3)&7) as u8,
            operand:if h&0x0400!=0{Operand::Immediate(field)}else{Operand::Register(field)}};
    }
    if h&0xfc00==0x4000{
        let kind=[AluKind::And,AluKind::Eor,AluKind::Lsl,AluKind::Lsr,AluKind::Asr,AluKind::Adc,AluKind::Sbc,
            AluKind::Ror,AluKind::Tst,AluKind::Rsb,AluKind::Cmp,AluKind::Cmn,AluKind::Orr,AluKind::Mul,AluKind::Bic,AluKind::Mvn][((h>>6)&15) as usize];
        return Op::Alu{kind,rdn:(h&7) as u8,source:((h>>3)&7) as u8};
    }
    // High-register ADD/CMP/MOV, excluding PC and SP forms. BX/BLX handled above.
    if h&0xfc00==0x4400{
        let kind=match (h>>8)&3{0=>HighKind::Add,1=>HighKind::Cmp,2=>HighKind::Mov,_=>return Op::Unknown};
        let destination=((h&7)|((h>>4)&8)) as u8;let source=((h>>3)&15) as u8;
        if destination==15||source==15||destination==13||source==13||
            (kind==HighKind::Cmp&&destination<8&&source<8){return Op::Unknown;}
        return Op::HighRegister{kind,destination,source};
    }
    if h&0xf000==0x5000{
        let (load,kind)=match (h>>9)&7{
            0=>(false,MemKind::Word),1=>(false,MemKind::Half),2=>(false,MemKind::Byte),3=>(true,MemKind::SignedByte),
            4=>(true,MemKind::Word),5=>(true,MemKind::Half),6=>(true,MemKind::Byte),_=>(true,MemKind::SignedHalf)};
        return Op::MemoryRegister{load,kind,base:((h>>3)&7) as u8,register:(h&7) as u8,offset:((h>>6)&7) as u8};
    }
    if h&0xf000==0x7000||h&0xf000==0x8000{
        let half=h&0xf000==0x8000;
        return Op::MemoryImmediate{load:h&0x0800!=0,kind:if half{MemKind::Half}else{MemKind::Byte},
            base:((h>>3)&7) as u8,register:(h&7) as u8,displacement:((h>>6)&31)*if half{2}else{1}};
    }
    if h&0xf000==0x9000{
        return Op::MemoryImmediate{load:h&0x0800!=0,kind:MemKind::Word,base:13,
            register:((h>>8)&7) as u8,displacement:(h&255)*4};
    }
    if h&0xfe00==0xb400||h&0xfe00==0xbc00{
        let pop=h&0x0800!=0;
        let list=(h&255)|if h&0x100!=0{if pop{1<<15}else{1<<14}}else{0};
        if list==0{return Op::Unknown;}
        return Op::StackList{pop,list};
    }
    if h&0xf000==0xc000{
        let load=h&0x0800!=0;let base=((h>>8)&7) as u8;let list=(h&255) as u8;
        // Exclude base-in-list cases, where writeback/overlap semantics vary.
        if list==0||list&(1<<base)!=0{return Op::Unknown;}
        return Op::BlockTransfer{load,base,list};
    }
    Op::Unknown
}
fn wide(pc:u32,a:u16,b:u16)->Op{
    // T3 conditional branch: J2/J1 are not inverted as in B.W/BL.
    if a&0xf800==0xf000&&b&0xd000==0x8000{
        let cond=((a>>6)&15) as u8;
        if cond<14{
            let field=(u32::from((a>>10)&1)<<20)|(u32::from((b>>11)&1)<<19)|
                (u32::from((b>>13)&1)<<18)|(u32::from(a&63)<<12)|(u32::from(b&0x7ff)<<1);
            return Op::Branch{link:false,condition:Some(cond),target:address(i64::from(pc)+4,sign(field,21))};
        }
        // Other opcodes in this encoding space are not conditional branches.
        return Op::Unknown;
    }
    // MOVW/MOVT: immediate assembled from imm4:i:imm3:imm8.
    let key=a&0xfbf0;
    if (key==0xf240||key==0xf2c0)&&b&0x8000==0{
        let destination=((b>>8)&15) as u8;
        if destination==13||destination==15{return Op::Unknown;}
        let value=((a&15)<<12)|(((a>>10)&1)<<11)|(((b>>12)&7)<<8)|(b&255);
        return Op::WideMove{top:key==0xf2c0,destination,value};
    }
    // ADDW/SUBW immediate, no PC-relative aliases or SP forms in this subset.
    if (key==0xf200||key==0xf2a0)&&b&0x8000==0{
        let destination=((b>>8)&15) as u8;let source=(a&15) as u8;
        if [destination,source].iter().any(|&x|x==13||x==15){return Op::Unknown;}
        let value=(((a>>10)&1)<<11)|(((b>>12)&7)<<8)|(b&255);
        return Op::WideAddSub{subtract:key==0xf2a0,destination,source,value};
    }
    // Unsigned imm12 single transfers, excluding literal/PC and special Rt forms.
    let memory=match a&0xfff0{
        0xf8c0=>Some((false,MemKind::Word)),0xf8d0=>Some((true,MemKind::Word)),
        0xf880=>Some((false,MemKind::Byte)),0xf890=>Some((true,MemKind::Byte)),
        0xf8a0=>Some((false,MemKind::Half)),0xf8b0=>Some((true,MemKind::Half)),
        0xf990=>Some((true,MemKind::SignedByte)),0xf9b0=>Some((true,MemKind::SignedHalf)),_=>None
    };
    if let Some((load,kind))=memory{
        let base=(a&15) as u8;let register=(b>>12) as u8;
        if base==15||register==13||register==15{return Op::Unknown;}
        return Op::MemoryImmediate{load,kind,base,register,displacement:b&0xfff};
    }
    // T4 B.W and T1 BL, with inverted J1/J2 encoding; no BLX.
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


/// Sequential IT context, supplied by the caller at a known entry boundary.
/// This is a static annotation, not CPU state or proof of executable control flow.
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub struct Context{next:u32,state:u8}
impl Context{
    pub fn outside(next:u32)->Self{Self{next,state:0}}
    pub fn next_address(self)->u32{self.next}
    pub fn pending_condition(self)->Option<u8>{if self.state==0{None}else{Some(self.state>>4)}}
}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub struct Annotated{pub instruction:Instruction,pub it_condition:Option<u8>,pub last_in_it:bool}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum ContextError{Decode(Error),Discontinuous,UnsupportedIt{address:u32},NestedIt{address:u32},
    ConditionalBranchInIt{address:u32},ControlFlowBeforeLast{address:u32}}
fn advance(state:u8)->u8{
    if state&7==0{0}else{(state&0xe0)|((state<<1)&0x1f)}
}
/// Annotate consecutive decoded instructions. Unknown instructions consume
/// one IT slot regardless of width; their legality and effects are not inferred.
/// An unfinished block is returned as opaque context for the next window.
/// No partial result or updated context escapes on error.
pub fn decode_context(pc:u32,bytes:&[u8],entry:Context)->Result<(Vec<Annotated>,Context),ContextError>{
    if entry.next!=pc{return Err(ContextError::Discontinuous);}
    let decoded=decode(pc,bytes).map_err(ContextError::Decode)?;
    let mut state=entry.state;
    let mut result=Vec::with_capacity(decoded.len());
    for instruction in decoded{
        let at=instruction.address;
        let raw=instruction.first;
        if instruction.second.is_none()&&raw&0xff00==0xbf00&&raw&15!=0{
            if state!=0{return Err(ContextError::NestedIt{address:at});}
            let Op::It{condition,mask}=instruction.op else{return Err(ContextError::UnsupportedIt{address:at});};
            state=(condition<<4)|mask;
            result.push(Annotated{instruction,it_condition:None,last_in_it:false});
            continue;
        }
        let it_condition=if state==0{None}else{Some(state>>4)};
        let last_in_it=state!=0&&state&7==0;
        if state!=0{
            if matches!(instruction.op,Op::Branch{condition:Some(_),..}){
                return Err(ContextError::ConditionalBranchInIt{address:at});
            }
            let control=matches!(instruction.op,Op::Branch{..}|Op::Exchange{..})||
                matches!(instruction.op,Op::StackList{pop:true,list} if list&0x8000!=0);
            if control&&!last_in_it{return Err(ContextError::ControlFlowBeforeLast{address:at});}
            state=advance(state);
        }
        result.push(Annotated{instruction,it_condition,last_in_it});
    }
    // decode already validated checked exclusive end.
    Ok((result,Context{next:pc+bytes.len() as u32,state}))
}
