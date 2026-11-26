use negrodroid_core::aarch64_decode::{self,Op,LogicalKind,BitfieldKind,Register};
fn one(w:u32)->Op{aarch64_decode::decode(0,&w.to_le_bytes()).unwrap()[0].op}
fn logical(wide:bool,k:u32,n:u32,r:u32,s:u32)->u32{
    0x12000000|((wide as u32)<<31)|(k<<29)|(n<<22)|(r<<16)|(s<<10)|(31<<5)|31
}
#[test]
fn logical_immediate_known_masks(){
    for (wide,n,r,s,mask) in [(true,1,0,7,0xff),(true,1,8,7,0xff00000000000000),
        (false,0,0,39,0x00ff00ff),(true,0,0,60,0x5555555555555555)]{
        assert_eq!(aarch64_decode::logical_mask(wide,n,r,s),Some(mask));
    }
}
#[test]
fn exhaustive_logical_mask_against_bit_oracle(){
    for wide in [false,true]{for n in 0..2u8{for r in 0..64u8{for s in 0..64u8{
        let width=if wide{64}else{32};
        let mut expected=None;
        if wide||n==0{
            let selector=(u32::from(n)<<6)|u32::from(63-s);
            if let Some(k)=(1..=6).rev().find(|&k|selector&(1<<k)!=0){
                let e=1u32<<k;let run=(u32::from(s)%e)+1;
                if e<=width&&run<e{
                    let mut mask=0u64;
                    for bit in 0..width{
                        if (bit+u32::from(r))%e<run{mask|=1u64<<bit;}
                    }
                    expected=Some(mask);
                }
            }
        }
        assert_eq!(aarch64_decode::logical_mask(wide,n,r,s),expected);
    }}}}
}
#[test]
fn logical_op_fields_and_reserved(){
    for (k,kind) in [(0,LogicalKind::And),(1,LogicalKind::Orr),(2,LogicalKind::Eor),(3,LogicalKind::Ands)]{
        assert_eq!(one(logical(true,k,1,0,7)),Op::LogicalImmediate{kind,wide:true,destination:31,source:31,n:1,immr:0,imms:7,mask:255});
    }
    for w in [logical(false,0,1,0,7),logical(true,0,1,0,63),logical(true,0,0,0,63)]{assert_eq!(one(w),Op::Unknown);}
    assert_eq!(aarch64_decode::logical_mask(true,2,0,0),None);
    assert_eq!(aarch64_decode::logical_mask(true,0,64,0),None);
}
#[test]
fn bitfield_forms_and_width_checks(){
    for wide in [false,true]{for (k,kind) in [(0,BitfieldKind::Signed),(1,BitfieldKind::Merge),(2,BitfieldKind::Unsigned)]{
        let w=0x13000000|((wide as u32)<<31)|(k<<29)|((wide as u32)<<22)|(7<<16)|(13<<10)|(4<<5)|3;
        assert_eq!(one(w),Op::Bitfield{kind,wide,destination:3,source:4,immr:7,imms:13});
    }}
    for w in [0x13400000,0x93000000,0x13200000,0x13008000,0x73400000]{assert_eq!(one(w),Op::Unknown);}
}
#[test]
fn extract_width_and_operands(){
    for wide in [false,true]{
        let w=0x13800000|((wide as u32)<<31)|((wide as u32)<<22)|(9<<16)|(17<<10)|(8<<5)|7;
        assert_eq!(one(w),Op::Extract{wide,destination:7,left:8,right:9,lsb:17});
    }
    for w in [0x13c00000,0x93800000,0x13808000,0x13a00000,0x33800000]{assert_eq!(one(w),Op::Unknown);}
}
#[test]
fn stack_pointer_and_zero_register_add_immediate(){
    let sp=Register::StackPointer{wide:true};let zr=Register::Zero{wide:true};
    assert_eq!(one(0x910003ff).arithmetic_registers(),Some((sp,sp)));
    assert_eq!(one(0xb10003ff).arithmetic_registers(),Some((zr,sp)));
    assert_eq!(one(0x110003ff).arithmetic_registers(),Some((Register::StackPointer{wide:false},Register::StackPointer{wide:false})));
}
#[test]
fn logical_immediate_register_roles(){
    let sp=Register::StackPointer{wide:true};let zr=Register::Zero{wide:true};
    assert_eq!(one(logical(true,0,1,0,7)).arithmetic_registers(),Some((sp,zr)));
    assert_eq!(one(logical(true,3,1,0,7)).arithmetic_registers(),Some((zr,zr)));
}
#[test]
fn register_forms_use_zero_not_stack(){
    let zr=Register::Zero{wide:true};
    assert_eq!(one(0x8b0003ff).arithmetic_registers(),Some((zr,zr)));
    assert_eq!(one(0xaa0003ff).arithmetic_registers(),Some((zr,zr)));
    assert_eq!(one(0xd34003ff).arithmetic_registers(),Some((zr,zr)));
    assert_eq!(one(0xd503201f).arithmetic_registers(),None);
}
#[test]
fn ordinary_registers_and_invalid_constructed_operand(){
    assert_eq!(one(0x91000420).arithmetic_registers(),Some((Register::General{wide:true,index:0},Register::General{wide:true,index:1})));
    assert_eq!(Op::Bitfield{kind:BitfieldKind::Merge,wide:true,destination:32,source:1,immr:0,imms:0}.arithmetic_registers(),None);
}
#[test]
fn mixed_words_retain_raw_and_coordinates(){
    let words=[0x92001fffu32,0xd34003ff,0x93c00000,0x14000000,0xffffffff];
    let bytes:Vec<_>=words.iter().flat_map(|w|w.to_le_bytes()).collect();
    let d=aarch64_decode::decode(0x1000,&bytes).unwrap();
    assert_eq!(d.iter().map(|i|i.word).collect::<Vec<_>>(),words);
    assert!(matches!(d[0].op,Op::LogicalImmediate{..}));
    assert!(matches!(d[1].op,Op::Bitfield{..}));
    assert!(matches!(d[2].op,Op::Extract{..}));
    assert_eq!(d[4].address,0x1010);assert_eq!(d[4].op,Op::Unknown);
}
