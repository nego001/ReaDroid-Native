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
pub enum Shift{Lsl,Lsr,Asr,Ror}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum LogicalKind{And,Orr,Eor,Ands}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum BitfieldKind{Signed,Merge,Unsigned}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum FpFormat{Single,Double}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum FpBinaryKind{Add,Sub,Mul,Div,Max,Min}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum FpUnaryKind{Move,Abs,Neg,Sqrt}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum VectorLogicalKind{And,Bic,Orr,Eor}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Op{
    Unknown,Nop,
    FpBinary{kind:FpBinaryKind,format:FpFormat,destination:u8,left:u8,right:u8},
    FpUnary{kind:FpUnaryKind,format:FpFormat,destination:u8,source:u8},
    VectorArithmetic{subtract:bool,vector_bits:u8,element_bits:u8,destination:u8,left:u8,right:u8},
    VectorLogical{kind:VectorLogicalKind,vector_bits:u8,destination:u8,left:u8,right:u8},
    LogicalImmediate{kind:LogicalKind,wide:bool,destination:u8,source:u8,n:u8,immr:u8,imms:u8,mask:u64},
    Bitfield{kind:BitfieldKind,wide:bool,destination:u8,source:u8,immr:u8,imms:u8},
    Extract{wide:bool,destination:u8,left:u8,right:u8,lsb:u8},
    AddSubRegister{wide:bool,subtract:bool,set_flags:bool,destination:u8,left:u8,right:u8,shift:Shift,amount:u8},
    LogicalRegister{kind:LogicalKind,wide:bool,invert:bool,destination:u8,left:u8,right:u8,shift:Shift,amount:u8},
    MultiplyAdd{wide:bool,subtract:bool,destination:u8,left:u8,right:u8,accumulator:u8},
    Divide{wide:bool,signed:bool,destination:u8,left:u8,right:u8},
    VariableShift{wide:bool,shift:Shift,destination:u8,source:u8,amount_register:u8},
    PcAddress{page:bool,register:u8,target:Target},
    LiteralLoad{width:u8,signed:bool,register:u8,target:Target},
    MemoryImmediate{load:bool,width:u8,scaled:bool,base:u8,register:u8,displacement:i32},
    MemoryPair{load:bool,width:u8,base:u8,first:u8,second:u8,displacement:i32},
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
    scaled_target(pc,field,bits,4)
}
fn sign_extend(field:u32,bits:u32)->i64{(i64::from(field)<<(64-bits))>>(64-bits)}
fn scaled_target(pc:u64,field:u32,bits:u32,scale:i64)->Target{
    let signed=sign_extend(field,bits)*scale;
    let value=if signed<0{pc.checked_sub(signed.unsigned_abs())}else{pc.checked_add(signed as u64)};
    match value{Some(v)=>Target::Address(v),None=>Target::Overflow}
}
/// Expand one encoded logical immediate. Reject reserved encodings.
/// The result is a bitmask of the selected register width, zero-extended
/// to u64; high immr bits may be ignored by the architectural encoding.
pub fn logical_mask(wide:bool,n:u8,immr:u8,imms:u8)->Option<u64>{
    if n>1||immr>63||imms>63||(!wide&&n!=0){return None;}
    let selector=(u32::from(n)<<6)|u32::from((!imms)&63);
    if selector<2{return None;}
    let len=31-selector.leading_zeros();
    let element=1u32<<len;let width=if wide{64}else{32};
    if element>width{return None;}
    let levels=element-1;
    let ones=(u32::from(imms)&levels)+1;
    if ones==element{return None;}
    let rotation=u32::from(immr)&levels;
    let bits=(1u64<<ones)-1;
    let element_mask=if element==64{u64::MAX}else{(1u64<<element)-1};
    let rotated=if rotation==0{bits}else{((bits>>rotation)|(bits<<(element-rotation)))&element_mask};
    let mut result=0u64;
    for shift in (0..width).step_by(element as usize){result|=rotated<<shift;}
    Some(result)
}
/// Register encoding 31 has context-dependent meaning. These helpers
/// cover only the operand positions explicitly represented here.
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Register{General{wide:bool,index:u8},StackPointer{wide:bool},Zero{wide:bool}}
fn register(wide:bool,index:u8,stack:bool)->Register{
    if index==31{
        if stack{Register::StackPointer{wide}}else{Register::Zero{wide}}
    }else{Register::General{wide,index}}
}
impl Op{
    /// Destination and first source for supported arithmetic/bitmask forms.
    /// None means this helper has no semantic contract for that operation.
    /// Public enum values can be constructed by callers; reject invalid indexes.
    pub fn arithmetic_registers(&self)->Option<(Register,Register)>{
        let (wide,d,s,ds,ss)=match *self{
            Op::AddSubImmediate{wide,destination,source,set_flags,..}=>(wide,destination,source,!set_flags,true),
            Op::LogicalImmediate{wide,destination,source,kind,..}=>(wide,destination,source,kind!=LogicalKind::Ands,false),
            Op::AddSubRegister{wide,destination,left,..}|Op::LogicalRegister{wide,destination,left,..}|
            Op::MultiplyAdd{wide,destination,left,..}|Op::Divide{wide,destination,left,..}|
            Op::Extract{wide,destination,left,..}=>(wide,destination,left,false,false),
            Op::Bitfield{wide,destination,source,..}|Op::VariableShift{wide,destination,source,..}=>(wide,destination,source,false,false),
            _=>return None,
        };
        if d>31||s>31{return None;}
        Some((register(wide,d,ds),register(wide,s,ss)))
    }
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
    // ADR/ADRP: signed immediate split between immhi and immlo.
    if w&0x1f000000==0x10000000{
        let page=w>>31!=0;
        let imm=((w>>5)&0x7ffff)<<2|((w>>29)&3);
        let base=if page{pc&!0xfff}else{pc};
        return Op::PcAddress{page,register:(w&31) as u8,
            target:scaled_target(base,imm,21,if page{4096}else{1})};
    }
    // Integer literal loads, excluding SIMD/FP and PRFM.
    if w&0x3f000000==0x18000000{
        let (width,signed)=match w>>30{0=>(4,false),1=>(8,false),2=>(4,true),_=>return Op::Unknown};
        return Op::LiteralLoad{width,signed,register:(w&31) as u8,target:target(pc,(w>>5)&0x7ffff,19)};
    }
    // Integer unsigned-scaled and signed-unscaled immediates only.
    // No signed-extending loads, writeback, unprivileged or register offsets.
    let scaled=w&0x3f000000==0x39000000;
    let unscaled=w&0x3f200c00==0x38000000;
    if scaled||unscaled{
        let load=match (w>>22)&3{0=>false,1=>true,_=>return Op::Unknown};
        let width=1u8<<(w>>30);
        let displacement=if scaled{(((w>>10)&0xfff) as i32)*i32::from(width)}
            else{sign_extend((w>>12)&0x1ff,9) as i32};
        return Op::MemoryImmediate{load,width,scaled,base:((w>>5)&31) as u8,
            register:(w&31) as u8,displacement};
    }
    // Integer STP/LDP signed offset, no pre/post-index or non-temporal forms.
    if w&0x3f800000==0x29000000{
        let width=match w>>30{0=>4,2=>8,_=>return Op::Unknown};
        return Op::MemoryPair{load:w&(1<<22)!=0,width,base:((w>>5)&31) as u8,
            first:(w&31) as u8,second:((w>>10)&31) as u8,
            displacement:(sign_extend((w>>15)&127,7) as i32)*i32::from(width)};
    }
    // ADD/SUB shifted register. Shift selector 3 is reserved.
    if w&0x1f200000==0x0b000000{
        let wide=w>>31!=0;let amount=((w>>10)&63) as u8;
        if !wide&&amount>=32{return Op::Unknown;}
        let shift=match (w>>22)&3{0=>Shift::Lsl,1=>Shift::Lsr,2=>Shift::Asr,_=>return Op::Unknown};
        return Op::AddSubRegister{wide,subtract:w&(1<<30)!=0,set_flags:w&(1<<29)!=0,
            destination:(w&31) as u8,left:((w>>5)&31) as u8,right:((w>>16)&31) as u8,shift,amount};
    }
    // AND/BIC/ORR/ORN/EOR/EON/ANDS/BICS shifted register.
    if w&0x1f000000==0x0a000000{
        let wide=w>>31!=0;let amount=((w>>10)&63) as u8;
        if !wide&&amount>=32{return Op::Unknown;}
        let shift=match (w>>22)&3{0=>Shift::Lsl,1=>Shift::Lsr,2=>Shift::Asr,_=>Shift::Ror};
        let kind=match (w>>29)&3{0=>LogicalKind::And,1=>LogicalKind::Orr,2=>LogicalKind::Eor,_=>LogicalKind::Ands};
        return Op::LogicalRegister{kind,wide,invert:w&(1<<21)!=0,destination:(w&31) as u8,
            left:((w>>5)&31) as u8,right:((w>>16)&31) as u8,shift,amount};
    }
    // MADD/MSUB (same-width integer form), not widening or high-half forms.
    if w&0x7fe00000==0x1b000000{
        return Op::MultiplyAdd{wide:w>>31!=0,subtract:w&(1<<15)!=0,destination:(w&31) as u8,
            left:((w>>5)&31) as u8,right:((w>>16)&31) as u8,accumulator:((w>>10)&31) as u8};
    }
    // UDIV/SDIV: operands only; never calculate a quotient.
    if w&0x7fe0f800==0x1ac00800{
        return Op::Divide{wide:w>>31!=0,signed:w&(1<<10)!=0,destination:(w&31) as u8,
            left:((w>>5)&31) as u8,right:((w>>16)&31) as u8};
    }
    // LSLV/LSRV/ASRV/RORV.
    if w&0x7fe0f000==0x1ac02000{
        let shift=match (w>>10)&3{0=>Shift::Lsl,1=>Shift::Lsr,2=>Shift::Asr,_=>Shift::Ror};
        return Op::VariableShift{wide:w>>31!=0,shift,destination:(w&31) as u8,
            source:((w>>5)&31) as u8,amount_register:((w>>16)&31) as u8};
    }
    // Logical immediate: decode the architectural repeated bitmask, not
    // the result of applying it to any register.
    if w&0x1f800000==0x12000000{
        let wide=w>>31!=0;
        let n=((w>>22)&1) as u8;let immr=((w>>16)&63) as u8;let imms=((w>>10)&63) as u8;
        let Some(mask)=logical_mask(wide,n,immr,imms)else{return Op::Unknown;};
        let kind=match (w>>29)&3{0=>LogicalKind::And,1=>LogicalKind::Orr,2=>LogicalKind::Eor,_=>LogicalKind::Ands};
        return Op::LogicalImmediate{kind,wide,destination:(w&31) as u8,source:((w>>5)&31) as u8,n,immr,imms,mask};
    }
    // SBFM/BFM/UBFM, retain raw rotate and mask fields, not aliases.
    if w&0x1f800000==0x13000000{
        let wide=w>>31!=0;let n=w&(1<<22)!=0;
        let immr=((w>>16)&63) as u8;let imms=((w>>10)&63) as u8;
        if n!=wide||(!wide&&(immr>=32||imms>=32)){return Op::Unknown;}
        let kind=match (w>>29)&3{0=>BitfieldKind::Signed,1=>BitfieldKind::Merge,2=>BitfieldKind::Unsigned,_=>return Op::Unknown};
        return Op::Bitfield{kind,wide,destination:(w&31) as u8,source:((w>>5)&31) as u8,immr,imms};
    }
    // EXTR: same-width integer form, no execution or alias expansion.
    if w&0x7fa00000==0x13800000{
        let wide=w>>31!=0;let n=w&(1<<22)!=0;
        let lsb=((w>>10)&63) as u8;
        if n!=wide||(!wide&&lsb>=32){return Op::Unknown;}
        return Op::Extract{wide,destination:(w&31) as u8,left:((w>>5)&31) as u8,right:((w>>16)&31) as u8,lsb};
    }
    // Scalar FP two-source S/D subset. Type 2/3 (other formats) excluded.
    let fp2=match w&0xffa0fc00{
        0x1e200800=>Some(FpBinaryKind::Mul),0x1e201800=>Some(FpBinaryKind::Div),
        0x1e202800=>Some(FpBinaryKind::Add),0x1e203800=>Some(FpBinaryKind::Sub),
        0x1e204800=>Some(FpBinaryKind::Max),0x1e205800=>Some(FpBinaryKind::Min),_=>None
    };
    if let Some(kind)=fp2{
        return Op::FpBinary{kind,format:if w&(1<<22)!=0{FpFormat::Double}else{FpFormat::Single},
            destination:(w&31) as u8,left:((w>>5)&31) as u8,right:((w>>16)&31) as u8};
    }
    let fp1=match w&0xffbffc00{
        0x1e204000=>Some(FpUnaryKind::Move),0x1e20c000=>Some(FpUnaryKind::Abs),
        0x1e214000=>Some(FpUnaryKind::Neg),0x1e21c000=>Some(FpUnaryKind::Sqrt),_=>None
    };
    if let Some(kind)=fp1{
        return Op::FpUnary{kind,format:if w&(1<<22)!=0{FpFormat::Double}else{FpFormat::Single},
            destination:(w&31) as u8,source:((w>>5)&31) as u8};
    }
    // Advanced SIMD same-width integer ADD/SUB. 1D is not this vector form.
    if w&0x9f20fc00==0x0e208400{
        let vector_bits=if w&(1<<30)!=0{128}else{64};
        let element_bits=8u8<<((w>>22)&3);
        if element_bits==64&&vector_bits==64{return Op::Unknown;}
        return Op::VectorArithmetic{subtract:w&(1<<29)!=0,vector_bits,element_bits,
            destination:(w&31) as u8,left:((w>>5)&31) as u8,right:((w>>16)&31) as u8};
    }
    // Selected byte-vector logical forms, no bit-select or ORN.
    let vlogic=match w&0xbfe0fc00{
        0x0e201c00=>Some(VectorLogicalKind::And),0x0e601c00=>Some(VectorLogicalKind::Bic),
        0x0ea01c00=>Some(VectorLogicalKind::Orr),0x2e201c00=>Some(VectorLogicalKind::Eor),_=>None
    };
    if let Some(kind)=vlogic{
        return Op::VectorLogical{kind,vector_bits:if w&(1<<30)!=0{128}else{64},
            destination:(w&31) as u8,left:((w>>5)&31) as u8,right:((w>>16)&31) as u8};
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
