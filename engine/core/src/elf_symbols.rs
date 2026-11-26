//! Bounded ELF section-name and symbol-table inspection. Reports raw name
//! bytes, not trusted display text. No demangling, relocations or execution.
use crate::{ReadSession,elf_structure::{self,Class,Order,Image,Verdict,Section}};
use std::io::{self,Read,Seek};
pub const MAX_PAGE:usize=128;
pub const MAX_NAME_BYTES:usize=256;
#[derive(Debug,Clone,PartialEq,Eq)]
pub enum Name{Absent,Bytes(Vec<u8>),TooLong}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum SectionRef{Undefined,Index(u16),Reserved(u16),ExtendedUnsupported}
#[derive(Debug,PartialEq,Eq)]
pub struct NamedSection{pub index:usize,pub header:Section,pub name:Name}
#[derive(Debug,PartialEq,Eq)]
pub struct Symbol{
    pub index:u64,pub name:Name,pub value:u64,pub size:u64,
    pub binding:u8,pub kind:u8,pub visibility:u8,pub other:u8,pub section:SectionRef,
}
#[derive(Debug,PartialEq,Eq)]
pub struct Page<T>{pub entries:Vec<T>,pub total:u64,pub next:Option<u64>}
pub struct Inspector<R:Read+Seek>{session:ReadSession<R>,image:Image}
fn invalid(s:&'static str)->io::Error{io::Error::new(io::ErrorKind::InvalidInput,s)}
fn malformed(s:&'static str)->io::Error{io::Error::new(io::ErrorKind::InvalidData,s)}
fn unsupported(s:&'static str)->io::Error{io::Error::new(io::ErrorKind::Unsupported,s)}
fn number(b:&[u8],at:usize,n:usize,o:Order)->u64{
    match o{
        Order::Big=>b[at..at+n].iter().fold(0,|a,&v|(a<<8)|u64::from(v)),
        Order::Little=>b[at..at+n].iter().rev().fold(0,|a,&v|(a<<8)|u64::from(v)),
    }
}
fn page_end(start:u64,total:u64,limit:usize)->io::Result<u64>{
    if limit==0||limit>MAX_PAGE||start>total{return Err(invalid("invalid ELF page"));}
    Ok(start+(total-start).min(limit as u64))
}
impl<R:Read+Seek> Inspector<R>{
    /// Structural report is built from this same owned source and kept private.
    pub fn open(mut session:ReadSession<R>)->io::Result<Self>{
        let image=match elf_structure::inspect(&mut session)?{
            Verdict::Checked(i)=>i,
            Verdict::Malformed(_)=>return Err(malformed("ELF structural subset rejected")),
            Verdict::Unsupported(_)=>return Err(unsupported("ELF structural subset unsupported")),
        };
        Ok(Self{session,image})
    }
    pub fn image(&self)->&Image{&self.image}
    pub fn remaining_budget(&self)->u64{self.session.remaining_budget()}
    fn string_table(&mut self,index:usize)->io::Result<Section>{
        let t=self.image.sections.get(index).ok_or_else(||malformed("string table index"))?.clone();
        if t.kind!=3||t.size==0{return Err(malformed("invalid string table"));}
        if t.flags&0x800!=0{return Err(unsupported("compressed string table"));}
        let end=t.offset.checked_add(t.size).filter(|&e|e<=self.session.len()).ok_or_else(||malformed("string table extent"))?;
        if self.session.read_window(t.offset,1)?.bytes[0]!=0||
            (t.size>1&&self.session.read_window(end-1,1)?.bytes[0]!=0){
            return Err(malformed("string table boundary"));
        }
        Ok(t)
    }
    fn name(&mut self,t:&Section,index:u32)->io::Result<Name>{
        let at=u64::from(index);
        if at>=t.size{return Err(malformed("name offset outside string table"));}
        let size=(t.size-at).min((MAX_NAME_BYTES+1) as u64) as usize;
        let w=self.session.read_window(t.offset+at,size)?;
        if let Some(n)=w.bytes.iter().position(|&b|b==0){
            return Ok(Name::Bytes(w.bytes[..n].to_vec()));
        }
        if size==MAX_NAME_BYTES+1{return Ok(Name::TooLong);}
        Err(malformed("unterminated name"))
    }
    pub fn sections(&mut self,start:u64,limit:usize)->io::Result<Page<NamedSection>>{
        self.session.cancellation.check()?;
        let total=self.image.sections.len() as u64;
        let end=page_end(start,total,limit)?;
        let t=if start<end{match self.image.section_names{Some(i)=>Some(self.string_table(i)?),None=>None}}else{None};
        let mut entries=Vec::with_capacity((end-start) as usize);
        for index in start..end{
            self.session.cancellation.check()?;
            let header=self.image.sections[index as usize].clone();
            let name=match &t{
                Some(t)=>self.name(t,header.name_offset)?,
                None=>Name::Absent,
            };
            entries.push(NamedSection{index:index as usize,header,name});
        }
        self.session.cancellation.check()?;
        Ok(Page{entries,total,next:(end<total).then_some(end)})
    }
    /// Explicitly selected SHT_SYMTAB or SHT_DYNSYM; no implicit table scan.
    /// Raw values are not automatically converted to addresses or interpreted
    /// as functions. SHN_XINDEX remains explicitly unresolved.
    pub fn symbols(&mut self,index:usize,start:u64,limit:usize)->io::Result<Page<Symbol>>{
        self.session.cancellation.check()?;
        let t=self.image.sections.get(index).ok_or_else(||invalid("symbol table index"))?.clone();
        if !matches!(t.kind,2|11){return Err(invalid("not a symbol table"));}
        if t.flags&0x800!=0{return Err(unsupported("compressed symbol table"));}
        let width=if self.image.class==Class::Elf32{16}else{24};
        if t.entry_size!=width||t.size%width!=0||t.size==0{return Err(malformed("symbol table size"));}
        let total=t.size/width;
        if u64::from(t.info)>total{return Err(malformed("symbol local boundary"));}
        let end=page_end(start,total,limit)?;
        let mut entries=Vec::with_capacity((end-start) as usize);
        if start<end{
            let names=self.string_table(t.link as usize)?;
            let offset=t.offset.checked_add(start*width).ok_or_else(||malformed("symbol offset"))?;
            let raw=self.session.read_window(offset,((end-start)*width) as usize)?.bytes;
            for (i,b) in raw.chunks_exact(width as usize).enumerate(){
                self.session.cancellation.check()?;
                let g=|a,n|number(b,a,n,self.image.order);
                let name_index=g(0,4) as u32;
                let (value,size,info,other,sh)=if width==16{(g(4,4),g(8,4),b[12],b[13],g(14,2) as u16)}
                    else{(g(8,8),g(16,8),b[4],b[5],g(6,2) as u16)};
                let section=match sh{
                    0=>SectionRef::Undefined,0xffff=>SectionRef::ExtendedUnsupported,
                    0xff00..=0xfffe=>SectionRef::Reserved(sh),
                    _ if usize::from(sh)<self.image.sections.len()=>SectionRef::Index(sh),
                    _=>return Err(malformed("symbol section index")),
                };
                let name=self.name(&names,name_index)?;
                entries.push(Symbol{index:start+i as u64,name,value,size,binding:info>>4,kind:info&15,
                    visibility:other&3,other,section});
            }
        }
        self.session.cancellation.check()?;
        Ok(Page{entries,total,next:(end<total).then_some(end)})
    }
}
