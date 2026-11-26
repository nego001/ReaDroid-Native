//! ELF32/ELF64 structural subset, not a loader, ABI validator or executable
//! integrity proof. No segment payload, section names, symbols or code read.
use crate::ReadSession;
use std::io::{self,Read,Seek};
pub const MAX_PROGRAM_HEADERS:usize=256;
pub const MAX_SECTION_HEADERS:usize=4096;
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Class{Elf32,Elf64}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Order{Little,Big}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Issue{Truncated,Signature,Field,TableBounds,FileBounds,VirtualBounds,Alignment}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Unsupported{ExtendedNumbering,TableLimit}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Mapping{FileOffset(u64),VirtualOnly,Unmapped,Ambiguous}
#[derive(Debug,Clone,PartialEq,Eq)]
pub struct Segment{pub kind:u32,pub flags:u32,pub offset:u64,pub vaddr:u64,pub file_size:u64,pub memory_size:u64,pub alignment:u64}
#[derive(Debug,Clone,PartialEq,Eq)]
pub struct Section{pub name_offset:u32,pub kind:u32,pub flags:u64,pub address:u64,pub offset:u64,pub size:u64,pub link:u32,pub info:u32,pub alignment:u64,pub entry_size:u64}
#[derive(Debug,PartialEq,Eq)]
pub struct Image{
    pub class:Class,pub order:Order,pub kind:u16,pub machine:u16,pub entry:u64,pub flags:u32,
    pub section_names:Option<usize>,pub segments:Vec<Segment>,pub sections:Vec<Section>,
}
#[derive(Debug,PartialEq,Eq)]
pub enum Verdict{Checked(Image),Malformed(Issue),Unsupported(Unsupported)}
fn number(b:&[u8],at:usize,n:usize,o:Order)->u64{
    let bytes=&b[at..at+n];
    match o{
        Order::Big=>bytes.iter().fold(0,|a,&b|(a<<8)|u64::from(b)),
        Order::Little=>bytes.iter().rev().fold(0,|a,&b|(a<<8)|u64::from(b)),
    }
}
fn alignment(a:u64)->bool{a==0||a.is_power_of_two()}
fn extent(offset:u64,size:u64,length:u64)->bool{
    offset.checked_add(size).is_some_and(|end|end<=length)
}
fn table(offset:u64,count:usize,size:usize,header:usize,length:u64)->bool{
    if count==0{return offset==0;}
    offset>=header as u64&&extent(offset,(count*size) as u64,length)
}
impl Image{
    /// Positional mapping through declared PT_LOAD byte extents only.
    /// Overlapping loads are ambiguous; alignment padding is not mapped.
    pub fn map_vaddr(&self,address:u64)->Mapping{
        let mut found=None;
        for p in &self.segments{
            if p.kind!=1||address<p.vaddr{continue;}
            let delta=address-p.vaddr;
            if delta>=p.memory_size{continue;}
            if found.is_some(){return Mapping::Ambiguous;}
            found=Some(if delta<p.file_size{
                match p.offset.checked_add(delta){Some(n)=>Mapping::FileOffset(n),None=>Mapping::Unmapped}
            }else{Mapping::VirtualOnly});
        }
        found.unwrap_or(Mapping::Unmapped)
    }
}
pub fn inspect<R:Read+Seek>(s:&mut ReadSession<R>)->io::Result<Verdict>{
    use Issue::*;
    let length=s.len();s.cancellation.check()?;
    if length<16{return Ok(Verdict::Malformed(Truncated));}
    let ident=s.read_window(0,16)?.bytes;
    if &ident[..4]!=b"\x7fELF"{return Ok(Verdict::Malformed(Signature));}
    let (class,h,pw,sw,word)=match ident[4]{
        1=>(Class::Elf32,52,32,40,4),2=>(Class::Elf64,64,56,64,8),
        _=>return Ok(Verdict::Malformed(Field))
    };
    let order=match ident[5]{1=>Order::Little,2=>Order::Big,_=>return Ok(Verdict::Malformed(Field))};
    if ident[6]!=1{return Ok(Verdict::Malformed(Field));}
    if length<h as u64{return Ok(Verdict::Malformed(Truncated));}
    let mut header=ident;
    header.extend(s.read_window(16,h-16)?.bytes);
    let get=|at,n|number(&header,at,n,order);
    let off=if class==Class::Elf32{40}else{52};
    if get(20,4)!=1||get(off,2)!=h as u64{return Ok(Verdict::Malformed(Field));}
    let po=get(24+word,word);let so=get(24+2*word,word);
    let pn=get(off+4,2) as usize;let sn=get(off+8,2) as usize;let si=get(off+10,2) as usize;
    if pn==0xffff||si==0xffff||(sn==0&&so!=0){return Ok(Verdict::Unsupported(Unsupported::ExtendedNumbering));}
    if pn>MAX_PROGRAM_HEADERS||sn>MAX_SECTION_HEADERS{return Ok(Verdict::Unsupported(Unsupported::TableLimit));}
    if (pn!=0&&get(off+2,2)!=pw as u64)||(sn!=0&&get(off+6,2)!=sw as u64)||
        !table(po,pn,pw,h,length)||!table(so,sn,sw,h,length){
        return Ok(Verdict::Malformed(TableBounds));
    }
    if si!=0&&si>=sn{return Ok(Verdict::Malformed(Field));}
    if ((pn*pw)+(sn*sw)) as u64>s.remaining_budget(){return Err(io::Error::new(io::ErrorKind::Other,"ELF tables exceed remaining budget"));}
    let mut segments=Vec::with_capacity(pn);
    if pn!=0{
        let bytes=s.read_window(po,pn*pw)?.bytes;
        for row in bytes.chunks_exact(pw){
            s.cancellation.check()?;
            let g=|a,n|number(row,a,n,order);
            let p=if class==Class::Elf32{
                Segment{kind:g(0,4) as u32,flags:g(24,4) as u32,offset:g(4,4),vaddr:g(8,4),file_size:g(16,4),memory_size:g(20,4),alignment:g(28,4)}
            }else{
                Segment{kind:g(0,4) as u32,flags:g(4,4) as u32,offset:g(8,8),vaddr:g(16,8),file_size:g(32,8),memory_size:g(40,8),alignment:g(48,8)}
            };
            if p.kind!=0{
                if p.file_size!=0&&!extent(p.offset,p.file_size,length){return Ok(Verdict::Malformed(FileBounds));}
                if !alignment(p.alignment){return Ok(Verdict::Malformed(Alignment));}
                if p.kind==1{
                    if p.file_size>p.memory_size||p.vaddr.checked_add(p.memory_size).is_none()||
                        (class==Class::Elf32&&p.vaddr+p.memory_size>1u64<<32){return Ok(Verdict::Malformed(VirtualBounds));}
                    if p.alignment>1&&p.offset%p.alignment!=p.vaddr%p.alignment{return Ok(Verdict::Malformed(Alignment));}
                }
            }
            segments.push(p);
        }
    }
    let mut sections=Vec::with_capacity(sn);
    if sn!=0{
        let bytes=s.read_window(so,sn*sw)?.bytes;
        for (i,row) in bytes.chunks_exact(sw).enumerate(){
            s.cancellation.check()?;
            let g=|a,n|number(row,a,n,order);
            let z=Section{name_offset:g(0,4) as u32,kind:g(4,4) as u32,flags:g(8,word),
                address:g(8+word,word),offset:g(8+2*word,word),size:g(8+3*word,word),
                link:g(8+4*word,4) as u32,info:g(12+4*word,4) as u32,
                alignment:g(16+4*word,word),entry_size:g(16+5*word,word)};
            if i==0&&z.kind!=0{return Ok(Verdict::Malformed(Field));}
            if z.kind!=0{
                // SHT_NOBITS has an extent in memory but no file payload.
                if z.kind!=8&&z.size!=0&&!extent(z.offset,z.size,length){return Ok(Verdict::Malformed(FileBounds));}
                if !alignment(z.alignment){return Ok(Verdict::Malformed(Alignment));}
                if z.flags&2!=0&&(z.address.checked_add(z.size).is_none()||
                    (class==Class::Elf32&&z.address+z.size>1u64<<32)){return Ok(Verdict::Malformed(VirtualBounds));}
            }
            sections.push(z);
        }
    }
    if si!=0&&sections[si].kind!=3{return Ok(Verdict::Malformed(Field));}
    s.cancellation.check()?;
    Ok(Verdict::Checked(Image{class,order,kind:get(16,2) as u16,machine:get(18,2) as u16,
        entry:get(24,word),flags:get(off-4,4) as u32,section_names:(si!=0).then_some(si),segments,sections}))
}
