//! Bounded classic COFF symbol records in PE images, not import/export
//! directories, PDB, BigObj, auxiliary record interpretation or execution.
use crate::{ReadSession,pe_structure::{self,Image,Verdict}};
use std::io::{self,Read,Seek};
pub const MAX_PAGE:usize=128;
pub const MAX_NAME_BYTES:usize=256;
const RECORD:u64=18;
#[derive(Debug,Clone,PartialEq,Eq)]
pub enum Name{Bytes(Vec<u8>),TooLong}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum SectionRef{Undefined,Absolute,Debug,Index(u16)}
#[derive(Debug,PartialEq,Eq)]
pub struct Symbol{
    pub record_index:u64,pub name:Name,pub value:u32,pub section:SectionRef,
    pub type_code:u16,pub storage_class:u8,pub auxiliary_count:u8,
}
#[derive(Debug,PartialEq,Eq)]
pub struct Page{pub entries:Vec<Symbol>,pub raw_total:u64,pub next_record:Option<u64>}
struct Table{offset:u64,count:u64,strings:u64,string_size:u64}
pub struct Inspector<R:Read+Seek>{session:ReadSession<R>,image:Image,table:Option<Table>,cursor:u64}
fn malformed(s:&'static str)->io::Error{io::Error::new(io::ErrorKind::InvalidData,s)}
fn invalid(s:&'static str)->io::Error{io::Error::new(io::ErrorKind::InvalidInput,s)}
fn u16_at(b:&[u8],i:usize)->u16{u16::from_le_bytes(b[i..i+2].try_into().unwrap())}
fn u32_at(b:&[u8],i:usize)->u32{u32::from_le_bytes(b[i..i+4].try_into().unwrap())}
impl<R:Read+Seek> Inspector<R>{
    /// Owns the same stable source used for structural inspection. Zero
    /// pointer/count is an absent classic table, common in stripped images.
    pub fn open(mut session:ReadSession<R>)->io::Result<Self>{
        let image=match pe_structure::inspect(&mut session)?{
            Verdict::Checked(i)=>i,
            Verdict::Malformed(_)=>return Err(malformed("PE structural subset rejected")),
            Verdict::Unsupported(_)=>return Err(io::Error::new(io::ErrorKind::Unsupported,"PE structural subset unsupported")),
        };
        let dos=session.read_window(0,64)?.bytes;
        let pe=u64::from(u32_at(&dos,60));
        let coff=session.read_window(pe,24)?.bytes;
        if &dos[..2]!=b"MZ"||&coff[..4]!=b"PE\0\0"{return Err(malformed("PE header changed"));}
        let offset=u64::from(u32_at(&coff,12));let count=u64::from(u32_at(&coff,16));
        let table=if offset==0&&count==0{None}else{
            if offset<u64::from(image.header_size)||count==0{return Err(malformed("COFF symbol pointer/count"));}
            let strings=offset+count*RECORD;
            if strings+4>session.len(){return Err(malformed("COFF symbol extent"));}
            let n=session.read_window(strings,4)?.bytes;
            let string_size=u64::from(u32_at(&n,0));
            let end=strings+string_size;
            if string_size<4||end>session.len(){return Err(malformed("COFF string extent"));}
            for sec in &image.sections{
                let start=u64::from(sec.raw_offset);let stop=start+u64::from(sec.raw_size);
                if sec.raw_size!=0&&offset<stop&&start<end{return Err(malformed("COFF table overlaps section payload"));}
            }
            Some(Table{offset,count,strings,string_size})
        };
        session.cancellation.check()?;
        Ok(Self{session,image,table,cursor:0})
    }
    pub fn image(&self)->&Image{&self.image}
    pub fn raw_total(&self)->u64{self.table.as_ref().map_or(0,|t|t.count)}
    pub fn cursor(&self)->u64{self.cursor}
    pub fn remaining_budget(&self)->u64{self.session.remaining_budget()}
    /// Explicit restart; no arbitrary seek into auxiliary records.
    pub fn restart(&mut self)->io::Result<()>{
        self.session.cancellation.check()?;self.cursor=0;Ok(())
    }
    /// Each page counts primary symbols, raw_total includes auxiliary records.
    /// Auxiliary payloads are skipped by declared extent, not validated.
    /// On failure no result/cursor is committed; admitted reads remain charged.
    pub fn next(&mut self,limit:usize)->io::Result<Page>{
        self.session.cancellation.check()?;
        if limit==0||limit>MAX_PAGE{return Err(invalid("invalid COFF page limit"));}
        let Some(t)=&self.table else{return Ok(Page{entries:vec![],raw_total:0,next_record:None});};
        let mut pos=self.cursor;
        let mut entries=Vec::with_capacity(limit);
        while pos<t.count&&entries.len()<limit{
            self.session.cancellation.check()?;
            let b=self.session.read_window(t.offset+pos*RECORD,RECORD as usize)?.bytes;
            let aux=b[17];
            let next=pos+1+u64::from(aux);
            if next>t.count{return Err(malformed("COFF auxiliary extent"));}
            let section=match u16_at(&b,12) as i16{
                0=>SectionRef::Undefined,-1=>SectionRef::Absolute,-2=>SectionRef::Debug,
                n if n>0&&n as usize<=self.image.sections.len()=>SectionRef::Index(n as u16),
                _=>return Err(malformed("COFF section reference")),
            };
            let name=if b[..4]==[0;4]{
                let at=u64::from(u32_at(&b,4));
                if at<4||at>=t.string_size{return Err(malformed("COFF string offset"));}
                let size=(t.string_size-at).min((MAX_NAME_BYTES+1) as u64) as usize;
                let w=self.session.read_window(t.strings+at,size)?;
                match w.bytes.iter().position(|&v|v==0){
                    Some(n)=>Name::Bytes(w.bytes[..n].to_vec()),
                    None if size==MAX_NAME_BYTES+1=>Name::TooLong,
                    None=>return Err(malformed("unterminated COFF name")),
                }
            }else{
                let n=b[..8].iter().position(|&v|v==0).unwrap_or(8);
                Name::Bytes(b[..n].to_vec())
            };
            entries.push(Symbol{record_index:pos,name,value:u32_at(&b,8),section,
                type_code:u16_at(&b,14),storage_class:b[16],auxiliary_count:aux});
            pos=next;
        }
        self.session.cancellation.check()?;
        self.cursor=pos;
        Ok(Page{entries,raw_total:t.count,next_record:(pos<t.count).then_some(pos)})
    }
}
