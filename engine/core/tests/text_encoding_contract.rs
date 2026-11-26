use negrodroid_core::{Cancellation,ReadSession,text_encoding::{decode,read,Encoding,Kind,Error,Unit,MAX_TEXT_BYTES}};
use std::io::{self,Cursor};
fn unit(offset:u64,length:u8,kind:Kind)->Unit{Unit{offset,length,kind}}
#[test]
fn ascii_preserves_controls_and_flags_high_bytes(){
    let d=decode(Encoding::Ascii,7,&[0,65,127,128,255]).unwrap();
    assert_eq!(d.units,vec![unit(7,1,Kind::Scalar('\0')),unit(8,1,Kind::Scalar('A')),unit(9,1,Kind::Scalar('\u{7f}')),unit(10,1,Kind::Invalid),unit(11,1,Kind::Invalid)]);
    assert_eq!(d.incomplete_at(),None);
}
#[test]
fn utf8_scalars_exact_byte_addresses_and_bom(){
    let s="\u{feff}Aé€😀\u{202e}";
    let d=decode(Encoding::Utf8,100,s.as_bytes()).unwrap();
    let expected:Vec<_>=s.char_indices().map(|(i,c)|unit(100+i as u64,c.len_utf8() as u8,Kind::Scalar(c))).collect();
    assert_eq!(d.units,expected);assert_eq!(d.byte_count,s.len());
}
#[test]
fn utf8_rejects_overlong_surrogate_and_out_of_range(){
    for b in [&[0xc0,0xaf][..],&[0xed,0xa0,0x80],&[0xf4,0x90,0x80,0x80],&[0x80]]{
        let d=decode(Encoding::Utf8,0,b).unwrap();
        assert!(d.units.iter().all(|u|u.kind==Kind::Invalid));
        assert_eq!(d.units.iter().map(|u|u.length as usize).sum::<usize>(),b.len());
    }
}
#[test]
fn utf8_invalid_prefix_and_incomplete_tail_distinct(){
    let d=decode(Encoding::Utf8,0,&[0xe2,0x82,b'A',0xf0,0x9f]).unwrap();
    assert_eq!(d.units,vec![unit(0,2,Kind::Invalid),unit(2,1,Kind::Scalar('A')),unit(3,2,Kind::Incomplete)]);
    assert_eq!(d.incomplete_at(),Some(3));
}
#[test]
fn utf16_both_endians_surrogate_pairs_and_bom(){
    let text="\u{feff}Aé😀";
    for (encoding,little) in [(Encoding::Utf16Le,true),(Encoding::Utf16Be,false)]{
        let bytes:Vec<u8>=text.encode_utf16().flat_map(|w|if little{w.to_le_bytes()}else{w.to_be_bytes()}).collect();
        let d=decode(encoding,1,&bytes).unwrap();
        assert_eq!(d.units,vec![unit(1,2,Kind::Scalar('\u{feff}')),unit(3,2,Kind::Scalar('A')),unit(5,2,Kind::Scalar('é')),unit(7,4,Kind::Scalar('😀'))]);
    }
}
#[test]
fn utf16_unpaired_and_split_units(){
    let d=decode(Encoding::Utf16Le,0,&[0,0xd8,65,0,0,0xdc,0,0xd8,0x12]).unwrap();
    assert_eq!(d.units,vec![unit(0,2,Kind::Invalid),unit(2,2,Kind::Scalar('A')),unit(4,2,Kind::Invalid),unit(6,3,Kind::Incomplete)]);
    assert_eq!(d.incomplete_at(),Some(6));
    assert_eq!(decode(Encoding::Utf16Be,9,&[0x12]).unwrap().units,vec![unit(9,1,Kind::Incomplete)]);
}
#[test]
fn every_two_byte_window_is_partitioned(){
    for a in 0..=255u8{for b in 0..=255u8{
        for enc in [Encoding::Ascii,Encoding::Utf8,Encoding::Utf16Le,Encoding::Utf16Be]{
            let d=decode(enc,19,&[a,b]).unwrap();
            let mut end=19;
            for (i,u) in d.units.iter().enumerate(){
                assert_eq!(u.offset,end);assert!(u.length>0);
                end+=u.length as u64;
                if u.kind==Kind::Incomplete{assert_eq!(i+1,d.units.len());}
            }
            assert_eq!(end,21);
        }
    }}
}
#[test]
fn size_offset_and_empty_limits(){
    assert_eq!(decode(Encoding::Utf8,0,&vec![0;MAX_TEXT_BYTES+1]),Err(Error::WindowLimit));
    assert_eq!(decode(Encoding::Utf8,u64::MAX,&[1]),Err(Error::OffsetOverflow));
    assert!(decode(Encoding::Utf8,u64::MAX,&[]).unwrap().units.is_empty());
    assert_eq!(decode(Encoding::Ascii,u64::MAX-1,&[65]).unwrap().units[0].offset,u64::MAX-1);
}
#[test]
fn read_tail_replay_and_cancellation_charge(){
    let c=Cancellation::default();
    let mut s=ReadSession::new(Cursor::new("A😀".as_bytes()),5,7,c.clone());
    let a=read(&mut s,Encoding::Utf8,0,3).unwrap();
    assert_eq!(a.decoded.incomplete_at(),Some(1));assert!(a.has_after);
    let b=read(&mut s,Encoding::Utf8,1,4096).unwrap();
    assert_eq!(b.decoded.units,vec![unit(1,4,Kind::Scalar('😀'))]);
    assert!(!b.has_after);assert_eq!(s.remaining_budget(),0);
    assert!(read(&mut s,Encoding::Utf8,0,1).is_err());
    c.cancel();
    assert_eq!(read(&mut s,Encoding::Utf8,5,1).unwrap_err().kind(),io::ErrorKind::Interrupted);
}
