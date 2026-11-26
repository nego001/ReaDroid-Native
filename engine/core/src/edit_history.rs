//! In-memory undo/redo journal over fixed-length virtual replacements.
//! No source writes, export, persistent recovery or cross-session replay.
use crate::{ReadSession,Window,virtual_overlay::{Overlay,MAX_EDIT_BYTES}};
use std::io::{self,Read,Seek};

pub const MAX_HISTORY_ENTRIES:usize=128;
pub const MAX_HISTORY_PAYLOAD:usize=1024*1024;
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub struct Limits{pub entries:usize,pub payload_bytes:usize}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub struct State{
    pub revision:u64,pub patched_bytes:usize,
    pub undo_count:usize,pub redo_count:usize,pub history_payload:usize,
}
struct Edit{offset:u64,before:Vec<u8>,after:Vec<u8>}
impl Edit{fn payload(&self)->usize{self.before.len()+self.after.len()}}
pub struct History<R:Read+Seek>{
    overlay:Overlay<R>,entries:Vec<Edit>,cursor:usize,limits:Limits,
}
fn invalid(s:&'static str)->io::Error{io::Error::new(io::ErrorKind::InvalidInput,s)}
impl<R:Read+Seek> History<R>{
    pub fn new(source:ReadSession<R>,patch_capacity:usize,limits:Limits)->io::Result<Self>{
        if limits.entries==0||limits.entries>MAX_HISTORY_ENTRIES||
            limits.payload_bytes<2||limits.payload_bytes>MAX_HISTORY_PAYLOAD{
            return Err(invalid("invalid history limits"));
        }
        Ok(Self{overlay:Overlay::new(source,patch_capacity)?,entries:Vec::with_capacity(limits.entries),cursor:0,limits})
    }
    pub fn state(&self)->State{
        let s=self.overlay.state();
        State{revision:s.revision,patched_bytes:s.patched_bytes,undo_count:self.cursor,
            redo_count:self.entries.len()-self.cursor,history_payload:self.entries.iter().map(Edit::payload).sum()}
    }
    pub fn remaining_budget(&self)->u64{self.overlay.remaining_budget()}
    pub fn read_window(&mut self,offset:u64,size:usize)->io::Result<Window>{self.overlay.read_window(offset,size)}
    fn require_revision(&self,revision:u64)->io::Result<()>{
        if revision!=self.overlay.state().revision{
            return Err(io::Error::new(io::ErrorKind::InvalidData,"stale history revision"));
        }
        Ok(())
    }
    /// One replacement is one transaction. Redo is discarded only after a
    /// successful non-noop edit. No silent eviction; full history rejects a
    /// new edit until undo frees a prefix slot. Payload counts both versions.
    /// Limits are logical retained bytes, not an allocator/RAM guarantee.
    pub fn replace(&mut self,revision:u64,offset:u64,expected:&[u8],replacement:&[u8])->io::Result<State>{
        self.require_revision(revision)?;
        if expected.is_empty()||expected.len()>MAX_EDIT_BYTES||expected.len()!=replacement.len(){
            return Err(invalid("invalid history edit length"));
        }
        if expected==replacement{
            self.overlay.replace(revision,offset,expected,replacement)?;
            return Ok(self.state());
        }
        let retained:usize=self.entries[..self.cursor].iter().map(Edit::payload).sum();
        let needed=expected.len()+replacement.len();
        if self.cursor>=self.limits.entries||retained+needed>self.limits.payload_bytes{
            return Err(invalid("history capacity exceeded"));
        }
        let edit=Edit{offset,before:expected.to_vec(),after:replacement.to_vec()};
        self.overlay.replace(revision,offset,expected,replacement)?;
        self.entries.truncate(self.cursor);
        self.entries.push(edit);
        self.cursor+=1;
        Ok(self.state())
    }
    /// Undo/redo uses the same source checks and read budget as a new edit.
    /// Failure leaves journal cursor and overlay unchanged (I/O may be charged).
    pub fn undo(&mut self,revision:u64)->io::Result<State>{
        self.require_revision(revision)?;
        if self.cursor==0{return Err(invalid("nothing to undo"));}
        let e=&self.entries[self.cursor-1];
        self.overlay.replace(revision,e.offset,&e.after,&e.before)?;
        self.cursor-=1;
        Ok(self.state())
    }
    pub fn redo(&mut self,revision:u64)->io::Result<State>{
        self.require_revision(revision)?;
        let e=self.entries.get(self.cursor).ok_or_else(||invalid("nothing to redo"))?;
        self.overlay.replace(revision,e.offset,&e.before,&e.after)?;
        self.cursor+=1;
        Ok(self.state())
    }
}
