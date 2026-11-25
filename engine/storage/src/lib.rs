#![forbid(unsafe_code)]
//! Candidate local SQLite adapter. Trusted destination only, no source opening.
//! Initial slice supports byte-observation reports (JSON v1) only.
use negrodroid_core::{capabilities::describe,inventory::SourceKey,orchestration::Report,
    parallel::Status,reporting::{validate_report,ExportError,Paths}};
use rusqlite::{params,Connection,OpenFlags,OptionalExtension};
use std::{fs::OpenOptions,io,path::Path};

const SCHEMA:&str=include_str!("../../core/schema/index_v1.sql");
const MAX_RUNS:i64=1024;
#[derive(Debug)]
pub enum Error { Sql(rusqlite::Error), Io(io::Error), InvalidDestination, InvalidReport(ExportError),
    UnsupportedHeaders, RunLimit, Accounting }
impl From<rusqlite::Error> for Error{fn from(e:rusqlite::Error)->Self{Self::Sql(e)}}
impl From<io::Error> for Error{fn from(e:io::Error)->Self{Self::Io(e)}}
#[derive(Debug,PartialEq,Eq)]
pub struct Summary {pub entries:i64,pub observed:i64,pub failed:i64,pub cancelled:i64,pub not_started:i64,pub state:String}
pub struct Store {conn:Connection}
impl Store {
    fn initialize(conn:Connection)->Result<Self,Error>{
        conn.execute_batch(SCHEMA)?;
        let version:i64=conn.query_row("PRAGMA user_version",[],|r|r.get(0))?;
        let foreign:i64=conn.query_row("PRAGMA foreign_keys",[],|r|r.get(0))?;
        if version!=1||foreign!=1{return Err(Error::Accounting);}
        Ok(Self{conn})
    }
    pub fn memory()->Result<Self,Error>{Self::initialize(Connection::open_in_memory()?)}
    /// Create a NEW database in a private, caller-authorized stable directory.
    /// Must not be in the analyzed source tree. Existing paths are refused,
    /// including symlinks. Path replacement races are not defended against.
    /// On initialization error a newly created file may remain; never remove
    /// or overwrite another file automatically.
    pub fn create_new(path:&Path)->Result<Self,Error>{
        if !path.is_absolute(){return Err(Error::InvalidDestination);}
        let file=OpenOptions::new().write(true).create_new(true).open(path)?;
        drop(file);
        let conn=Connection::open_with_flags(path,OpenFlags::SQLITE_OPEN_READ_WRITE|OpenFlags::SQLITE_OPEN_NO_MUTEX)?;
        Self::initialize(conn)
    }
    /// Insert and seal in one transaction. Reject header-mode reports instead
    /// of silently discarding structural evidence; schema v1 lacks those fields.
    /// Does not persist error-kind, reserved budget or per-run batching metadata.
    pub fn save_analysis(&mut self,r:&Report,paths:Paths)->Result<i64,Error>{
        if r.headers_enabled(){return Err(Error::UnsupportedHeaders);}
        validate_report(r).map_err(Error::InvalidReport)?;
        let tx=self.conn.transaction()?;
        let runs:i64=tx.query_row("SELECT count(*) FROM analysis_run",[],|r|r.get(0))?;
        if runs>=MAX_RUNS{return Err(Error::RunLimit);}
        let policy=match paths {Paths::Omit=>"omitted",Paths::IncludeLogical=>"logical_opt_in"};
        tx.execute("INSERT INTO analysis_run(kind,path_policy,planned,omissions) VALUES('analysis',?1,?2,0)",
            params![policy,r.summary.planned as i64])?;
        let id=tx.last_insert_rowid();
        {
            let mut insert=tx.prepare("INSERT INTO source_entry(run_id,ordinal,logical_key,declared_length,format_hint,status,sha256,charged_bytes) VALUES(?1,?2,?3,?4,?5,?6,?7,?8)")?;
            for (i,(key,e)) in r.inventory.iter().enumerate(){
                let d=r.diagnostics.get(key).ok_or(Error::Accounting)?;
                let length=e.declared_length.ok_or(Error::Accounting)?.to_be_bytes();
                let charged=d.charged_bytes.to_be_bytes();
                let digest=e.observation.map(|o|*o.sha256.bytes());
                let encoded=match paths{Paths::Omit=>None,Paths::IncludeLogical=>Some(encode_key(key))};
                let status=match d.status {Status::Observed=>"observed",Status::Failed(_)=>"failed",
                    Status::Cancelled=>"cancelled",Status::NotStarted=>"not_started"};
                insert.execute(params![id,(i+1) as i64,encoded,length.as_slice(),describe(e.format_hint).id,
                    status,digest.as_ref().map(|v|v.as_slice()),charged.as_slice()])?;
            }
        }
        if tx.execute("UPDATE analysis_run SET sealed=1 WHERE id=?1",[id])?!=1{return Err(Error::Accounting);}
        tx.commit()?;
        Ok(id)
    }
    pub fn summary(&self,id:i64)->Result<Option<Summary>,Error>{
        Ok(self.conn.query_row("SELECT entries,observed,failed,cancelled,not_started,state FROM sealed_run_summary WHERE id=?1",[id],|r|
            Ok(Summary{entries:r.get(0)?,observed:r.get(1)?,failed:r.get(2)?,cancelled:r.get(3)?,not_started:r.get(4)?,state:r.get(5)?})).optional()?)
    }
}
// Canonical v1 key: version byte, big-endian root, length-prefixed UTF-8 path,
// member count, then length-prefixed members. No delimiter collisions.
fn encode_key(key:&SourceKey)->Vec<u8>{
    fn append(b:&mut Vec<u8>,s:&str){b.extend_from_slice(&(s.len() as u32).to_be_bytes());b.extend_from_slice(s.as_bytes());}
    let mut b=vec![1];b.extend_from_slice(&key.root().to_be_bytes());
    append(&mut b,key.relative_path());
    b.push(key.members().len() as u8);
    for m in key.members(){append(&mut b,m);}
    b
}

#[cfg(test)]
mod tests{
    use super::*;
    use negrodroid_core::{Cancellation,orchestration::{run,run_with_headers,Config},parallel::Task};
    use std::{io::Cursor,fs,sync::atomic::{AtomicUsize,Ordering}};
    fn task(p:&str,data:&[u8],length:u64)->Task<Cursor<Vec<u8>>>{
        Task{key:SourceKey::physical(7,p).unwrap(),reader:Cursor::new(data.to_vec()),length}
    }
    fn cfg()->Config{Config{workers:2,batch_size:2,byte_budget:u64::MAX}}
    fn sample()->Report{run(vec![task("private/x",b"abc",3)],cfg(),Cancellation::default()).unwrap()}
    #[test]
    fn observed_row_is_sealed_and_paths_omitted(){
        let mut s=Store::memory().unwrap();let id=s.save_analysis(&sample(),Paths::Omit).unwrap();
        assert_eq!(s.summary(id).unwrap().unwrap().state,"complete_byte_observation");
        let row:(Option<Vec<u8>>,Vec<u8>,Vec<u8>,Vec<u8>)=s.conn.query_row(
            "SELECT logical_key,declared_length,sha256,charged_bytes FROM source_entry",[],|r|Ok((r.get(0)?,r.get(1)?,r.get(2)?,r.get(3)?))).unwrap();
        assert_eq!(row.0,None);assert_eq!(row.1,3u64.to_be_bytes());
        assert_eq!(row.2,sample().inventory.iter().next().unwrap().1.observation.unwrap().sha256.bytes().to_vec());
        assert_eq!(row.3,6u64.to_be_bytes());
    }
    #[test]
    fn logical_key_opt_in_and_no_delimiter_collision(){
        let mut s=Store::memory().unwrap();let r=sample();s.save_analysis(&r,Paths::IncludeLogical).unwrap();
        let b:Vec<u8>=s.conn.query_row("SELECT logical_key FROM source_entry",[],|r|r.get(0)).unwrap();
        assert_eq!(b,encode_key(r.inventory.iter().next().unwrap().0));
        let a=SourceKey::physical(7,"a/b").unwrap().member("c").unwrap();
        let b=SourceKey::physical(7,"a").unwrap().member("b/c").unwrap();
        assert_ne!(encode_key(&a),encode_key(&b));
    }
    #[test]
    fn mixed_status_and_cancelled_large_u64(){
        let mut s=Store::memory().unwrap();
        let r=run(vec![task("a",b"x",1),task("b",b"",1)],cfg(),Cancellation::default()).unwrap();
        let id=s.save_analysis(&r,Paths::Omit).unwrap();
        let summary=s.summary(id).unwrap().unwrap();assert_eq!((summary.observed,summary.failed),(1,1));
        assert_eq!(summary.state,"with_failures");
        let c=Cancellation::default();c.cancel();let n=9_007_199_254_740_993;
        let r=run(vec![task("c",b"",n)],cfg(),c).unwrap();
        let id=s.save_analysis(&r,Paths::Omit).unwrap();
        let row:(Vec<u8>,Option<Vec<u8>>)=s.conn.query_row("SELECT declared_length,sha256 FROM source_entry WHERE run_id=?1",[id],|r|Ok((r.get(0)?,r.get(1)?))).unwrap();
        assert_eq!(row.0,n.to_be_bytes());assert_eq!(row.1,None);
        assert_eq!(s.summary(id).unwrap().unwrap().state,"cancelled");
    }
    #[test]
    fn rejects_inconsistent_and_header_reports(){
        let mut s=Store::memory().unwrap();let mut r=sample();r.summary.observed=0;
        assert!(matches!(s.save_analysis(&r,Paths::Omit),Err(Error::InvalidReport(_))));
        let r=run_with_headers(vec![task("x",b"x",1)],cfg(),Cancellation::default()).unwrap();
        assert!(matches!(s.save_analysis(&r,Paths::Omit),Err(Error::UnsupportedHeaders)));
        let n:i64=s.conn.query_row("SELECT count(*) FROM analysis_run",[],|r|r.get(0)).unwrap();assert_eq!(n,0);
    }
    #[test]
    fn injected_sql_error_rolls_back_entire_transaction(){
        let mut s=Store::memory().unwrap();
        s.conn.execute_batch("CREATE TRIGGER synthetic_fail BEFORE INSERT ON source_entry WHEN NEW.ordinal=2 BEGIN SELECT RAISE(ABORT,'synthetic'); END;").unwrap();
        let r=run(vec![task("a",b"a",1),task("b",b"b",1)],cfg(),Cancellation::default()).unwrap();
        assert!(matches!(s.save_analysis(&r,Paths::Omit),Err(Error::Sql(_))));
        for table in ["analysis_run","source_entry"]{
            let n:i64=s.conn.query_row(&format!("SELECT count(*) FROM {table}"),[],|r|r.get(0)).unwrap();assert_eq!(n,0);
        }
    }
    #[test]
    fn fresh_disk_database_reopens_without_overwriting_existing_file(){
        static NEXT:AtomicUsize=AtomicUsize::new(0);
        let dir=loop{
            let dir=std::env::temp_dir().join(format!("negrodroid-store-{}-{}",std::process::id(),NEXT.fetch_add(1,Ordering::Relaxed)));
            match fs::create_dir(&dir){Ok(())=>break dir,Err(e) if e.kind()==io::ErrorKind::AlreadyExists=>continue,Err(e)=>panic!("{e}")}
        };
        let path=dir.join("index.sqlite");
        let mut s=Store::create_new(&path).unwrap();let id=s.save_analysis(&sample(),Paths::Omit).unwrap();drop(s);
        assert!(matches!(Store::create_new(&path),Err(Error::Io(e)) if e.kind()==io::ErrorKind::AlreadyExists));
        let c=Connection::open_with_flags(&path,OpenFlags::SQLITE_OPEN_READ_ONLY).unwrap();
        let state:String=c.query_row("SELECT state FROM sealed_run_summary WHERE id=?1",[id],|r|r.get(0)).unwrap();
        assert_eq!(state,"complete_byte_observation");drop(c);
        fs::remove_dir_all(dir).unwrap();
    }
}
