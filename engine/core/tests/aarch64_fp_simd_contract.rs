//! Fixed words independently assembled with clang --target=aarch64-linux-gnu
//! and checked with llvm-objdump; parameter sweeps exercise selected encodings.
use negrodroid_core::aarch64_decode::{self,Op,FpFormat as F,FpBinaryKind as B,FpUnaryKind as U,VectorLogicalKind as V};
fn one(w:u32)->Op{aarch64_decode::decode(0,&w.to_le_bytes()).unwrap()[0].op}
#[test]
fn assembled_scalar_binary_goldens(){
    for (word,kind,format,d,l,r) in [(0x1e222820,B::Add,F::Single,0,1,2),(0x1e653883,B::Sub,F::Double,3,4,5),
        (0x1e2808e6,B::Mul,F::Single,6,7,8),(0x1e6b1949,B::Div,F::Double,9,10,11),
        (0x1e2e49ac,B::Max,F::Single,12,13,14),(0x1e715a0f,B::Min,F::Double,15,16,17)]{
        assert_eq!(one(word),Op::FpBinary{kind,format,destination:d,left:l,right:r});
    }
}
#[test]
fn assembled_scalar_unary_goldens(){
    for (word,kind,format,d,s) in [(0x1e2043e0,U::Move,F::Single,0,31),(0x1e60c041,U::Abs,F::Double,1,2),
        (0x1e214083,U::Neg,F::Single,3,4),(0x1e61c0c5,U::Sqrt,F::Double,5,6)]{
        assert_eq!(one(word),Op::FpUnary{kind,format,destination:d,source:s});
    }
}
#[test]
fn scalar_formats_and_register_extremes(){
    for (base,kind) in [(0x1e200800,B::Mul),(0x1e201800,B::Div),(0x1e202800,B::Add),(0x1e203800,B::Sub),
        (0x1e204800,B::Max),(0x1e205800,B::Min)]{
        for (flag,format) in [(0,F::Single),(1<<22,F::Double)]{
            assert_eq!(one(base|flag|(31<<16)|(31<<5)|31),Op::FpBinary{kind,format,destination:31,left:31,right:31});
        }
    }
}
#[test]
fn other_scalar_formats_and_opcodes_unknown(){
    for word in [0x1ea02800,0x1ee02800,0x1e206800,0x1e207800,0x1ea04000,0x1ee04000,0x1e224000]{
        assert_eq!(one(word),Op::Unknown,"{word:08x}");
    }
}
#[test]
fn assembled_vector_arithmetic_goldens(){
    for (word,subtract,vector_bits,element_bits,d,l,r) in [(0x0e228420,false,64,8,0,1,2),
        (0x4ee28420,false,128,64,0,1,2),(0x6ea58483,true,128,32,3,4,5)]{
        assert_eq!(one(word),Op::VectorArithmetic{subtract,vector_bits,element_bits,destination:d,left:l,right:r});
    }
}
#[test]
fn vector_arrangements_and_reserved_one_d(){
    for q in 0..2u32{for u in 0..2u32{for size in 0..4u32{
        let w=0x0e208400|(q<<30)|(u<<29)|(size<<22)|(31<<16)|(30<<5)|29;
        let expected=if q==0&&size==3{Op::Unknown}else{Op::VectorArithmetic{subtract:u!=0,
            vector_bits:if q==0{64}else{128},element_bits:8u8<<size,destination:29,left:30,right:31}};
        assert_eq!(one(w),expected);
    }}}
}
#[test]
fn assembled_vector_logic_goldens(){
    for (w,kind,bits,d,l,r) in [(0x0e221c20,V::And,64,0,1,2),(0x4ea51c83,V::Orr,128,3,4,5),
        (0x6e281ce6,V::Eor,128,6,7,8),(0x0e6b1d49,V::Bic,64,9,10,11)]{
        assert_eq!(one(w),Op::VectorLogical{kind,vector_bits:bits,destination:d,left:l,right:r});
    }
}
#[test]
fn vector_logic_widths_and_exclusions(){
    for (base,kind) in [(0x0e201c00,V::And),(0x0e601c00,V::Bic),(0x0ea01c00,V::Orr),(0x2e201c00,V::Eor)]{
        for q in 0..2u32{
            assert_eq!(one(base|(q<<30)|(31<<16)|(31<<5)|31),Op::VectorLogical{kind,vector_bits:if q==0{64}else{128},destination:31,left:31,right:31});
        }
    }
    for w in [0x0ee01c00,0x2e601c00,0x2ea01c00,0x2ee01c00,0x5ee08400]{assert_eq!(one(w),Op::Unknown);}
}
#[test]
fn fp_simd_not_general_register_semantics(){
    for w in [0x1e222820,0x1e2043e0,0x0e228420,0x6e281ce6]{assert_eq!(one(w).arithmetic_registers(),None);}
    assert!(one(0x91000420).arithmetic_registers().is_some());
}
#[test]
fn mixed_word_stream_preserved(){
    let words=[0x1e222820u32,0x0e228420,0x1e61c0c5,0x91000420,0x6e281ce6,0xffffffff];
    let bytes:Vec<_>=words.iter().flat_map(|w|w.to_le_bytes()).collect();
    let p=aarch64_decode::decode(0x1000,&bytes).unwrap();
    assert_eq!(p.iter().map(|i|i.word).collect::<Vec<_>>(),words);
    assert_eq!(p[5].address,0x1014);assert_eq!(p[5].op,Op::Unknown);
}
