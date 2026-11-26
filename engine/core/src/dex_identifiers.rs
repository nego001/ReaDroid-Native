//! Bounded classic DEX identifier inspection. No class-data or bytecode
//! decoding. Strings retain UTF-16 code units (including lone surrogates),
//! not trusted display text. Offsets inside variable regions are candidates,
//! not proof of item boundaries or full DEX validity.
use crate::{ReadSession,dex_structure::{self,Dex,Table,Verdict}};
use std::io::{self,Read,Seek};
pub const MAX_PAGE:usize=128;
pub const MAX_STRING_UNITS:usize=256;
pub const MAX_TYPE_LIST:usize=128;
#[derive(Debug,Clone,PartialEq,Eq)]
pub enum StringValue{Units(Vec<u16>),TooLong{declared_units:u32}}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Kind{String,Type,Prototype,Field,Method,Class}
#[derive(Debug,PartialEq,Eq)]
pub enum Record{
    String{data_offset:u32},
    Type{descriptor:u32},
    Prototype{shorty:u32,return_type:u32,parameters_offset:u32},
    Field{class:u16,field_type:u16,name:u32},
    Method{class:u16,prototype:u16,name:u32},
    Class{class:u32,flags:u32,superclass:Option<u32>,interfaces_offset:u32,
        source_file:Option<u32>,annotations_offset:u32,class_data_offset:u32,static_values_offset:u32},
}
#[derive(Debug,PartialEq,Eq)]
pub struct Page{pub start:u32,pub total:u32,pub records:Vec<Record>,pub next:Option<u32>}
pub struct Inspector<R:Read+Seek>{session:ReadSession<R>,dex:Dex}
fn bad(s:&'static str)->io::Error{io::Error::new(io::ErrorKind::InvalidData,s)}
fn invalid(s:&'static str)->io::Error{io::Error::new(io::ErrorKind::InvalidInput,s)}
fn u16_at(b:&[u8],i:usize)->u16{u16::from_le_bytes(b[i..i+2].try_into().unwrap())}
fn u32_at(b:&[u8],i:usize)->u32{u32::from_le_bytes(b[i..i+4].try_into().unwrap())}
fn reference(i:u32,t:Table)->io::Result<u32>{if i<t.count{Ok(i)}else{Err(bad("identifier index outside table"))}}
fn optional(i:u32,t:Table)->io::Result<Option<u32>>{if i==u32::MAX{Ok(None)}else{reference(i,t).map(Some)}}
fn uleb(b:&[u8])->io::Result<(u32,usize)>{
    let mut value=0u32;
    for (i,&x) in b.iter().take(5).enumerate(){
        if i==4&&x>15{return Err(bad("ULEB128 overflow"));}
        value|=u32::from(x&127)<<(7*i);
        if x&128==0{return Ok((value,i+1));}
    }
    Err(bad("unterminated ULEB128"))
}
fn cont(b:&[u8],i:usize)->io::Result<u16>{
    match b.get(i){Some(&v) if v&0xc0==0x80=>Ok(u16::from(v&63)),_=>Err(bad("invalid modified UTF-8 continuation"))}
}
fn decode(b:&[u8],declared:u32)->io::Result<StringValue>{
    let mut out=Vec::with_capacity(declared as usize);let mut i=0;
    while let Some(&a)=b.get(i){
        if a==0{
            if out.len()!=declared as usize{return Err(bad("UTF-16 length mismatch"));}
            return Ok(StringValue::Units(out));
        }
        if out.len()==declared as usize{return Err(bad("UTF-16 length mismatch"));}
        let (v,n)=match a{
            1..=127=>(u16::from(a),1),
            0xc0..=0xdf=>{
                let v=(u16::from(a&31)<<6)|cont(b,i+1)?;
                if v!=0&&v<128{return Err(bad("overlong modified UTF-8"));}
                (v,2)
            },
            0xe0..=0xef=>{
                let v=(u16::from(a&15)<<12)|(cont(b,i+1)?<<6)|cont(b,i+2)?;
                if v<2048{return Err(bad("overlong modified UTF-8"));}
                (v,3)
            },
            _=>return Err(bad("invalid modified UTF-8 lead")),
        };
        out.push(v);i+=n;
    }
    Err(bad("missing modified UTF-8 terminator"))
}
impl<R:Read+Seek> Inspector<R>{
    pub fn open(mut session:ReadSession<R>)->io::Result<Self>{
        let dex=match dex_structure::inspect(&mut session)?{
            Verdict::Checked(d)=>d,Verdict::Malformed(_)=>return Err(bad("DEX structural subset rejected")),
            Verdict::Unsupported(_)=>return Err(io::Error::new(io::ErrorKind::Unsupported,"DEX structural subset unsupported")),
        };
        Ok(Self{session,dex})
    }
    pub fn dex(&self)->&Dex{&self.dex}
    pub fn remaining_budget(&self)->u64{self.session.remaining_budget()}
    fn table(&self,kind:Kind)->(Table,usize){
        match kind{Kind::String=>(self.dex.strings,4),Kind::Type=>(self.dex.types,4),
            Kind::Prototype=>(self.dex.prototypes,12),Kind::Field=>(self.dex.fields,8),
            Kind::Method=>(self.dex.methods,8),Kind::Class=>(self.dex.classes,32)}
    }
    fn region(&self,kind:u16,at:u32,alignment:u32)->io::Result<u64>{
        let i=self.dex.map.iter().position(|m|m.kind==kind).ok_or_else(||bad("missing mapped item kind"))?;
        let end=self.dex.map.get(i+1).map_or(self.dex.file_size,|m|m.offset);
        if at<self.dex.map[i].offset||at>=end||at%alignment!=0{return Err(bad("offset outside declared item region"));}
        Ok(u64::from(end))
    }
    fn optional_region(&self,kind:u16,at:u32,alignment:u32)->io::Result<u32>{
        if at!=0{self.region(kind,at,alignment)?;}Ok(at)
    }
    pub fn page(&mut self,kind:Kind,start:u32,limit:usize)->io::Result<Page>{
        self.session.cancellation.check()?;
        let (t,w)=self.table(kind);
        if start>t.count||limit==0||limit>MAX_PAGE{return Err(invalid("invalid identifier page"));}
        let n=(t.count-start).min(limit as u32);
        let mut records=Vec::with_capacity(n as usize);
        if n!=0{
            let offset=u64::from(t.offset)+u64::from(start)*w as u64;
            let raw=self.session.read_window(offset,n as usize*w)?.bytes;
            for b in raw.chunks_exact(w){
                self.session.cancellation.check()?;
                let d=&self.dex;
                let rec=match kind{
                    Kind::String=>{let data_offset=u32_at(b,0);self.region(0x2002,data_offset,1)?;Record::String{data_offset}},
                    Kind::Type=>Record::Type{descriptor:reference(u32_at(b,0),d.strings)?},
                    Kind::Prototype=>Record::Prototype{shorty:reference(u32_at(b,0),d.strings)?,return_type:reference(u32_at(b,4),d.types)?,
                        parameters_offset:self.optional_region(0x1001,u32_at(b,8),4)?},
                    Kind::Field=>{let class=u16_at(b,0);let field_type=u16_at(b,2);
                        reference(u32::from(class),d.types)?;reference(u32::from(field_type),d.types)?;
                        Record::Field{class,field_type,name:reference(u32_at(b,4),d.strings)?}},
                    Kind::Method=>{let class=u16_at(b,0);let prototype=u16_at(b,2);
                        reference(u32::from(class),d.types)?;reference(u32::from(prototype),d.prototypes)?;
                        Record::Method{class,prototype,name:reference(u32_at(b,4),d.strings)?}},
                    Kind::Class=>Record::Class{class:reference(u32_at(b,0),d.types)?,flags:u32_at(b,4),
                        superclass:optional(u32_at(b,8),d.types)?,interfaces_offset:self.optional_region(0x1001,u32_at(b,12),4)?,
                        source_file:optional(u32_at(b,16),d.strings)?,annotations_offset:self.optional_region(0x2006,u32_at(b,20),4)?,
                        class_data_offset:self.optional_region(0x2000,u32_at(b,24),1)?,
                        static_values_offset:self.optional_region(0x2005,u32_at(b,28),1)?},
                };
                records.push(rec);
            }
        }
        self.session.cancellation.check()?;
        let end=start+n;
        Ok(Page{start,total:t.count,records,next:(end<t.count).then_some(end)})
    }
    pub fn string(&mut self,index:u32)->io::Result<StringValue>{
        if index>=self.dex.strings.count{return Err(invalid("string index"));}
        let p=self.page(Kind::String,index,1)?;
        let Record::String{data_offset}=p.records[0] else{unreachable!()};
        let end=self.region(0x2002,data_offset,1)?;
        let at=u64::from(data_offset);
        let prefix=self.session.read_window(at,(end-at).min(5) as usize)?.bytes;
        let (declared,n)=uleb(&prefix)?;
        if declared>MAX_STRING_UNITS as u32{
            self.session.cancellation.check()?;
            return Ok(StringValue::TooLong{declared_units:declared});
        }
        let body=at+n as u64;
        let size=(end-body).min(u64::from(declared)*3+1) as usize;
        let bytes=self.session.read_window(body,size)?.bytes;
        let value=decode(&bytes,declared)?;
        self.session.cancellation.check()?;
        Ok(value)
    }
    pub fn descriptor(&mut self,index:u32)->io::Result<StringValue>{
        if index>=self.dex.types.count{return Err(invalid("type index"));}
        let p=self.page(Kind::Type,index,1)?;
        let Record::Type{descriptor}=p.records[0] else{unreachable!()};
        self.string(descriptor)
    }
    /// Caller-selected candidate type_list offset from a mapped region.
    /// Zero is the absent-list sentinel. No proof of variable-item boundary.
    pub fn type_list(&mut self,offset:u32)->io::Result<Vec<u16>>{
        self.session.cancellation.check()?;
        if offset==0{return Ok(vec![]);}
        let end=self.region(0x1001,offset,4)?;let at=u64::from(offset);
        if at+4>end{return Err(bad("truncated type list header"));}
        let head=self.session.read_window(at,4)?.bytes;
        let count=u32_at(&head,0);
        if count as u64>MAX_TYPE_LIST as u64{return Err(io::Error::new(io::ErrorKind::Unsupported,"type list limit"));}
        if at+4+u64::from(count)*2>end{return Err(bad("type list extent"));}
        let bytes=self.session.read_window(at+4,count as usize*2)?.bytes;
        let mut result=Vec::with_capacity(count as usize);
        for b in bytes.chunks_exact(2){let i=u16_at(b,0);reference(u32::from(i),self.dex.types)?;result.push(i);}
        self.session.cancellation.check()?;
        Ok(result)
    }
}
