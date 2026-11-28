//! Fixed-length virtual replacement over an owned, authorized read session.
//! Stable source required. No path opening, file writing, export, insertion,
//! deletion, persistent history or general concurrent-source tamper defense.
use crate::{ReadSession,Window};
use std::{collections::BTreeMap,io::{self,Read,Seek}};

pub const MAX_EDIT_BYTES:usize=4096;
pub const MAX_PATCHED_BYTES:usize=65536;
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
struct Patch{original:u8,replacement:u8}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub struct State{pub revision:u64,pub patched_bytes:usize}
pub struct Overlay<R:Read+Seek>{
    source:ReadSession<R>,patches:BTreeMap<u64,Patch>,capacity:usize,revision:u64,
}
fn invalid(s:&'static str)->io::Error{io::Error::new(io::ErrorKind::InvalidInput,s)}
fn conflict(s:&'static str)->io::Error{io::Error::new(io::ErrorKind::InvalidData,s)}
impl<R:Read+Seek> Overlay<R>{
    pub fn new(source:ReadSession<R>,capacity:usize)->io::Result<Self>{
        if capacity==0||capacity>MAX_PATCHED_BYTES{return Err(invalid("invalid overlay capacity"));}
        Ok(Self{source,patches:BTreeMap::new(),capacity,revision:0})
    }
    pub fn len(&self)->u64{self.source.len()}
    pub fn is_empty(&self)->bool{self.source.is_empty()}
    pub fn state(&self)->State{State{revision:self.revision,patched_bytes:self.patches.len()}}
    pub fn remaining_budget(&self)->u64{self.source.remaining_budget()}
    /// Read the virtual bytes. Original bytes are read and charged even
    /// where patched. Drift at an observed patched position rejects output.
    pub fn read_window(&mut self,offset:u64,size:usize)->io::Result<Window>{
        let mut w=self.source.read_window(offset,size)?;
        let end=offset+w.bytes.len() as u64;
        for (&at,p) in self.patches.range(offset..end){
            let i=(at-offset) as usize;
            if w.bytes[i]!=p.original{return Err(conflict("observed patched source byte changed"));}
            w.bytes[i]=p.replacement;
        }
        self.source.cancellation.check()?;
        Ok(w)
    }
    /// Compare-and-replace the current virtual window. All preconditions
    /// are checked before mutation. Restoring a byte to its original value
    /// removes its patch. A stale revision is rejected before I/O.
    /// An admitted failed read remains charged. No-op retains revision.
    pub fn replace(&mut self,revision:u64,offset:u64,expected:&[u8],replacement:&[u8])->io::Result<State>{
        self.source.cancellation.check()?;
        if revision!=self.revision{return Err(conflict("stale overlay revision"));}
        if expected.is_empty()||expected.len()>MAX_EDIT_BYTES||expected.len()!=replacement.len(){
            return Err(invalid("invalid replacement length"));
        }
        let end=offset.checked_add(expected.len() as u64).ok_or_else(||invalid("replacement range overflow"))?;
        if end>self.len(){return Err(invalid("replacement outside source"));}
        let original=self.source.read_window(offset,expected.len())?;
        let mut count=self.patches.len();
        let mut changes=Vec::with_capacity(expected.len());
        for (i,(&base,(&before,&after))) in original.bytes.iter().zip(expected.iter().zip(replacement)).enumerate(){
            let at=offset+i as u64;
            let existing=self.patches.get(&at).copied();
            if existing.is_some_and(|p|p.original!=base){return Err(conflict("observed patched source byte changed"));}
            let current=existing.map_or(base,|p|p.replacement);
            if current!=before{return Err(conflict("virtual precondition mismatch"));}
            if current==after{continue;}
            let next=(after!=base).then_some(Patch{original:base,replacement:after});
            match (existing.is_some(),next.is_some()){
                (false,true)=>count+=1,
                (true,false)=>count-=1,
                _=>{}
            }
            changes.push((at,next));
        }
        if count>self.capacity{return Err(invalid("overlay capacity exceeded"));}
        self.source.cancellation.check()?;
        if changes.is_empty(){return Ok(self.state());}
        let revision=self.revision.checked_add(1).ok_or_else(||invalid("revision exhausted"))?;
        // No fallible I/O after admission. Allocator/process failure is not
        // recoverable here; atomicity refers to ordinary Result errors.
        for (at,next) in changes{
            if let Some(p)=next{self.patches.insert(at,p);}
            else{self.patches.remove(&at);}
        }
        self.revision=revision;
        Ok(self.state())
    }
    /// Explicitly discard all virtual edits. No reads or source writes.
    pub fn discard(&mut self,revision:u64)->io::Result<State>{
        self.source.cancellation.check()?;
        if revision!=self.revision{return Err(conflict("stale overlay revision"));}
        if !self.patches.is_empty(){
            let next=self.revision.checked_add(1).ok_or_else(||invalid("revision exhausted"))?;
            self.patches.clear();self.revision=next;
        }
        Ok(self.state())
    }
}
