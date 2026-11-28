//! Read-only scalar interpretation of explicitly selected binary bytes.
//! No inferred types, implicit byte order, floating-point arithmetic or writes.
use crate::ReadSession;
use std::io::{self,Read,Seek};

#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Endian{Little,Big}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Type{U8,I8,U16,I16,U32,I32,U64,I64,U128,I128,F32,F64}
impl Type{
    pub const fn width(self)->usize{
        match self{
            Self::U8|Self::I8=>1,
            Self::U16|Self::I16=>2,
            Self::U32|Self::I32|Self::F32=>4,
            Self::U64|Self::I64|Self::F64=>8,
            Self::U128|Self::I128=>16,
        }
    }
}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum FloatClass{Zero,Subnormal,Normal,Infinite,NaN}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Value{
    Unsigned(u128),Signed(i128),
    /// Exact IEEE-754 representation. Never canonicalize NaN payloads.
    Float32{bits:u32,negative:bool,class:FloatClass},
    Float64{bits:u64,negative:bool,class:FloatClass},
}
impl Value{
    /// Explicit bit reinterpretation, not a decimal parsing operation.
    pub fn as_f32(self)->Option<f32>{if let Self::Float32{bits,..}=self{Some(f32::from_bits(bits))}else{None}}
    pub fn as_f64(self)->Option<f64>{if let Self::Float64{bits,..}=self{Some(f64::from_bits(bits))}else{None}}
}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Error{LengthMismatch,OffsetOverflow}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub struct Scalar{pub offset:u64,pub kind:Type,pub endian:Endian,pub value:Value}
fn classify(exponent:u64,mantissa:u64,max_exp:u64)->FloatClass{
    match (exponent,mantissa){
        (0,0)=>FloatClass::Zero,
        (0,_)=>FloatClass::Subnormal,
        (e,0) if e==max_exp=>FloatClass::Infinite,
        (e,_) if e==max_exp=>FloatClass::NaN,
        _=>FloatClass::Normal,
    }
}
/// Exactly one typed scalar. No alignment restriction; byte order and
/// source-relative origin are chosen by the caller. The exclusive end must
/// fit in u64. Integer sign is two's complement.
pub fn inspect(kind:Type,endian:Endian,offset:u64,bytes:&[u8])->Result<Scalar,Error>{
    let width=kind.width();
    if bytes.len()!=width{return Err(Error::LengthMismatch);}
    offset.checked_add(width as u64).ok_or(Error::OffsetOverflow)?;
    let mut full=[0u8;16];
    let bits=match endian{
        Endian::Little=>{full[..width].copy_from_slice(bytes);u128::from_le_bytes(full)},
        Endian::Big=>{full[16-width..].copy_from_slice(bytes);u128::from_be_bytes(full)},
    };
    let value=match kind{
        Type::U8|Type::U16|Type::U32|Type::U64|Type::U128=>Value::Unsigned(bits),
        Type::I8=>Value::Signed((bits as i8) as i128),
        Type::I16=>Value::Signed((bits as i16) as i128),
        Type::I32=>Value::Signed((bits as i32) as i128),
        Type::I64=>Value::Signed((bits as i64) as i128),
        Type::I128=>Value::Signed(bits as i128),
        Type::F32=>{
            let b=bits as u32;
            Value::Float32{bits:b,negative:b>>31!=0,class:classify(((b>>23)&0xff) as u64,(b&0x7fffff) as u64,0xff)}
        }
        Type::F64=>{
            let b=bits as u64;
            Value::Float64{bits:b,negative:b>>63!=0,class:classify((b>>52)&0x7ff,b&0x000f_ffff_ffff_ffff,0x7ff)}
        }
    };
    Ok(Scalar{offset,kind,endian,value})
}
/// Read exactly the selected scalar, never a partial value. Uses cumulative
/// ReadSession reservations; failed admitted reads remain charged.
pub fn read<R:Read+Seek>(session:&mut ReadSession<R>,kind:Type,endian:Endian,offset:u64)->io::Result<Scalar>{
    let window=session.read_window(offset,kind.width())?;
    let scalar=inspect(kind,endian,offset,&window.bytes)
        .map_err(|_|io::Error::new(io::ErrorKind::InvalidData,"scalar interpretation failed"))?;
    session.cancellation.check()?;
    Ok(scalar)
}
