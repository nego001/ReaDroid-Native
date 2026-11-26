//! Deliberately limited x86 legacy/long-mode decoder. An unsupported opcode
//! or prefix stops the window at its starting byte; no guessed length or
//! resynchronization. Static metadata only, not execution or full ISA proof.
use crate::ReadSession;
use std::io::{self,Read,Seek};
pub const MAX_BYTES:usize=4096;
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Mode{X86,X64}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Segment{Es,Cs,Ss,Ds,Fs,Gs}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum StringKind{Movs,Cmps,Stos,Lods,Scas}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Repeat{None,Rep,Repe,Repne}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum ShiftKind{Rol,Ror,Rcl,Rcr,Shl,Shr,Sar}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum ShiftCount{One,Cl,Immediate(u8)}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum BitKind{Test,Set,Reset,Complement}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum BitIndex{Register(u8),Immediate(u8)}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum ExchangeKind{Xchg,Xadd,Cmpxchg}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum FenceKind{Load,Store,Full}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum LockKind{None,Explicit,Implicit}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum CountKind{Population,LeadingZeros,TrailingZeros}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum CpuFeature{Popcnt,Lzcnt,Bmi1,Sse,Sse2}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum WithoutFeature{InvalidOpcode,BitScan{reverse:bool}}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub struct FeatureRequirement{pub feature:CpuFeature,pub without:WithoutFeature}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Target{Address(u64),Overflow}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Base{None,Register(u8),Rip,Eip}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub struct Memory{pub base:Base,pub index:Option<u8>,pub scale:u8,pub displacement:i64,pub rip_target:Option<Target>}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Operand{Register(u8),HighByte(u8),Memory(Memory)}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum XmmOperand{Register(u8),Memory(Memory)}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum FloatFormat{PackedSingle,PackedDouble,ScalarSingle,ScalarDouble}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum SseKind{MoveUnaligned,MoveAligned,Add,Sub,Mul,Div,Min,Max,Sqrt,And,AndNot,Or,Xor}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum PackedKind{MoveAligned,MoveUnaligned,Add,Sub,Equal,GreaterSigned,And,AndNot,Or,Xor}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum ConversionKind{IntToFloat,FloatToIntRounded,FloatToIntTruncated}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum ConversionOperand{Xmm(u8),Gpr(u8),Memory(Memory)}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum BinaryKind{Mov,Add,Or,Adc,Sbb,And,Sub,Xor,Cmp,Test}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum UnaryKind{Inc,Dec,Call,Jump,Push,Not,Neg,Mul,Imul,Div,Idiv}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub struct Immediate{pub encoded_bits:u8,pub raw:u64,pub value:u64}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Op{
    Nop,Return,Breakpoint,Pause,
    CountBits{kind:CountKind,width:u8,destination:u8,source:Operand},
    Sse{kind:SseKind,format:FloatFormat,destination:XmmOperand,source:XmmOperand},
    PackedInteger{kind:PackedKind,lane_bits:Option<u8>,destination:XmmOperand,source:XmmOperand},
    ScalarConvert{kind:ConversionKind,float_bits:u8,int_bits:u8,destination:ConversionOperand,source:ConversionOperand},
    String{kind:StringKind,width:u8,repeat:Repeat},
    Shift{kind:ShiftKind,width:u8,operand:Operand,count:ShiftCount},
    DoubleShift{right:bool,width:u8,destination:Operand,source:u8,count:ShiftCount},
    Bit{kind:BitKind,width:u8,operand:Operand,index:BitIndex},
    BitScan{reverse:bool,width:u8,destination:u8,source:Operand},
    Exchange{kind:ExchangeKind,width:u8,destination:Operand,source:Operand},
    CompareExchangePair{width:u8,memory:Memory},
    Fence{kind:FenceKind},
    BinaryImmediate{kind:BinaryKind,width:u8,operand:Operand,immediate:Immediate},
    Unary{kind:UnaryKind,width:u8,operand:Operand},
    Binary{kind:BinaryKind,width:u8,destination:Operand,source:Operand},
    Lea{width:u8,destination:u8,memory:Memory},
    ExtendMove{signed:bool,destination_width:u8,source_width:u8,destination:u8,source:Operand},
    Multiply{width:u8,destination:u8,source:Operand},
    MultiplyImmediate{width:u8,destination:u8,source:Operand,immediate:Immediate},
    ConditionalMove{condition:u8,width:u8,destination:u8,source:Operand},
    SetCondition{condition:u8,destination:Operand},
    PushPop{pop:bool,register:u8,width:u8},
    IncDec{decrement:bool,register:u8},
    MoveImmediate{register:u8,width:u8,value:u64},
    Branch{call:bool,condition:Option<u8>,target:Target},
}
#[derive(Debug,Clone,PartialEq,Eq)]
pub struct Instruction{pub address:u64,pub bytes:Vec<u8>,pub op:Op,pub address_width:u8,pub segment_override:Option<Segment>,pub locked:bool}
impl Instruction{
    /// Selected SSE/SSE2 encoding requirement, independent of the host CPU.
    pub fn sse_feature(&self)->Option<CpuFeature>{
        match self.op{
            Op::Sse{format:FloatFormat::PackedSingle|FloatFormat::ScalarSingle,..}=>Some(CpuFeature::Sse),
            Op::Sse{format:FloatFormat::PackedDouble|FloatFormat::ScalarDouble,..}|Op::PackedInteger{..}|Op::ScalarConvert{float_bits:64,..}=>Some(CpuFeature::Sse2),
            Op::ScalarConvert{float_bits:32,..}=>Some(CpuFeature::Sse),
            _=>None
        }
    }
    /// Selected count feature requirements, not a complete ISA inventory.
    pub fn count_feature(&self)->Option<FeatureRequirement>{
        let (feature,without)=match self.op{
            Op::CountBits{kind:CountKind::Population,..}=>(CpuFeature::Popcnt,WithoutFeature::InvalidOpcode),
            Op::CountBits{kind:CountKind::LeadingZeros,..}=>(CpuFeature::Lzcnt,WithoutFeature::BitScan{reverse:true}),
            Op::CountBits{kind:CountKind::TrailingZeros,..}=>(CpuFeature::Bmi1,WithoutFeature::BitScan{reverse:false}),
            _=>return None
        };
        Some(FeatureRequirement{feature,without})
    }
    /// Encoded LOCK versus implicit memory XCHG locking; not a runtime atomicity guarantee.
    pub fn lock_kind(&self)->LockKind{
        if self.locked{LockKind::Explicit}
        else if matches!(self.op,Op::Exchange{kind:ExchangeKind::Xchg,destination:Operand::Memory(_),..}){LockKind::Implicit}
        else{LockKind::None}
    }
}
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
fn modrm(mode:Mode,pc:u64,b:&[u8],mut i:usize,rex:u8,address_override:bool)->Result<(usize,u8,Operand),Local>{
    let m=take(b,i,1)?[0];i+=1;
    let form=m>>6;let raw=m&7;
    let reg=((m>>3)&7)|(((rex>>2)&1)<<3);
    let extension=(rex&1)<<3;
    if form==3{
        if address_override{return Err(Local::Unsupported);}
        return Ok((i,reg,Operand::Register(raw|extension)));
    }
    // 32-bit mode with 67 uses the legacy 16-bit ModRM table, never SIB.
    if mode==Mode::X86&&address_override{
        let (base,index)=match raw{
            0=>(Base::Register(3),Some(6)),1=>(Base::Register(3),Some(7)),
            2=>(Base::Register(5),Some(6)),3=>(Base::Register(5),Some(7)),
            4=>(Base::Register(6),None),5=>(Base::Register(7),None),
            6 if form==0=>(Base::None,None),6=>(Base::Register(5),None),_ =>(Base::Register(3),None)
        };
        let displacement=if form==0&&raw==6||form==2{
            let v=u16::from_le_bytes(take(b,i,2)?.try_into().unwrap());i+=2;
            if base==Base::None{i64::from(v)}else{i64::from(v as i16)}
        }else if form==1{let v=take(b,i,1)?[0] as i8;i+=1;i64::from(v)}else{0};
        return Ok((i,reg,Operand::Memory(Memory{base,index,scale:1,displacement,rip_target:None})));
    }
    let mut base=Base::Register(raw|extension);
    let mut index=None;let mut scale=1;
    let mut disp32=form==2;
    if raw==4{
        let sib=take(b,i,1)?[0];i+=1;
        let ix=(sib>>3)&7;
        if ix!=4||rex&2!=0{index=Some(ix|(((rex>>1)&1)<<3));scale=1<<(sib>>6);}
        let bs=sib&7;
        base=if form==0&&bs==5{disp32=true;Base::None}else{Base::Register(bs|extension)};
    }else if form==0&&raw==5{
        disp32=true;
        base=if mode==Mode::X64{if address_override{Base::Eip}else{Base::Rip}}else{Base::None};
    }
    let displacement=if disp32{
        let v=u32::from_le_bytes(take(b,i,4)?.try_into().unwrap());i+=4;
        if (mode==Mode::X86||address_override)&&base==Base::None{i64::from(v)}else{i64::from(v as i32)}
    }else if form==1{
        let v=take(b,i,1)?[0] as i8;i+=1;i64::from(v)
    }else{0};
    // Provisional RIP target; trailing-immediate forms must finish it at instruction end.
    let rip_target=ip_target(mode,base,pc+i as u64,displacement);
    Ok((i,reg,Operand::Memory(Memory{base,index,scale,displacement,rip_target})))
}
// EIP-relative effective addresses are reduced modulo 2^32 and zero-extended.
// Existing RIP coordinates retain the checked (non-wrapping) policy.
fn ip_target(mode:Mode,base:Base,next:u64,delta:i64)->Option<Target>{
    match base{
        Base::Rip=>Some(target(mode,next,delta)),
        Base::Eip=>Some(Target::Address(u64::from((next as u32).wrapping_add(delta as u32)))),
        _=>None
    }
}
fn finish_rip(mode:Mode,pc:u64,end:usize,operand:Operand)->Operand{
    match operand{
        Operand::Memory(mut m) if matches!(m.base,Base::Rip|Base::Eip)=>{
            m.rip_target=ip_target(mode,m.base,pc+end as u64,m.displacement);
            Operand::Memory(m)
        }
        _=>operand
    }
}
fn immediate(b:&[u8],i:usize,n:usize,width:u8)->Result<Immediate,Local>{
    let raw=match n{1=>u64::from(take(b,i,1)?[0]),2=>u64::from(u16::from_le_bytes(take(b,i,2)?.try_into().unwrap())),4=>u64::from(u32::from_le_bytes(take(b,i,4)?.try_into().unwrap())),_=>return Err(Local::Unsupported)};
    let extended=if n==1{(raw as i8 as i64) as u64}else if width==64{(raw as i32 as i64) as u64}else{raw};
    Ok(Immediate{encoded_bits:(n*8) as u8,raw,value:match width{8=>extended&255,16=>extended&65535,32=>extended&0xffff_ffff,_=>extended}})
}
// HighByte stores the parent register index (0=AH, 1=CH, 2=DH, 3=BH).
fn byte_register(index:u8,rex:u8)->Operand{
    if rex==0&&(4..8).contains(&index){Operand::HighByte(index-4)}else{Operand::Register(index)}
}
fn byte_operand(operand:Operand,rex:u8)->Operand{
    match operand{Operand::Register(index)=>byte_register(index,rex),_=>operand}
}
fn xmm_operand(op:Operand)->Result<XmmOperand,Local>{
    match op{Operand::Register(r)=>Ok(XmmOperand::Register(r)),Operand::Memory(m)=>Ok(XmmOperand::Memory(m)),_=>Err(Local::Unsupported)}
}
fn sse_kind(opcode:u8)->Option<SseKind>{match opcode{
    0x10|0x11=>Some(SseKind::MoveUnaligned),0x28|0x29=>Some(SseKind::MoveAligned),
    0x51=>Some(SseKind::Sqrt),0x54=>Some(SseKind::And),0x55=>Some(SseKind::AndNot),0x56=>Some(SseKind::Or),0x57=>Some(SseKind::Xor),
    0x58=>Some(SseKind::Add),0x59=>Some(SseKind::Mul),0x5c=>Some(SseKind::Sub),0x5d=>Some(SseKind::Min),0x5e=>Some(SseKind::Div),0x5f=>Some(SseKind::Max),_=>None
}}
fn packed_kind(op:u8)->Option<(PackedKind,Option<u8>)>{
    use PackedKind::*;
    Some(match op{
        0xfc=>(Add,Some(8)),0xfd=>(Add,Some(16)),0xfe=>(Add,Some(32)),0xd4=>(Add,Some(64)),
        0xf8=>(Sub,Some(8)),0xf9=>(Sub,Some(16)),0xfa=>(Sub,Some(32)),0xfb=>(Sub,Some(64)),
        0x74=>(Equal,Some(8)),0x75=>(Equal,Some(16)),0x76=>(Equal,Some(32)),
        0x64=>(GreaterSigned,Some(8)),0x65=>(GreaterSigned,Some(16)),0x66=>(GreaterSigned,Some(32)),
        0xdb=>(And,None),0xdf=>(AndNot,None),0xeb=>(Or,None),0xef=>(Xor,None),
        0x6f|0x7f=>(MoveAligned,None),_=>return None
    })
}
fn conversion_rm(rm:Operand,gpr:bool)->Result<ConversionOperand,Local>{
    match rm{Operand::Register(r)=>Ok(if gpr{ConversionOperand::Gpr(r)}else{ConversionOperand::Xmm(r)}),Operand::Memory(m)=>Ok(ConversionOperand::Memory(m)),_=>Err(Local::Unsupported)}
}
fn explicit_memory(op:Op)->bool{
    match op{
        Op::Sse{destination,source,..}|Op::PackedInteger{destination,source,..}=>matches!(destination,XmmOperand::Memory(_))||matches!(source,XmmOperand::Memory(_)),
        Op::ScalarConvert{destination,source,..}=>matches!(destination,ConversionOperand::Memory(_))||matches!(source,ConversionOperand::Memory(_)),
        Op::Binary{destination,source,..}=>matches!(destination,Operand::Memory(_))||matches!(source,Operand::Memory(_)),
        Op::BinaryImmediate{operand,..}|Op::Unary{operand,..}=>matches!(operand,Operand::Memory(_)),
        Op::ExtendMove{source,..}|Op::Multiply{source,..}|Op::MultiplyImmediate{source,..}|Op::ConditionalMove{source,..}|Op::CountBits{source,..}=>matches!(source,Operand::Memory(_)),
        Op::SetCondition{destination,..}|Op::DoubleShift{destination,..}|Op::Exchange{destination,..}=>matches!(destination,Operand::Memory(_)),
        Op::CompareExchangePair{..}=>true,
        Op::Shift{operand,..}|Op::Bit{operand,..}|Op::BitScan{source:operand,..}=>matches!(operand,Operand::Memory(_)),
        // LEA computes an offset; it is not a segmented memory access.
        _=>false
    }
}
fn segment_prefix(b:u8)->Option<Segment>{match b{
    0x26=>Some(Segment::Es),0x2e=>Some(Segment::Cs),0x36=>Some(Segment::Ss),
    0x3e=>Some(Segment::Ds),0x64=>Some(Segment::Fs),0x65=>Some(Segment::Gs),_=>None
}}
fn lockable(op:Op)->bool{
    fn alu(k:BinaryKind)->bool{matches!(k,BinaryKind::Add|BinaryKind::Or|BinaryKind::Adc|BinaryKind::Sbb|BinaryKind::And|BinaryKind::Sub|BinaryKind::Xor)}
    match op{
        Op::Binary{kind,destination:Operand::Memory(_),..}|Op::BinaryImmediate{kind,operand:Operand::Memory(_),..}=>alu(kind),
        Op::Unary{kind:UnaryKind::Inc|UnaryKind::Dec|UnaryKind::Not|UnaryKind::Neg,operand:Operand::Memory(_),..}=>true,
        Op::Bit{kind:BitKind::Set|BitKind::Reset|BitKind::Complement,operand:Operand::Memory(_),..}=>true,
        Op::Exchange{destination:Operand::Memory(_),..}|Op::CompareExchangePair{..}=>true,
        _=>false
    }
}
fn string_kind(opcode:u8)->Option<StringKind>{match opcode{
    0xa4|0xa5=>Some(StringKind::Movs),0xa6|0xa7=>Some(StringKind::Cmps),
    0xaa|0xab=>Some(StringKind::Stos),0xac|0xad=>Some(StringKind::Lods),
    0xae|0xaf=>Some(StringKind::Scas),_=>None
}}
fn one(mode:Mode,pc:u64,b:&[u8])->Result<(usize,Op,u8,Option<Segment>,bool),Local>{
    let mut i=0;
    let mut rex=0u8;
    let mut override16=false;let mut address_override=false;let mut segment=None;let mut group1=None;
    while let Some(prefix)=b.get(i){match *prefix{
        0x66 if !override16=>{override16=true;i+=1;},
        0x67 if !address_override=>{address_override=true;i+=1;},
        0x66|0x67=>return Err(Local::Unsupported),
        v @ (0xf0|0xf2|0xf3)=>{if group1.is_some(){return Err(Local::Unsupported);}group1=Some(v);i+=1;},
        v if segment_prefix(v).is_some()=>{
            let seg=segment_prefix(v).unwrap();
            if segment.is_some()||mode==Mode::X64&&!matches!(seg,Segment::Fs|Segment::Gs){return Err(Local::Unsupported);}
            segment=Some(seg);i+=1;
        },
        _=>break
    }}
    if mode==Mode::X64&&b.get(i).is_some_and(|v|(0x40..=0x4f).contains(v)){
        rex=b[i];i+=1;
    }
    let opcode=*b.get(i).ok_or(Local::Truncated)?;
    // The escape byte alone is not enough to select a mandatory-prefix map.
    // Classify a missing secondary opcode before rejecting unsupported forms.
    if opcode==0x0f{take(b,i+1,1)?;}
    let locked=group1==Some(0xf0);
    let (n,op)=if let Some(kind)=string_kind(opcode){
        // Conservatively accept only REX.W, not ignored register-extension bits.
        if rex!=0&&rex!=0x48||locked{return Err(Local::Unsupported);}
        let compare=matches!(kind,StringKind::Cmps|StringKind::Scas);
        let repeat=match group1{
            None=>Repeat::None,Some(0xf3) if compare=>Repeat::Repe,Some(0xf3)=>Repeat::Rep,
            Some(0xf2) if compare=>Repeat::Repne,_=>return Err(Local::Unsupported)
        };
        // Segment override applies to source only, never fixed ES destination.
        if segment.is_some()&&!matches!(kind,StringKind::Movs|StringKind::Cmps|StringKind::Lods){return Err(Local::Unsupported);}
        let width=if opcode&1==0{8}else if rex&8!=0{64}else if override16{16}else{32};
        (i+1,Op::String{kind,width,repeat})
    }else if group1==Some(0xf3)&&opcode==0x90{
        if rex!=0||override16||address_override||segment.is_some(){return Err(Local::Unsupported);}
        (i+1,Op::Pause)
    }else if opcode==0x0f&&b.get(i+1).copied().and_then(packed_kind).is_some(){
        let secondary=b[i+1];let (mut kind,lane_bits)=packed_kind(secondary).unwrap();
        // 66 selects XMM rather than MMX. F3 selects MOVDQU only.
        if rex&8!=0||locked{return Err(Local::Unsupported);}
        match (override16,group1){
            (true,None)=>{},
            (false,Some(0xf3)) if matches!(secondary,0x6f|0x7f)=>kind=PackedKind::MoveUnaligned,
            _=>return Err(Local::Unsupported)
        }
        let (end,reg,rm)=modrm(mode,pc,b,i+2,rex,address_override)?;
        let rm=xmm_operand(rm)?;let reg=XmmOperand::Register(reg);
        let (destination,source)=if secondary==0x7f{(rm,reg)}else{(reg,rm)};
        let op=Op::PackedInteger{kind,lane_bits,destination,source};
        if segment.is_some()&&!explicit_memory(op){return Err(Local::Unsupported);}
        (end,op)
    }else if opcode==0x0f&&matches!(b.get(i+1),Some(0x2a|0x2c|0x2d)){
        // Scalar signed integer conversions: F3=single, F2=double. REX.W selects 64-bit integer.
        if override16||locked{return Err(Local::Unsupported);}
        let float_bits=match group1{Some(0xf3)=>32,Some(0xf2)=>64,_=>return Err(Local::Unsupported)};
        let int_bits=if rex&8!=0{64}else{32};
        let kind=match b[i+1]{0x2a=>ConversionKind::IntToFloat,0x2c=>ConversionKind::FloatToIntTruncated,_=>ConversionKind::FloatToIntRounded};
        let (end,reg,rm)=modrm(mode,pc,b,i+2,rex,address_override)?;
        let to_float=kind==ConversionKind::IntToFloat;
        let destination=if to_float{ConversionOperand::Xmm(reg)}else{ConversionOperand::Gpr(reg)};
        let source=conversion_rm(rm,to_float)?;
        let op=Op::ScalarConvert{kind,float_bits,int_bits,destination,source};
        if segment.is_some()&&!explicit_memory(op){return Err(Local::Unsupported);}
        (end,op)
    }else if opcode==0x0f&&b.get(i+1).copied().and_then(sse_kind).is_some(){
        let secondary=b[i+1];
        let kind=sse_kind(secondary).unwrap();
        // No conflicting mandatory prefixes, ignored REX.W, or LOCK in this subset.
        if locked||rex&8!=0||override16&&group1.is_some(){return Err(Local::Unsupported);}
        let format=match group1{
            Some(0xf3)=>FloatFormat::ScalarSingle,Some(0xf2)=>FloatFormat::ScalarDouble,
            None if override16=>FloatFormat::PackedDouble,None=>FloatFormat::PackedSingle,_=>return Err(Local::Unsupported)
        };
        if matches!(format,FloatFormat::ScalarSingle|FloatFormat::ScalarDouble)&&matches!(kind,SseKind::MoveAligned|SseKind::And|SseKind::AndNot|SseKind::Or|SseKind::Xor){return Err(Local::Unsupported);}
        let (end,reg,rm)=modrm(mode,pc,b,i+2,rex,address_override)?;
        let rm=xmm_operand(rm)?;let reg=XmmOperand::Register(reg);
        let (destination,source)=if matches!(secondary,0x11|0x29){(rm,reg)}else{(reg,rm)};
        let op=Op::Sse{kind,format,destination,source};
        if segment.is_some()&&!explicit_memory(op){return Err(Local::Unsupported);}
        (end,op)
    }else if group1==Some(0xf3)&&opcode==0x0f{
        let secondary=take(b,i+1,1)?[0];
        let kind=match secondary{0xb8=>CountKind::Population,0xbc=>CountKind::TrailingZeros,0xbd=>CountKind::LeadingZeros,_=>return Err(Local::Unsupported)};
        let width=if rex&8!=0{64}else if override16{16}else{32};
        let (end,destination,source)=modrm(mode,pc,b,i+2,rex,address_override)?;
        let op=Op::CountBits{kind,width,destination,source};
        if segment.is_some()&&!explicit_memory(op){return Err(Local::Unsupported);}
        (end,op)
    }else{
        if matches!(group1,Some(0xf2|0xf3)){return Err(Local::Unsupported);}
        let (n,op)=one_opcode(mode,pc,b,i,rex,override16,address_override)?;
        if segment.is_some()&&!explicit_memory(op){return Err(Local::Unsupported);}
        if locked&&!lockable(op){return Err(Local::Unsupported);}
        (n,op)
    };
    let address_width=match (mode,address_override){(Mode::X86,false)|(Mode::X64,true)=>32,(Mode::X86,true)=>16,(Mode::X64,false)=>64};
    // Keep the architectural instruction-length limit explicit.
    if n>15{return Err(Local::Unsupported);}
    Ok((n,op,address_width,segment,locked))
}
fn one_opcode(mode:Mode,pc:u64,b:&[u8],mut i:usize,rex:u8,override16:bool,address_override:bool)->Result<(usize,Op),Local>{
    let opcode=*b.get(i).ok_or(Local::Truncated)?;i+=1;
    // Only one REX and only on the forms explicitly supported below.
    // Unique 66/67 in either order before optional single REX.
    // 67 is accepted only for explicitly supported memory forms, not ignored prefixes.
    if address_override&&!matches!(opcode,0x00..=0x03|0x08..=0x0b|0x10..=0x13|0x18..=0x1b|0x20..=0x23|0x28..=0x2b|0x30..=0x33|0x38..=0x3b|0x69|0x6b|0x80|0x81|0x83|0x84..=0x87|0x88..=0x8b|0x8d|0xc0|0xc1|0xc6|0xc7|0xd0..=0xd3|0xf6|0xf7|0xff|0x0f){return Err(Local::Unsupported);}
    let operand_width=if rex&8!=0{64}else if override16{16}else{32};
    if (0xb0..=0xb7).contains(&opcode){
        let raw=u64::from(take(b,i,1)?[0]);
        return Ok((i+1,Op::BinaryImmediate{kind:BinaryKind::Mov,width:8,operand:byte_register((opcode&7)|((rex&1)<<3),rex),immediate:Immediate{encoded_bits:8,raw,value:raw}}));
    }
    if (0xb8..=0xbf).contains(&opcode){
        let width=operand_width;
        let n=match width{64=>8,16=>2,_=>4};
        let raw=take(b,i,n)?;
        let mut padded=[0u8;8];padded[..n].copy_from_slice(raw);
        return Ok((i+n,Op::MoveImmediate{register:(opcode&7)|((rex&1)<<3),width,value:u64::from_le_bytes(padded)}));
    }
    if (0x50..=0x5f).contains(&opcode){
        return Ok((i,Op::PushPop{pop:opcode>=0x58,register:(opcode&7)|((rex&1)<<3),width:if override16{16}else if mode==Mode::X64{64}else{32}}));
    }
    if matches!(opcode,0x86|0x87){
        let (end,reg,rm)=modrm(mode,pc,b,i,rex,address_override)?;
        let width=if opcode==0x86{8}else{operand_width};
        let (destination,source)=if width==8{(byte_operand(rm,rex),byte_register(reg,rex))}else{(rm,Operand::Register(reg))};
        return Ok((end,Op::Exchange{kind:ExchangeKind::Xchg,width,destination,source}));
    }
    // 90 and prefixed 90 stay under the existing conservative NOP policy.
    if (0x91..=0x97).contains(&opcode){
        if rex&6!=0{return Err(Local::Unsupported);}
        return Ok((i,Op::Exchange{kind:ExchangeKind::Xchg,width:operand_width,destination:Operand::Register(0),source:Operand::Register((opcode&7)|((rex&1)<<3))}));
    }
    let binary=match opcode{
        0x88..=0x8b=>Some(BinaryKind::Mov),0x00..=0x03=>Some(BinaryKind::Add),
        0x08..=0x0b=>Some(BinaryKind::Or),0x10..=0x13=>Some(BinaryKind::Adc),0x18..=0x1b=>Some(BinaryKind::Sbb),0x20..=0x23=>Some(BinaryKind::And),
        0x28..=0x2b=>Some(BinaryKind::Sub),0x30..=0x33=>Some(BinaryKind::Xor),
        0x38..=0x3b=>Some(BinaryKind::Cmp),0x84|0x85=>Some(BinaryKind::Test),_=>None
    };
    if let Some(kind)=binary{
        let (n,reg,rm)=modrm(mode,pc,b,i,rex,address_override)?;
        let width=if opcode&1==0{8}else{operand_width};
        let (reg,rm)=if width==8{(byte_register(reg,rex),byte_operand(rm,rex))}else{(Operand::Register(reg),rm)};
        let (destination,source)=if opcode&2!=0{(reg,rm)}else{(rm,reg)};
        return Ok((n,Op::Binary{kind,width,destination,source}));
    }
    if opcode==0x8d{
        let (n,reg,rm)=modrm(mode,pc,b,i,rex,address_override)?;
        let Operand::Memory(memory)=rm else{return Err(Local::Unsupported);};
        return Ok((n,Op::Lea{width:operand_width,destination:reg,memory}));
    }
    // Group 2: preserve encoded counts, not computed flag or register values.
    if matches!(opcode,0xc0|0xc1|0xd0..=0xd3){
        if rex&4!=0{return Err(Local::Unsupported);}
        let selector=(take(b,i,1)?[0]>>3)&7;
        let kind=match selector{0=>ShiftKind::Rol,1=>ShiftKind::Ror,2=>ShiftKind::Rcl,3=>ShiftKind::Rcr,4=>ShiftKind::Shl,5=>ShiftKind::Shr,7=>ShiftKind::Sar,_=>return Err(Local::Unsupported)};
        let width=if opcode&1==0{8}else{operand_width};
        let (at,_,rm)=modrm(mode,pc,b,i,rex,address_override)?;
        let (end,count)=match opcode{0xc0|0xc1=>(at+1,ShiftCount::Immediate(take(b,at,1)?[0])),0xd0|0xd1=>(at,ShiftCount::One),_=>(at,ShiftCount::Cl)};
        let operand=if width==8{byte_operand(rm,rex)}else{rm};
        return Ok((end,Op::Shift{kind,width,operand:finish_rip(mode,pc,end,operand),count}));
    }
    // Group selectors are the raw three ModRM bits, not extended by REX.R.
    // This subset conservatively excludes REX.R on group opcodes.
    if matches!(opcode,0x80|0x81|0x83|0xc6|0xc7|0xf6|0xf7|0xff){
        if rex&4!=0{return Err(Local::Unsupported);}
        let selector=(take(b,i,1)?[0]>>3)&7;
        let width=if matches!(opcode,0x80|0xc6|0xf6){8}else{operand_width};
        if opcode==0xff{
            let kind=match selector{0=>UnaryKind::Inc,1=>UnaryKind::Dec,2=>UnaryKind::Call,4=>UnaryKind::Jump,6=>UnaryKind::Push,_=>return Err(Local::Unsupported)};
            let (end,_,operand)=modrm(mode,pc,b,i,rex,address_override)?;
            if override16&&matches!(kind,UnaryKind::Call|UnaryKind::Jump){return Err(Local::Unsupported);}
            let width=if matches!(kind,UnaryKind::Call|UnaryKind::Jump|UnaryKind::Push)&&mode==Mode::X64{if override16{16}else{64}}else{width};
            return Ok((end,Op::Unary{kind,width,operand}));
        }
        if matches!(opcode,0xf6|0xf7)&&selector>=2{
            let kind=match selector{2=>UnaryKind::Not,3=>UnaryKind::Neg,4=>UnaryKind::Mul,5=>UnaryKind::Imul,6=>UnaryKind::Div,_=>UnaryKind::Idiv};
            let (end,_,operand)=modrm(mode,pc,b,i,rex,address_override)?;
            return Ok((end,Op::Unary{kind,width,operand:if width==8{byte_operand(operand,rex)}else{operand}}));
        }
        let kind=match opcode{
            0x80|0x81|0x83=>[BinaryKind::Add,BinaryKind::Or,BinaryKind::Adc,BinaryKind::Sbb,BinaryKind::And,BinaryKind::Sub,BinaryKind::Xor,BinaryKind::Cmp][selector as usize],
            0xc6|0xc7 if selector==0=>BinaryKind::Mov,
            0xf6|0xf7 if selector==0=>BinaryKind::Test,
            _=>return Err(Local::Unsupported)
        };
        let (at,_,operand)=modrm(mode,pc,b,i,rex,address_override)?;
        let operand=if width==8{byte_operand(operand,rex)}else{operand};
        let n=if width==8||opcode==0x83{1}else if width==16{2}else{4};
        let value=immediate(b,at,n,width)?;
        let end=at+n;
        return Ok((end,Op::BinaryImmediate{kind,width,operand:finish_rip(mode,pc,end,operand),immediate:value}));
    }
    if matches!(opcode,0x05|0x0d|0x15|0x1d|0x25|0x2d|0x35|0x3d|0xa9){
        let kind=match opcode{0x05=>BinaryKind::Add,0x0d=>BinaryKind::Or,0x15=>BinaryKind::Adc,0x1d=>BinaryKind::Sbb,
            0x25=>BinaryKind::And,0x2d=>BinaryKind::Sub,0x35=>BinaryKind::Xor,0x3d=>BinaryKind::Cmp,_=>BinaryKind::Test};
        let width=operand_width;
        let n=if width==16{2}else{4};
        let value=immediate(b,i,n,width)?;
        return Ok((i+n,Op::BinaryImmediate{kind,width,operand:Operand::Register(0),immediate:value}));
    }
    // Selected unprefixed two-byte legacy map; mandatory F3 count forms handled above.
    if opcode==0x0f{
        let secondary=take(b,i,1)?[0];
        if matches!(secondary,0xb0|0xb1|0xc0|0xc1){
            i+=1;
            let (end,reg,rm)=modrm(mode,pc,b,i,rex,address_override)?;
            let width=if secondary&1==0{8}else{operand_width};
            let (destination,source)=if width==8{(byte_operand(rm,rex),byte_register(reg,rex))}else{(rm,Operand::Register(reg))};
            let kind=if secondary<0xc0{ExchangeKind::Cmpxchg}else{ExchangeKind::Xadd};
            return Ok((end,Op::Exchange{kind,width,destination,source}));
        }
        if secondary==0xc7{
            i+=1;
            if override16||rex&4!=0||(take(b,i,1)?[0]>>3)&7!=1{return Err(Local::Unsupported);}
            let (end,_,rm)=modrm(mode,pc,b,i,rex,address_override)?;
            let Operand::Memory(memory)=rm else{return Err(Local::Unsupported);};
            return Ok((end,Op::CompareExchangePair{width:if rex&8!=0{128}else{64},memory}));
        }
        if secondary==0xae{
            i+=1;
            if rex!=0||override16||address_override{return Err(Local::Unsupported);}
            let kind=match take(b,i,1)?[0]{0xe8=>FenceKind::Load,0xf0=>FenceKind::Full,0xf8=>FenceKind::Store,_=>return Err(Local::Unsupported)};
            return Ok((i+1,Op::Fence{kind}));
        }
        if matches!(secondary,0xa4|0xa5|0xac|0xad){
            i+=1;
            let (at,reg,rm)=modrm(mode,pc,b,i,rex,address_override)?;
            let (end,count)=if secondary&1==0{(at+1,ShiftCount::Immediate(take(b,at,1)?[0]))}else{(at,ShiftCount::Cl)};
            return Ok((end,Op::DoubleShift{right:secondary&8!=0,width:operand_width,destination:finish_rip(mode,pc,end,rm),source:reg,count}));
        }
        if matches!(secondary,0xa3|0xab|0xb3|0xbb|0xba){
            i+=1;
            let kind=if secondary==0xba{
                if rex&4!=0{return Err(Local::Unsupported);}
                match (take(b,i,1)?[0]>>3)&7{4=>BitKind::Test,5=>BitKind::Set,6=>BitKind::Reset,7=>BitKind::Complement,_=>return Err(Local::Unsupported)}
            }else{match secondary{0xa3=>BitKind::Test,0xab=>BitKind::Set,0xb3=>BitKind::Reset,_=>BitKind::Complement}};
            let (at,reg,rm)=modrm(mode,pc,b,i,rex,address_override)?;
            let (end,index)=if secondary==0xba{(at+1,BitIndex::Immediate(take(b,at,1)?[0]))}else{(at,BitIndex::Register(reg))};
            return Ok((end,Op::Bit{kind,width:operand_width,operand:finish_rip(mode,pc,end,rm),index}));
        }
        if matches!(secondary,0xbc|0xbd){
            i+=1;
            let (end,reg,rm)=modrm(mode,pc,b,i,rex,address_override)?;
            return Ok((end,Op::BitScan{reverse:secondary==0xbd,width:operand_width,destination:reg,source:rm}));
        }
        if matches!(secondary,0xb6|0xb7|0xbe|0xbf|0xaf|0x40..=0x4f|0x90..=0x9f){
            i+=1;
            // SETcc has a reserved/ignored reg field; accept canonical /0 only.
            if (0x90..=0x9f).contains(&secondary)&&(rex&4!=0||take(b,i,1)?[0]&0x38!=0){
                return Err(Local::Unsupported);
            }
            let (end,reg,rm)=modrm(mode,pc,b,i,rex,address_override)?;
            let op=match secondary{
                0xb6|0xb7|0xbe|0xbf=>{
                    let source_width=if secondary&1==0{8}else{16};
                    if source_width>=operand_width{return Err(Local::Unsupported);}
                    Op::ExtendMove{signed:secondary&8!=0,destination_width:operand_width,source_width,destination:reg,source:if source_width==8{byte_operand(rm,rex)}else{rm}}
                },
                0xaf=>Op::Multiply{width:operand_width,destination:reg,source:rm},
                0x40..=0x4f=>Op::ConditionalMove{condition:secondary&15,width:operand_width,destination:reg,source:rm},
                _=>Op::SetCondition{condition:secondary&15,destination:byte_operand(rm,rex)}
            };
            return Ok((end,op));
        }
    }
    if matches!(opcode,0x69|0x6b){
        let (at,reg,rm)=modrm(mode,pc,b,i,rex,address_override)?;
        let n=if opcode==0x6b{1}else if operand_width==16{2}else{4};
        let value=immediate(b,at,n,operand_width)?;
        let end=at+n;
        return Ok((end,Op::MultiplyImmediate{width:operand_width,destination:reg,source:finish_rip(mode,pc,end,rm),immediate:value}));
    }
    if rex!=0||override16||address_override{return Err(Local::Unsupported);}
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
            Ok((n,op,address_width,segment_override,locked))=>{
                instructions.push(Instruction{address:pc+i as u64,bytes:bytes[i..i+n].to_vec(),op,address_width,segment_override,locked});
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
