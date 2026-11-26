//! Read-only, caller-authorized binary navigation. No file paths, cache or
//! writes. Page coordinates are source-relative u64; page size is fixed per
//! navigator. The source must remain stable for the navigator lifetime.
use crate::{ReadSession,hex::{self,Preview,MAX_HEX_BYTES}};
use std::io::{self,Read,Seek};

#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Error{InvalidPageSize,OutsideSource,EmptySource}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub struct Layout{length:u64,page_size:usize}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub struct Location{
    pub offset:u64,pub size:usize,pub index:u64,pub total_pages:u64,
    pub previous:Option<u64>,pub next:Option<u64>,
}
impl Layout{
    pub fn new(length:u64,page_size:usize)->Result<Self,Error>{
        if page_size==0||page_size>MAX_HEX_BYTES{return Err(Error::InvalidPageSize);}
        Ok(Self{length,page_size})
    }
    pub fn length(&self)->u64{self.length}
    pub fn page_size(&self)->usize{self.page_size}
    pub fn total_pages(&self)->u64{
        let p=self.page_size as u64;
        self.length/p+u64::from(self.length%p!=0)
    }
    /// Empty sources have a single display sentinel at offset zero, but
    /// total_pages is zero. For nonempty sources EOF is not a byte address.
    pub fn containing(&self,address:u64)->Result<Location,Error>{
        if self.length==0{
            if address!=0{return Err(Error::OutsideSource);}
            return Ok(Location{offset:0,size:0,index:0,total_pages:0,previous:None,next:None});
        }
        if address>=self.length{return Err(Error::OutsideSource);}
        self.page(address/self.page_size as u64)
    }
    pub fn page(&self,index:u64)->Result<Location,Error>{
        if self.length==0{return Err(Error::EmptySource);}
        let count=self.total_pages();
        if index>=count{return Err(Error::OutsideSource);}
        let p=self.page_size as u64;
        let offset=index*p; // bounded by length - 1
        let size=(self.length-offset).min(p) as usize;
        Ok(Location{offset,size,index,total_pages:count,
            previous:if index>0{Some(index-1)}else{None},
            next:if index<count-1{Some(index+1)}else{None}})
    }
}
#[derive(Debug,PartialEq,Eq)]
pub struct Page{pub location:Location,pub preview:Preview}
pub struct Navigator<R:Read+Seek>{session:ReadSession<R>,layout:Layout,current:Option<u64>}
impl<R:Read+Seek> Navigator<R>{
    pub fn new(session:ReadSession<R>,page_size:usize)->Result<Self,Error>{
        let layout=Layout::new(session.len(),page_size)?;
        Ok(Self{session,layout,current:None})
    }
    pub fn layout(&self)->Layout{self.layout}
    /// Last successfully read page, never advanced on failure.
    pub fn current(&self)->Option<u64>{self.current}
    pub fn remaining_budget(&self)->u64{self.session.remaining_budget()}
    pub fn jump(&mut self,address:u64)->io::Result<Page>{
        let loc=self.layout.containing(address).map_err(invalid)?;
        self.read(loc)
    }
    pub fn page(&mut self,index:u64)->io::Result<Page>{
        let loc=self.layout.page(index).map_err(invalid)?;
        self.read(loc)
    }
    pub fn next(&mut self)->io::Result<Option<Page>>{
        match self.current{
            None=>self.jump(0).map(Some),
            Some(i)=>match self.layout.page(i).ok().and_then(|p|p.next){
                Some(n)=>self.page(n).map(Some),None=>Ok(None)
            }
        }
    }
    pub fn previous(&mut self)->io::Result<Option<Page>>{
        match self.current{
            Some(i)=>match self.layout.page(i).ok().and_then(|p|p.previous){
                Some(n)=>self.page(n).map(Some),None=>Ok(None)
            },
            None=>Ok(None)
        }
    }
    fn read(&mut self,location:Location)->io::Result<Page>{
        let preview=hex::preview(&mut self.session,location.offset,self.layout.page_size)?;
        if preview.shown!=location.size{return Err(io::Error::new(io::ErrorKind::InvalidData,"page length mismatch"));}
        self.current=Some(location.index);
        Ok(Page{location,preview})
    }
}
fn invalid(_:Error)->io::Error{io::Error::new(io::ErrorKind::InvalidInput,"invalid binary page")}
