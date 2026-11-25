//! Metadata discovery for a caller-authorized, stable directory tree.
//! This portable path-based walk is not a security boundary against concurrent
//! path replacement, untrusted ancestors, mount points or filesystem aliases.
use crate::{Cancellation,format::FormatHint,inventory::{Coverage,Entry,Inventory,SourceKey,IndexError,MAX_PATH_BYTES,MAX_INDEX_PATH_BYTES,MAX_INDEX_ENTRIES}};
use std::{fs,io,path::Path};

pub const MAX_DEPTH:usize=32;
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub struct Limits {pub max_entries:usize,pub max_depth:usize,pub max_path_bytes:usize}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Error {InvalidLimits,InvalidRoot,EntryLimit,PathBudget,Cancelled,Io(io::ErrorKind),Index(IndexError)}
#[derive(Debug,Default,Clone,Copy,PartialEq,Eq)]
pub struct Counts {pub visited:usize,pub files:usize,pub directories:usize,pub links:usize,pub special:usize,pub invalid_names:usize,pub depth_skipped:usize}
impl Counts {
    /// No deliberately omitted entries/subtrees; not a snapshot or guarantee
    /// that a changing tree was fully enumerated.
    pub fn no_skips(&self)->bool {self.links+self.special+self.invalid_names+self.depth_skipped==0}
}
pub struct Discovery {pub inventory:Inventory,pub counts:Counts}
fn io_error(e:io::Error)->Error{Error::Io(e.kind())}
fn check(c:&Cancellation)->Result<(),Error>{if c.is_cancelled(){Err(Error::Cancelled)}else{Ok(())}}
fn link_like(m:&fs::Metadata)->bool{
    if m.file_type().is_symlink(){return true;}
    #[cfg(windows)]
    {use std::os::windows::fs::MetadataExt;if m.file_attributes()&0x400!=0{return true;}}
    false
}
/// Only absolute, caller-authorized roots with trusted stable ancestors.
/// No content opened, no following observed symlinks/reparse points, no writes.
/// Refuses limit/I/O/cancellation failures atomically; skip counts are explicit.
/// Does not exclude mount crossings or hard-link aliases. Blocking OS calls
/// cannot be cancelled immediately; a race-resistant handle walker is future work.
pub fn discover(root:&Path,root_id:u64,limits:Limits,cancel:&Cancellation)->Result<Discovery,Error>{
    if limits.max_entries==0 || limits.max_entries>MAX_INDEX_ENTRIES ||
        limits.max_depth>MAX_DEPTH || limits.max_path_bytes==0 ||
        limits.max_path_bytes>MAX_INDEX_PATH_BYTES {return Err(Error::InvalidLimits);}
    check(cancel)?;
    if !root.is_absolute(){return Err(Error::InvalidRoot);}
    let m=fs::symlink_metadata(root).map_err(io_error)?;
    if link_like(&m)||!m.is_dir(){return Err(Error::InvalidRoot);}
    let mut out=Discovery{inventory:Inventory::new(limits.max_entries,limits.max_path_bytes),counts:Counts::default()};
    let mut path_bytes=0;
    walk(root,"",0,root_id,limits,cancel,&mut out,&mut path_bytes)?;
    check(cancel)?;
    Ok(out)
}
fn walk(dir:&Path,prefix:&str,depth:usize,root_id:u64,limits:Limits,cancel:&Cancellation,out:&mut Discovery,path_bytes:&mut usize)->Result<(),Error>{
    check(cancel)?;
    let meta=fs::symlink_metadata(dir).map_err(io_error)?;
    if link_like(&meta)||!meta.is_dir(){return Err(Error::InvalidRoot);}
    for result in fs::read_dir(dir).map_err(io_error)?{
        check(cancel)?;
        let item=result.map_err(io_error)?;
        if out.counts.visited>=limits.max_entries{return Err(Error::EntryLimit);}
        out.counts.visited+=1;
        let name=item.file_name();
        let Some(key)=logical_key(root_id,prefix,&name)? else {out.counts.invalid_names+=1;continue;};
        let logical=key.relative_path().to_owned();
        *path_bytes=path_bytes.checked_add(logical.len()).ok_or(Error::PathBudget)?;
        if *path_bytes>limits.max_path_bytes{return Err(Error::PathBudget);}
        let path=item.path();
        let m=fs::symlink_metadata(&path).map_err(io_error)?;
        if link_like(&m){out.counts.links+=1;}
        else if m.is_dir(){
            out.counts.directories+=1;
            if depth>=limits.max_depth{out.counts.depth_skipped+=1;}
            else{walk(&path,&logical,depth+1,root_id,limits,cancel,out,path_bytes)?;}
        }else if m.is_file(){
            out.inventory.insert(key,Entry{declared_length:Some(m.len()),format_hint:FormatHint::Unknown,
                coverage:Coverage::Unexamined,observation:None}).map_err(Error::Index)?;
            out.counts.files+=1;
        }else{out.counts.special+=1;}
    }
    check(cancel)
}

fn logical_key(root_id:u64,prefix:&str,name:&std::ffi::OsStr)->Result<Option<SourceKey>,Error>{
    let Some(name)=name.to_str() else{return Ok(None);};
    if name.len()>MAX_PATH_BYTES || prefix.len()+name.len()+usize::from(!prefix.is_empty())>MAX_PATH_BYTES{
        return Ok(None);
    }
    let logical=if prefix.is_empty(){name.to_owned()}else{format!("{prefix}/{name}")};
    match SourceKey::physical(root_id,&logical){
        Ok(k)=>Ok(Some(k)),Err(IndexError::InvalidPath)=>Ok(None),Err(e)=>Err(Error::Index(e))
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    use std::ffi::OsStr;
    #[test]
    fn logical_policy_rejects_unrepresentable_paths(){
        for name in ["bad:name","bad\\name","..",""]{
            // Empty name with a nonempty prefix also yields an invalid trailing slash.
            assert!(logical_key(1,"dir",OsStr::new(name)).unwrap().is_none());
        }
        let overlong="x".repeat(MAX_PATH_BYTES);
        assert!(logical_key(1,"dir",OsStr::new(&overlong)).unwrap().is_none());
    }
    #[cfg(unix)]
    #[test]
    fn raw_invalid_utf8_is_rejected_without_filesystem_assumptions(){
        use std::os::unix::ffi::OsStrExt;
        assert!(logical_key(1,"",OsStr::from_bytes(b"bad\xff")).unwrap().is_none());
    }
    #[cfg(windows)]
    #[test]
    fn unpaired_utf16_surrogate_is_rejected(){
        use std::os::windows::ffi::OsStringExt;
        let name=std::ffi::OsString::from_wide(&[0xd800]);
        assert!(logical_key(1,"",&name).unwrap().is_none());
    }
}
