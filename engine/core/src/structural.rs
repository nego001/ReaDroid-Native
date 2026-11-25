//! Bounded header checks, not full-file validation or execution.
use crate::{ReadSession,format::FormatHint};
use std::io::{self,Read,Seek};

pub const MAX_HEADER_BYTES: usize=64;
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum ByteOrder { Little, Big }
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Header {
    Elf { bits:u8, byte_order:ByteOrder, machine:u16 },
    Png { width:u32,height:u32,bit_depth:u8,color_type:u8 },
}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Issue { Truncated, Signature, Field, Checksum, TableBounds }
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Verdict { HeaderChecked(Header), Malformed(Issue), Unsupported }
/// Checks only the selected header subset, using the existing read budget.
/// I/O, budget exhaustion and cancellation propagate as errors. No content
/// decoding, executable loading, section traversal or snapshot attestation.
pub fn inspect<R:Read+Seek>(s:&mut ReadSession<R>,hint:FormatHint)->io::Result<Verdict>{
    let limit=match hint { FormatHint::Elf=>64,FormatHint::Png=>33,_=>return Ok(Verdict::Unsupported) };
    let length=s.len();
    let b=s.read_window(0,length.min(limit) as usize)?.bytes;
    Ok(match hint {FormatHint::Elf=>elf(&b,length),FormatHint::Png=>png(&b),_=>unreachable!()})
}
fn integer(b:&[u8],o:ByteOrder)->u64 {
    match o {
        ByteOrder::Big=>b.iter().fold(0,|n,&x|(n<<8)|u64::from(x)),
        ByteOrder::Little=>b.iter().rev().fold(0,|n,&x|(n<<8)|u64::from(x)),
    }
}
fn table_ok(offset:u64,size:u64,count:u64,expected:u64,header:u64,length:u64)->bool {
    if count==0 { return offset==0; }
    offset>=header && size==expected &&
        size.checked_mul(count).and_then(|n|offset.checked_add(n)).is_some_and(|end|end<=length)
}
fn elf(b:&[u8],length:u64)->Verdict {
    use Issue::*;
    if b.len()<16 { return Verdict::Malformed(Truncated); }
    if &b[..4]!=b"\x7fELF" { return Verdict::Malformed(Signature); }
    let (bits,h,ph,sh,phoff,shoff,ehsize)=match b[4] {
        1=>(32,52,32,40,28,32,40),2=>(64,64,56,64,32,40,52),
        _=>return Verdict::Malformed(Field)
    };
    let order=match b[5]{1=>ByteOrder::Little,2=>ByteOrder::Big,_=>return Verdict::Malformed(Field)};
    if b.len()<h {return Verdict::Malformed(Truncated);}
    let get=|offset:usize,n:usize|integer(&b[offset..offset+n],order);
    if b[6]!=1 || get(20,4)!=1 || get(ehsize,2)!=h as u64 {
        return Verdict::Malformed(Field);
    }
    let word=if bits==32 {4}else{8};
    let po=get(phoff,word);let so=get(shoff,word);
    let pe=get(ehsize+2,2);let pn=get(ehsize+4,2);
    let se=get(ehsize+6,2);let sn=get(ehsize+8,2);let si=get(ehsize+10,2);
    // Extended numbering needs section zero; deliberately not interpreted.
    if pn==0xffff || si==0xffff || (sn==0 && so!=0) {return Verdict::Unsupported;}
    if !table_ok(po,pe,pn,ph,h as u64,length) || !table_ok(so,se,sn,sh,h as u64,length) {
        return Verdict::Malformed(TableBounds);
    }
    if si!=0 && si>=sn {return Verdict::Malformed(Field);}
    Verdict::HeaderChecked(Header::Elf {bits,byte_order:order,machine:get(18,2) as u16})
}
fn crc32(b:&[u8])->u32 {
    let mut crc=u32::MAX;
    for &byte in b {
        crc^=u32::from(byte);
        for _ in 0..8 { crc=if crc&1!=0 {(crc>>1)^0xedb88320}else{crc>>1}; }
    }
    !crc
}
fn png(b:&[u8])->Verdict {
    use Issue::*;
    if b.len()<33 {return Verdict::Malformed(Truncated);}
    if &b[..8]!=b"\x89PNG\r\n\x1a\n" {return Verdict::Malformed(Signature);}
    let u32_at=|n:usize|u32::from_be_bytes(b[n..n+4].try_into().unwrap());
    if u32_at(8)!=13 || &b[12..16]!=b"IHDR" {return Verdict::Malformed(Field);}
    let width=u32_at(16);let height=u32_at(20);let depth=b[24];let color=b[25];
    let allowed=match color {
        0=>matches!(depth,1|2|4|8|16),2|4|6=>matches!(depth,8|16),3=>matches!(depth,1|2|4|8),_=>false
    };
    if width==0 || height==0 || width>0x7fffffff || height>0x7fffffff || !allowed ||
        b[26]!=0 || b[27]!=0 || b[28]>1 {return Verdict::Malformed(Field);}
    if crc32(&b[12..29])!=u32_at(29) {return Verdict::Malformed(Checksum);}
    Verdict::HeaderChecked(Header::Png {width,height,bit_depth:depth,color_type:color})
}
