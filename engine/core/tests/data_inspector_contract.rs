use negrodroid_core::{Cancellation,ReadSession,data_inspector::{inspect,read,Endian,Type,Value,FloatClass,Error}};
use std::io::{self,Cursor};
fn v(t:Type,e:Endian,b:&[u8])->Value{inspect(t,e,0,b).unwrap().value}
#[test]
fn widths_and_unsigned_endian(){
    for (t,n) in [(Type::U8,1),(Type::U16,2),(Type::U32,4),(Type::U64,8),(Type::U128,16)]{
        assert_eq!(t.width(),n);
        let b:Vec<u8>=(1..=n as u8).collect();
        let big=b.iter().fold(0u128,|a,b|(a<<8)|*b as u128);
        let little=b.iter().rev().fold(0u128,|a,b|(a<<8)|*b as u128);
        assert_eq!(v(t,Endian::Big,&b),Value::Unsigned(big));
        assert_eq!(v(t,Endian::Little,&b),Value::Unsigned(little));
    }
}
#[test]
fn signed_extremes_and_minus_one_all_widths(){
    for (t,n) in [(Type::I8,1),(Type::I16,2),(Type::I32,4),(Type::I64,8),(Type::I128,16)]{
        assert_eq!(t.width(),n);
        for e in [Endian::Little,Endian::Big]{
            assert_eq!(v(t,e,&vec![255;n]),Value::Signed(-1));
            let mut b=vec![0;n];b[if e==Endian::Big{0}else{n-1}]=128;
            assert_eq!(v(t,e,&b),Value::Signed(if n==16{i128::MIN}else{-(1i128<<(n*8-1))}));
            let mut b=vec![255;n];b[if e==Endian::Big{0}else{n-1}]=127;
            assert_eq!(v(t,e,&b),Value::Signed(if n==16{i128::MAX}else{(1i128<<(n*8-1))-1}));
        }
    }
}
#[test]
fn u128_full_precision(){
    let n=0xfedc_ba98_7654_3210_ffff_eeee_dddd_ccccu128;
    assert_eq!(v(Type::U128,Endian::Little,&n.to_le_bytes()),Value::Unsigned(n));
    assert_eq!(v(Type::U128,Endian::Big,&u128::MAX.to_be_bytes()),Value::Unsigned(u128::MAX));
}
#[test]
fn all_float32_classes_preserve_bits(){
    for (bits,class) in [(0u32,FloatClass::Zero),(0x80000000,FloatClass::Zero),(1,FloatClass::Subnormal),(0x807fffff,FloatClass::Subnormal),(0x3f800000,FloatClass::Normal),(0xbf800000,FloatClass::Normal),(0x7f800000,FloatClass::Infinite),(0xff800000,FloatClass::Infinite),(0x7fc01234,FloatClass::NaN),(0xff800001,FloatClass::NaN)]{
        for e in [Endian::Little,Endian::Big]{
            let b=if e==Endian::Little{bits.to_le_bytes()}else{bits.to_be_bytes()};
            let val=v(Type::F32,e,&b);
            assert_eq!(val,Value::Float32{bits,negative:bits>>31!=0,class});
            assert_eq!(val.as_f32().unwrap().to_bits(),bits);
            assert!(val.as_f64().is_none());
        }
    }
}
#[test]
fn all_float64_classes_preserve_bits(){
    for (bits,class) in [(0u64,FloatClass::Zero),(0x8000000000000000,FloatClass::Zero),(1,FloatClass::Subnormal),(0x800fffffffffffff,FloatClass::Subnormal),(0x3ff0000000000000,FloatClass::Normal),(0xbff0000000000000,FloatClass::Normal),(0x7ff0000000000000,FloatClass::Infinite),(0xfff0000000000000,FloatClass::Infinite),(0x7ff8000000001234,FloatClass::NaN),(0xfff0000000000001,FloatClass::NaN)]{
        for e in [Endian::Little,Endian::Big]{
            let b=if e==Endian::Little{bits.to_le_bytes()}else{bits.to_be_bytes()};
            let val=v(Type::F64,e,&b);
            assert_eq!(val,Value::Float64{bits,negative:bits>>63!=0,class});
            assert_eq!(val.as_f64().unwrap().to_bits(),bits);
            assert!(val.as_f32().is_none());
        }
    }
}
#[test]
fn exhaustive_u16_i16_against_standard_library(){
    for n in 0..=u16::MAX{
        for e in [Endian::Little,Endian::Big]{
            let b=if e==Endian::Little{n.to_le_bytes()}else{n.to_be_bytes()};
            assert_eq!(v(Type::U16,e,&b),Value::Unsigned(n as u128));
            assert_eq!(v(Type::I16,e,&b),Value::Signed((n as i16) as i128));
        }
    }
}
#[test]
fn strict_length_and_offset(){
    assert_eq!(inspect(Type::U32,Endian::Big,0,&[1,2,3]),Err(Error::LengthMismatch));
    assert_eq!(inspect(Type::U8,Endian::Little,0,&[1,2]),Err(Error::LengthMismatch));
    assert_eq!(inspect(Type::U8,Endian::Little,u64::MAX,&[1]),Err(Error::OffsetOverflow));
    let s=inspect(Type::U16,Endian::Big,u64::MAX-2,&[1,2]).unwrap();
    assert_eq!(s.offset,u64::MAX-2);assert_eq!(s.value,Value::Unsigned(258));
}
#[test]
fn read_unaligned_scalar_budget_and_cancellation(){
    let c=Cancellation::default();
    let mut s=ReadSession::new(Cursor::new([0,0x12,0x34,0x56,0x78]),5,4,c.clone());
    let a=read(&mut s,Type::U16,Endian::Big,1).unwrap();
    assert_eq!(a.value,Value::Unsigned(0x1234));assert_eq!(a.offset,1);
    assert!(read(&mut s,Type::U32,Endian::Little,1).is_err());
    assert_eq!(s.remaining_budget(),2);
    assert_eq!(read(&mut s,Type::U16,Endian::Little,4).unwrap_err().kind(),io::ErrorKind::UnexpectedEof);
    assert_eq!(s.remaining_budget(),2);
    assert_eq!(read(&mut s,Type::U16,Endian::Little,3).unwrap().value,Value::Unsigned(0x7856));
    c.cancel();
    assert_eq!(read(&mut s,Type::U8,Endian::Big,0).unwrap_err().kind(),io::ErrorKind::Interrupted);
}
#[test]
fn truncated_source_charged_without_partial_scalar(){
    let mut s=ReadSession::new(Cursor::new([1u8]),4,4,Cancellation::default());
    assert_eq!(read(&mut s,Type::F32,Endian::Little,0).unwrap_err().kind(),io::ErrorKind::UnexpectedEof);
    assert_eq!(s.remaining_budget(),0);
}
