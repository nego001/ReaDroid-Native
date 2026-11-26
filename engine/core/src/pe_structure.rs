//! PE32/PE32+ structural subset: headers and section extents, not a loader,
//! signature validator, disassembler, or proof that a program is executable.
use crate::ReadSession;
use std::io::{self,Read,Seek};
pub const MAX_SECTIONS:usize=96;
pub const MAX_OPTIONAL_BYTES:usize=4096;
pub const MAX_DIRECTORIES:usize=16;
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Kind{Pe32,Pe32Plus}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Issue{Truncated,Signature,Field,TableBounds,RawBounds,VirtualBounds,Overlap}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Unsupported{OptionalMagic,OptionalSize,DirectoryCount}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Mapping{FileOffset(u64),VirtualOnly,Unmapped}
#[derive(Debug,Clone,PartialEq,Eq)]
pub struct Section{
    pub name:[u8;8],pub virtual_size:u32,pub rva:u32,
    pub raw_size:u32,pub raw_offset:u32,pub characteristics:u32,
}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub struct Directory{pub address:u32,pub size:u32}
#[derive(Debug,PartialEq,Eq)]
pub struct Image{
    pub kind:Kind,pub machine:u16,pub characteristics:u16,pub entry_rva:u32,
    pub image_base:u64,pub image_size:u32,pub header_size:u32,
    pub section_alignment:u32,pub file_alignment:u32,
    pub directories:Vec<Directory>,pub sections:Vec<Section>,
}
#[derive(Debug,PartialEq,Eq)]
pub enum Verdict{Checked(Image),Malformed(Issue),Unsupported(Unsupported)}
fn u16_at(b:&[u8],i:usize)->u16{u16::from_le_bytes(b[i..i+2].try_into().unwrap())}
fn u32_at(b:&[u8],i:usize)->u32{u32::from_le_bytes(b[i..i+4].try_into().unwrap())}
fn u64_at(b:&[u8],i:usize)->u64{u64::from_le_bytes(b[i..i+8].try_into().unwrap())}
fn overlap(a:(u64,u64),b:(u64,u64))->bool{a.0<b.1&&b.0<a.1}
impl Image{
    /// One RVA in the checked extent model, not OS loader behavior. Raw
    /// padding may be mapped by this model. Directory addresses are NOT
    /// automatically interpreted as RVAs (certificate index 4 is a file offset).
    /// Public report fields can be modified by callers; ambiguity fails closed.
    pub fn map_rva(&self,rva:u32)->Mapping{
        if rva>=self.image_size{return Mapping::Unmapped;}
        let at=u64::from(rva);
        let mut found=if rva<self.header_size{Some(Mapping::FileOffset(at))}else{None};
        for s in &self.sections{
            let start=u64::from(s.rva);
            let size=u64::from(s.virtual_size.max(s.raw_size));
            if at>=start&&at-start<size{
                if found.is_some(){return Mapping::Unmapped;}
                let delta=at-start;
                found=Some(if delta<u64::from(s.raw_size){Mapping::FileOffset(u64::from(s.raw_offset)+delta)}else{Mapping::VirtualOnly});
            }
        }
        found.unwrap_or(Mapping::Unmapped)
    }
}
pub fn inspect<R:Read+Seek>(s:&mut ReadSession<R>)->io::Result<Verdict>{
    use Issue::*;
    let length=s.len();
    s.cancellation.check()?;
    if length<64{return Ok(Verdict::Malformed(Truncated));}
    let dos=s.read_window(0,64)?.bytes;
    if &dos[..2]!=b"MZ"{return Ok(Verdict::Malformed(Signature));}
    let pe=u64::from(u32_at(&dos,60));
    if pe<64||pe+24>length{return Ok(Verdict::Malformed(TableBounds));}
    let coff=s.read_window(pe,24)?.bytes;
    if &coff[..4]!=b"PE\0\0"{return Ok(Verdict::Malformed(Signature));}
    let machine=u16_at(&coff,4);let count=u16_at(&coff,6) as usize;
    let opt_len=u16_at(&coff,20) as usize;
    if machine==0||count==0||count>MAX_SECTIONS||opt_len<2{return Ok(Verdict::Malformed(Field));}
    if opt_len>MAX_OPTIONAL_BYTES{return Ok(Verdict::Unsupported(Unsupported::OptionalSize));}
    let table_size=count*40;
    let table_start=pe+24+opt_len as u64;
    let table_end=table_start+table_size as u64;
    if table_end>length{return Ok(Verdict::Malformed(TableBounds));}
    if (opt_len+table_size) as u64>s.remaining_budget(){
        return Err(io::Error::new(io::ErrorKind::Other,"PE structure exceeds remaining budget"));
    }
    let opt=s.read_window(pe+24,opt_len)?.bytes;
    let (kind,min,base)=match u16_at(&opt,0){
        0x10b=>(Kind::Pe32,96,28),
        0x20b=>(Kind::Pe32Plus,112,24),
        _=>return Ok(Verdict::Unsupported(Unsupported::OptionalMagic))
    };
    if opt_len<min{return Ok(Verdict::Malformed(Field));}
    let dirs=u32_at(&opt,min-4) as u64;
    if dirs>(opt_len-min) as u64/8{return Ok(Verdict::Malformed(TableBounds));}
    if dirs>MAX_DIRECTORIES as u64{return Ok(Verdict::Unsupported(Unsupported::DirectoryCount));}
    let image_size=u32_at(&opt,56);let header_size=u32_at(&opt,60);
    let section_alignment=u32_at(&opt,32);let file_alignment=u32_at(&opt,36);
    if section_alignment==0||file_alignment==0||image_size==0||header_size==0||
        header_size>image_size||u64::from(header_size)<table_end||u64::from(header_size)>length{
        return Ok(Verdict::Malformed(Field));
    }
    let directory_table=(0..dirs as usize).map(|i|Directory{address:u32_at(&opt,min+8*i),size:u32_at(&opt,min+8*i+4)}).collect();
    let table=s.read_window(table_start,table_size)?.bytes;
    let mut sections:Vec<Section>=Vec::with_capacity(count);
    let mut raw=Vec::with_capacity(count);let mut virtual_ranges=Vec::with_capacity(count);
    for row in table.chunks_exact(40){
        s.cancellation.check()?;
        let sec=Section{name:row[..8].try_into().unwrap(),virtual_size:u32_at(row,8),rva:u32_at(row,12),
            raw_size:u32_at(row,16),raw_offset:u32_at(row,20),characteristics:u32_at(row,36)};
        if sec.raw_size!=0{
            let start=u64::from(sec.raw_offset);let end=start+u64::from(sec.raw_size);
            if start<u64::from(header_size)||end>length{return Ok(Verdict::Malformed(RawBounds));}
            if raw.iter().any(|&r|overlap(r,(start,end))){return Ok(Verdict::Malformed(Overlap));}
            raw.push((start,end));
        }
        let extent=u64::from(sec.virtual_size.max(sec.raw_size));
        if extent!=0{
            let start=u64::from(sec.rva);let end=start+extent;
            if start<u64::from(header_size)||end>u64::from(image_size){return Ok(Verdict::Malformed(VirtualBounds));}
            if virtual_ranges.iter().any(|&r|overlap(r,(start,end))){return Ok(Verdict::Malformed(Overlap));}
            virtual_ranges.push((start,end));
        }
        sections.push(sec);
    }
    s.cancellation.check()?;
    Ok(Verdict::Checked(Image{kind,machine,characteristics:u16_at(&coff,22),entry_rva:u32_at(&opt,16),
        image_base:if kind==Kind::Pe32{u64::from(u32_at(&opt,base))}else{u64_at(&opt,base)},
        image_size,header_size,section_alignment,file_alignment,directories:directory_table,sections}))
}
