//! Bounded header checks, not full-file validation or execution.
use crate::{ReadSession,format::FormatHint};
use std::io::{self,Read,Seek};

pub const MAX_HEADER_BYTES: usize=112;
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum ByteOrder { Little, Big }
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Header {
    Elf { bits:u8, byte_order:ByteOrder, machine:u16 },
    Png { width:u32,height:u32,bit_depth:u8,color_type:u8 },
    Pe { bits:u8,machine:u16,sections:u16 },
    Dex { version:u8,byte_order:ByteOrder,file_size:u32 },
    ZipLocal { method:u16,compressed:u32,uncompressed:u32 },
    ZipEmpty,
}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Issue { Truncated, Signature, Field, Checksum, TableBounds }
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Verdict { HeaderChecked(Header), Malformed(Issue), Unsupported }
/// Checks only the selected header subset, using the existing read budget.
/// I/O, budget exhaustion and cancellation propagate as errors. No content
/// decoding, executable loading, section traversal or snapshot attestation.
pub fn inspect<R:Read+Seek>(s:&mut ReadSession<R>,hint:FormatHint)->io::Result<Verdict>{
    if hint==FormatHint::PortableExecutable {return pe(s);}
    let limit=match hint { FormatHint::Elf=>64,FormatHint::Png=>33,FormatHint::Dex=>112,FormatHint::Zip=>30,_=>return Ok(Verdict::Unsupported) };
    let length=s.len();
    let b=s.read_window(0,length.min(limit) as usize)?.bytes;
    Ok(match hint {FormatHint::Elf=>elf(&b,length),FormatHint::Png=>png(&b),FormatHint::Dex=>dex(&b,length),FormatHint::Zip=>zip(&b,length),_=>unreachable!()})
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

fn le16(b:&[u8],i:usize)->u16 {u16::from_le_bytes(b[i..i+2].try_into().unwrap())}
fn le32(b:&[u8],i:usize)->u32 {u32::from_le_bytes(b[i..i+4].try_into().unwrap())}
fn pe<R:Read+Seek>(s:&mut ReadSession<R>)->io::Result<Verdict>{
    use Issue::*;
    let length=s.len();
    let dos=s.read_window(0,length.min(64) as usize)?.bytes;
    if dos.len()<64 {return Ok(Verdict::Malformed(Truncated));}
    if &dos[..2]!=b"MZ" {return Ok(Verdict::Malformed(Signature));}
    let off=u64::from(le32(&dos,60));
    if off<64 || off.checked_add(26).is_none_or(|end|end>length) {
        return Ok(Verdict::Malformed(TableBounds));
    }
    let b=s.read_window(off,26)?.bytes;
    if &b[..4]!=b"PE\0\0" {return Ok(Verdict::Malformed(Signature));}
    let machine=le16(&b,4);let sections=le16(&b,6);let optional=u64::from(le16(&b,20));
    let (bits,minimum)=match le16(&b,24) {
        0x10b=>(32,96),0x20b=>(64,112),0x107=>return Ok(Verdict::Unsupported),
        _=>return Ok(Verdict::Malformed(Field))
    };
    if machine==0 || sections==0 || sections>96 || optional<minimum {
        return Ok(Verdict::Malformed(Field));
    }
    if off.checked_add(24).and_then(|n|n.checked_add(optional))
        .and_then(|n|n.checked_add(u64::from(sections)*40)).is_none_or(|end|end>length){
        return Ok(Verdict::Malformed(TableBounds));
    }
    Ok(Verdict::HeaderChecked(Header::Pe{bits,machine,sections}))
}
fn dex(b:&[u8],length:u64)->Verdict{
    use Issue::*;
    if b.len()<112{return Verdict::Malformed(Truncated);}
    if &b[..4]!=b"dex\n" || b[7]!=0{return Verdict::Malformed(Signature);}
    let version=match &b[4..7]{
        b"035"=>35,b"037"=>37,b"038"=>38,b"039"=>39,b"040"=>40,
        _=>return Verdict::Unsupported
    };
    let order=match le32(b,40){0x12345678=>ByteOrder::Little,0x78563412=>return Verdict::Unsupported,_=>return Verdict::Malformed(Field)};
    let get=|i:usize|u64::from(le32(b,i));
    if get(32)!=length || get(36)!=112{return Verdict::Malformed(Field);}
    let data_size=get(104);let data_off=get(108);let map=get(52);
    if data_off<112 || data_off%4!=0 || data_size==0 || data_off.checked_add(data_size)!=Some(length)
        || map<data_off || map%4!=0 || map.checked_add(4).is_none_or(|end|end>length){
        return Verdict::Malformed(TableBounds);
    }
    for (i,width) in [(44,1),(56,4),(64,4),(72,12),(80,8),(88,8),(96,32)]{
        let count=get(i);let off=get(i+4);
        if count==0 {if off!=0{return Verdict::Malformed(Field);}}
        else if off<112 || off%4!=0 || count.checked_mul(width).and_then(|n|off.checked_add(n)).is_none_or(|end|end>length){
            return Verdict::Malformed(TableBounds);
        }
    }
    Verdict::HeaderChecked(Header::Dex{version,byte_order:order,file_size:length as u32})
}
fn zip(b:&[u8],length:u64)->Verdict{
    use Issue::*;
    if b.len()<4{return Verdict::Malformed(Truncated);}
    match &b[..4]{
        b"PK\x03\x04"=>{
            if b.len()<30{return Verdict::Malformed(Truncated);}
            let flags=le16(b,6);let method=le16(b,8);
            let compressed=le32(b,18);let uncompressed=le32(b,22);
            let name=le16(b,26);let extra=le16(b,28);
            // Data descriptors, encryption and ZIP64 need separate parsing.
            if flags&0x2049!=0 || compressed==u32::MAX || uncompressed==u32::MAX
                || le16(b,4)>=45{return Verdict::Unsupported;}
            if name==0 || (method==0 && compressed!=uncompressed){return Verdict::Malformed(Field);}
            let end=30+u64::from(name)+u64::from(extra)+u64::from(compressed);
            if end>length{return Verdict::Malformed(TableBounds);}
            Verdict::HeaderChecked(Header::ZipLocal{method,compressed,uncompressed})
        }
        b"PK\x05\x06"=>{
            if b.len()<22{return Verdict::Malformed(Truncated);}
            if b[4..20].iter().any(|&x|x!=0){return Verdict::Unsupported;}
            if 22+u64::from(le16(b,20))!=length{return Verdict::Malformed(TableBounds);}
            Verdict::HeaderChecked(Header::ZipEmpty)
        }
        b"PK\x07\x08"=>Verdict::Unsupported,
        _=>Verdict::Malformed(Signature)
    }
}
