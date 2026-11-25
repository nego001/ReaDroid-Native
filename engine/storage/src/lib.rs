#![forbid(unsafe_code)]
//! Candidate local SQLite adapter. Trusted destination only, no source opening.
//! Fresh schema v4 stores analysis reports and metadata-only discoveries.
use negrodroid_core::{capabilities::describe,inventory::{SourceKey,Coverage,MAX_INDEX_ENTRIES},discovery::{Discovery,Counts},format::FormatHint,orchestration::Report,
    parallel::Status,reporting::{export_json,Options,ExportError,Paths,MAX_EXPORT_BYTES}};
use rusqlite::{params,Connection,OpenFlags,OptionalExtension};
use std::{fs::OpenOptions,io,path::Path};

const SCHEMA:&str=include_str!("../../core/schema/index_v4.sql");
const APPLICATION_ID:i64=1313098072;
const MAX_RUNS:i64=1024;
const MAX_DOCUMENT_PAYLOAD:i64=128*1024*1024;
const MAX_REOPEN_BYTES:u64=512*1024*1024;
const MAX_TOTAL_ENTRIES:i64=100_000;
const MAX_KEY_PAYLOAD:i64=128*1024*1024;
#[derive(Debug)]
pub enum Error { Sql(rusqlite::Error), Io(io::Error), InvalidDestination, InvalidReport(ExportError),
    RunLimit, PayloadLimit, Accounting, InvalidDatabase, UnsupportedVersion, PhysicalLimit, ActiveSidecar, InvalidDiscovery, EntryLimit, KeyLimit, InvalidPage, UnknownSession }
impl From<rusqlite::Error> for Error{fn from(e:rusqlite::Error)->Self{Self::Sql(e)}}
impl From<io::Error> for Error{fn from(e:io::Error)->Self{Self::Io(e)}}
#[derive(Debug,PartialEq,Eq)]
pub struct Summary {pub entries:i64,pub observed:i64,pub failed:i64,pub cancelled:i64,pub not_started:i64,pub state:String}
pub struct Store {conn:Connection}
pub const MAX_PAGE_SIZE:usize=128;
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum SessionKind { Analysis, Discovery }
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum SessionState { CompleteByteObservation, WithFailures, Cancelled, DiscoveryNoReportedOmissions, DiscoveryWithOmissions }
#[derive(Debug,Clone,PartialEq,Eq)]
pub struct SessionRow {
    pub id:i64,pub kind:SessionKind,pub state:SessionState,pub planned:u32,pub omissions:u32,pub stored_paths:Paths,
    pub observed:u32,pub failed:u32,pub cancelled:u32,pub not_started:u32,
}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum EntryStatus { Unexamined, Observed, Failed, Cancelled, NotStarted }
#[derive(Debug,Clone,PartialEq,Eq)]
pub struct EntryRow {
    pub ordinal:u32,pub declared_length:u64,pub format_hint:FormatHint,pub status:EntryStatus,
    pub sha256:Option<[u8;32]>,pub charged_bytes:Option<u64>,pub logical_key:Option<SourceKey>
}
#[derive(Debug,Clone,PartialEq,Eq)]
pub struct Page<T,C>{pub rows:Vec<T>,pub next:Option<C>}
impl Store {
    fn initialize(conn:Connection)->Result<Self,Error>{
        conn.execute_batch(SCHEMA)?;
        let version:i64=conn.query_row("PRAGMA user_version",[],|r|r.get(0))?;
        let foreign:i64=conn.query_row("PRAGMA foreign_keys",[],|r|r.get(0))?;
        let recursive:i64=conn.query_row("PRAGMA recursive_triggers",[],|r|r.get(0))?;
        let app:i64=conn.query_row("PRAGMA application_id",[],|r|r.get(0))?;
        if version!=4||foreign!=1||recursive!=1||app!=APPLICATION_ID{return Err(Error::Accounting);}
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
    /// Insert and seal query rows and full bounded report JSON in one transaction.
    /// The document retains error-kind, budgets and header metadata, not raw contents.
    pub fn save_analysis(&mut self,r:&Report,paths:Paths)->Result<i64,Error>{
        let document=export_json(r,Options{max_bytes:MAX_EXPORT_BYTES,paths}).map_err(Error::InvalidReport)?;
        let schema=if r.headers_enabled(){2}else{1};
        let tx=self.conn.transaction()?;
        admit(&tx,r.summary.planned,r.inventory.iter().map(|(k,_)|k),paths)?;
        let used:i64=tx.query_row("SELECT coalesce(sum(length(CAST(payload AS BLOB))),0) FROM report_document",[],|r|r.get(0))?;
        if used.checked_add(document.len() as i64).is_none_or(|n|n>MAX_DOCUMENT_PAYLOAD){return Err(Error::PayloadLimit);}
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
        tx.execute("INSERT INTO report_document(run_id,schema_version,payload) VALUES(?1,?2,?3)",params![id,schema,document])?;
        if tx.execute("UPDATE analysis_run SET sealed=1 WHERE id=?1",[id])?!=1{return Err(Error::Accounting);}
        tx.commit()?;
        Ok(id)
    }
    /// Persist only metadata and discovery counters; no hashing or file opening.
    pub fn save_discovery(&mut self,d:&Discovery,paths:Paths)->Result<i64,Error>{
        let c=d.counts;
        let omissions=validate_discovery(d)?;
        let tx=self.conn.transaction()?;
        admit(&tx,d.inventory.len(),d.inventory.iter().map(|(k,_)|k),paths)?;
        let policy=match paths{Paths::Omit=>"omitted",Paths::IncludeLogical=>"logical_opt_in"};
        tx.execute("INSERT INTO analysis_run(kind,path_policy,planned,omissions) VALUES('discovery',?1,?2,?3)",
            params![policy,c.files as i64,omissions as i64])?;
        let id=tx.last_insert_rowid();
        {
            let mut stmt=tx.prepare("INSERT INTO source_entry(run_id,ordinal,logical_key,declared_length,format_hint,status,sha256,charged_bytes)
                VALUES(?1,?2,?3,?4,'unknown','unexamined',NULL,NULL)")?;
            for (i,(k,e)) in d.inventory.iter().enumerate(){
                let length=e.declared_length.ok_or(Error::InvalidDiscovery)?.to_be_bytes();
                let key=match paths{Paths::Omit=>None,Paths::IncludeLogical=>Some(encode_key(k))};
                stmt.execute(params![id,(i+1) as i64,key,length.as_slice()])?;
            }
        }
        tx.execute("INSERT INTO discovery_detail VALUES(?1,?2,?3,?4,?5,?6,?7,?8)",
            params![id,c.visited as i64,c.files as i64,c.directories as i64,c.links as i64,c.special as i64,c.invalid_names as i64,c.depth_skipped as i64])?;
        if tx.execute("UPDATE analysis_run SET sealed=1 WHERE id=?1",[id])?!=1{return Err(Error::Accounting);}
        tx.commit()?;Ok(id)
    }
    pub fn discovery_counts(&self,id:i64)->Result<Option<Counts>,Error>{
        Ok(self.conn.query_row("SELECT d.visited,d.files,d.directories,d.links,d.special,d.invalid_names,d.depth_skipped
            FROM discovery_detail d JOIN analysis_run r ON r.id=d.run_id WHERE r.sealed=1 AND d.run_id=?1",[id],|r|
            Ok(Counts{visited:r.get::<_,u32>(0)? as usize,files:r.get::<_,u32>(1)? as usize,
                directories:r.get::<_,u32>(2)? as usize,links:r.get::<_,u32>(3)? as usize,
                special:r.get::<_,u32>(4)? as usize,invalid_names:r.get::<_,u32>(5)? as usize,
                depth_skipped:r.get::<_,u32>(6)? as usize})).optional()?)
    }
    /// Ascending keyset pagination of sealed sessions. A live Store may append
    /// new sessions between pages; a Reader requires a stable closed database.
    pub fn sessions(&self,after:Option<i64>,limit:usize)->Result<Page<SessionRow,i64>,Error>{
        let after=page_after(after,limit)?;
        let mut stmt=self.conn.prepare("SELECT id,kind,state,planned,omissions,path_policy,observed,failed,cancelled,not_started
            FROM sealed_run_summary WHERE id>?1 ORDER BY id LIMIT ?2")?;
        let mut rows=stmt.query(params![after,(limit+1) as i64])?;
        let mut result=Vec::new();
        while let Some(r)=rows.next()?{
            let kind=match r.get::<_,String>(1)?.as_str(){
                "analysis"=>SessionKind::Analysis,"discovery"=>SessionKind::Discovery,_=>return Err(Error::InvalidDatabase)};
            let state=match r.get::<_,String>(2)?.as_str(){
                "complete_byte_observation"=>SessionState::CompleteByteObservation,"with_failures"=>SessionState::WithFailures,
                "cancelled"=>SessionState::Cancelled,"discovery_no_reported_omissions"=>SessionState::DiscoveryNoReportedOmissions,
                "discovery_with_omissions"=>SessionState::DiscoveryWithOmissions,_=>return Err(Error::InvalidDatabase)};
            let stored_paths=match r.get::<_,String>(5)?.as_str(){
                "omitted"=>Paths::Omit,"logical_opt_in"=>Paths::IncludeLogical,_=>return Err(Error::InvalidDatabase)};
            result.push(SessionRow{id:r.get(0)?,kind,state,planned:r.get(3)?,omissions:r.get(4)?,stored_paths,
                observed:r.get(6)?,failed:r.get(7)?,cancelled:r.get(8)?,not_started:r.get(9)?});
        }
        let next=if result.len()>limit{result.pop();result.last().map(|r|r.id)}else{None};
        Ok(Page{rows:result,next})
    }
    /// Privacy is explicit: Omit avoids even selecting the stored logical key.
    /// A requested key cannot restore a path that was omitted when saved.
    /// Only sealed sessions are queryable. Ordinals are local to one session.
    pub fn entries(&self,id:i64,after:Option<u32>,limit:usize,paths:Paths)->Result<Page<EntryRow,u32>,Error>{
        let after=page_after(after.map(i64::from),limit)?;
        if id<=0||after>MAX_TOTAL_ENTRIES{return Err(Error::InvalidPage);}
        let present:bool=self.conn.query_row("SELECT EXISTS(SELECT 1 FROM analysis_run WHERE id=?1 AND sealed=1)",[id],|r|r.get(0))?;
        if !present{return Err(Error::UnknownSession);}
        let sql=match paths{
            Paths::Omit=>"SELECT ordinal,declared_length,format_hint,status,sha256,charged_bytes,NULL FROM source_entry WHERE run_id=?1 AND ordinal>?2 ORDER BY ordinal LIMIT ?3",
            Paths::IncludeLogical=>"SELECT ordinal,declared_length,format_hint,status,sha256,charged_bytes,logical_key FROM source_entry WHERE run_id=?1 AND ordinal>?2 ORDER BY ordinal LIMIT ?3"};
        let mut stmt=self.conn.prepare(sql)?;
        let mut rows=stmt.query(params![id,after,(limit+1) as i64])?;
        let mut result=Vec::new();
        while let Some(r)=rows.next()?{
            let status=match r.get::<_,String>(3)?.as_str(){
                "unexamined"=>EntryStatus::Unexamined,"observed"=>EntryStatus::Observed,"failed"=>EntryStatus::Failed,
                "cancelled"=>EntryStatus::Cancelled,"not_started"=>EntryStatus::NotStarted,_=>return Err(Error::InvalidDatabase)};
            let hint=r.get::<_,String>(2)?;
            let format_hint=negrodroid_core::capabilities::ALL_HINTS.iter().copied().find(|&h|describe(h).id==hint).ok_or(Error::InvalidDatabase)?;
            let length=u64::from_be_bytes(fixed_blob(r.get::<_,Vec<u8>>(1)?)?);
            let digest=r.get::<_,Option<Vec<u8>>>(4)?.map(fixed_blob::<32>).transpose()?;
            let charged=r.get::<_,Option<Vec<u8>>>(5)?.map(|b|fixed_blob::<8>(b).map(u64::from_be_bytes)).transpose()?;
            let key=r.get::<_,Option<Vec<u8>>>(6)?.map(|b|decode_key(&b)).transpose()?;
            result.push(EntryRow{ordinal:r.get(0)?,declared_length:length,format_hint,status,sha256:digest,charged_bytes:charged,logical_key:key});
        }
        let next=if result.len()>limit{result.pop();result.last().map(|r|r.ordinal)}else{None};
        Ok(Page{rows:result,next})
    }
    /// Exact exported report from a sealed run; no arbitrary SQL access.
    pub fn document(&self,id:i64)->Result<Option<String>,Error>{
        Ok(self.conn.query_row("SELECT d.payload FROM report_document d JOIN analysis_run r ON r.id=d.run_id WHERE r.sealed=1 AND d.run_id=?1",[id],|r|r.get(0)).optional()?)
    }
    pub fn summary(&self,id:i64)->Result<Option<Summary>,Error>{
        Ok(self.conn.query_row("SELECT entries,observed,failed,cancelled,not_started,state FROM sealed_run_summary WHERE id=?1",[id],|r|
            Ok(Summary{entries:r.get(0)?,observed:r.get(1)?,failed:r.get(2)?,cancelled:r.get(3)?,not_started:r.get(4)?,state:r.get(5)?})).optional()?)
    }
}
fn validate_discovery(d:&Discovery)->Result<usize,Error>{
    let c=d.counts;
    if [c.visited,c.files,c.directories,c.links,c.special,c.invalid_names,c.depth_skipped].iter().any(|&n|n>MAX_INDEX_ENTRIES)
        || c.files!=d.inventory.len() || c.depth_skipped>c.directories
        || c.visited!=c.files+c.directories+c.links+c.special+c.invalid_names{
        return Err(Error::InvalidDiscovery);
    }
    let mut root=None;
    for (k,e) in d.inventory.iter(){
        if !k.members().is_empty()||e.coverage!=Coverage::Unexamined||e.format_hint!=FormatHint::Unknown
            ||e.observation.is_some()||e.declared_length.is_none()||root.is_some_and(|r|r!=k.root()){
            return Err(Error::InvalidDiscovery);
        }
        root=Some(k.root());
    }
    Ok(c.links+c.special+c.invalid_names+c.depth_skipped)
}
fn admit<'a>(conn:&Connection,n:usize,mut keys:impl Iterator<Item=&'a SourceKey>,paths:Paths)->Result<(),Error>{
    let runs:i64=conn.query_row("SELECT count(*) FROM analysis_run",[],|r|r.get(0))?;
    if runs>=MAX_RUNS{return Err(Error::RunLimit);}
    let existing:i64=conn.query_row("SELECT count(*) FROM source_entry",[],|r|r.get(0))?;
    if existing.checked_add(n as i64).is_none_or(|v|v>MAX_TOTAL_ENTRIES){return Err(Error::EntryLimit);}
    if paths==Paths::IncludeLogical{
        let used:i64=conn.query_row("SELECT coalesce(sum(length(logical_key)),0) FROM source_entry",[],|r|r.get(0))?;
        let extra=keys.try_fold(0i64,|sum,k|sum.checked_add(encode_key(k).len() as i64).ok_or(Error::KeyLimit))?;
        if used.checked_add(extra).is_none_or(|v|v>MAX_KEY_PAYLOAD){return Err(Error::KeyLimit);}
    }
    Ok(())
}
fn page_after(after:Option<i64>,limit:usize)->Result<i64,Error>{
    if limit==0||limit>MAX_PAGE_SIZE||after.is_some_and(|n|n<=0){return Err(Error::InvalidPage);}
    Ok(after.unwrap_or(0))
}
fn fixed_blob<const N:usize>(bytes:Vec<u8>)->Result<[u8;N],Error>{bytes.try_into().map_err(|_|Error::InvalidDatabase)}
fn decode_key(mut b:&[u8])->Result<SourceKey,Error>{
    fn take<'a>(b:&mut &'a [u8],n:usize)->Result<&'a [u8],Error>{
        if n>b.len(){return Err(Error::InvalidDatabase);}
        let (a,rest)=b.split_at(n);*b=rest;Ok(a)
    }
    fn text<'a>(b:&mut &'a [u8])->Result<&'a str,Error>{
        let n=u32::from_be_bytes(take(b,4)?.try_into().map_err(|_|Error::InvalidDatabase)?) as usize;
        if n==0||n>negrodroid_core::inventory::MAX_PATH_BYTES{return Err(Error::InvalidDatabase);}
        std::str::from_utf8(take(b,n)?).map_err(|_|Error::InvalidDatabase)
    }
    if b.len()>40000||take(&mut b,1)?!=[1]{return Err(Error::InvalidDatabase);}
    let root=u64::from_be_bytes(take(&mut b,8)?.try_into().map_err(|_|Error::InvalidDatabase)?);
    let mut key=SourceKey::physical(root,text(&mut b)?).map_err(|_|Error::InvalidDatabase)?;
    let n=take(&mut b,1)?[0] as usize;
    if n>negrodroid_core::inventory::MAX_CONTAINER_DEPTH{return Err(Error::InvalidDatabase);}
    for _ in 0..n{key=key.member(text(&mut b)?).map_err(|_|Error::InvalidDatabase)?;}
    if !b.is_empty(){return Err(Error::InvalidDatabase);}
    Ok(key)
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
    fn rejects_inconsistent_report_and_accepts_header_mode(){
        let mut s=Store::memory().unwrap();let mut r=sample();r.summary.observed=0;
        assert!(matches!(s.save_analysis(&r,Paths::Omit),Err(Error::InvalidReport(_))));
        let r=run_with_headers(vec![task("x",b"x",1)],cfg(),Cancellation::default()).unwrap();
        let n:i64=s.conn.query_row("SELECT count(*) FROM analysis_run",[],|r|r.get(0)).unwrap();assert_eq!(n,0);
        let id=s.save_analysis(&r,Paths::Omit).unwrap();
        let j=s.document(id).unwrap().unwrap();
        assert!(j.contains("\"schema_version\":2"));
        assert!(j.contains("\"header_inspection\""));
    }
    #[test]
    fn injected_sql_error_rolls_back_entire_transaction(){
        let mut s=Store::memory().unwrap();
        s.conn.execute_batch("CREATE TRIGGER synthetic_fail BEFORE INSERT ON source_entry WHEN NEW.ordinal=2 BEGIN SELECT RAISE(ABORT,'synthetic'); END;").unwrap();
        let r=run(vec![task("a",b"a",1),task("b",b"b",1)],cfg(),Cancellation::default()).unwrap();
        assert!(matches!(s.save_analysis(&r,Paths::Omit),Err(Error::Sql(_))));
        for table in ["analysis_run","source_entry","report_document"]{
            let n:i64=s.conn.query_row(&format!("SELECT count(*) FROM {table}"),[],|r|r.get(0)).unwrap();assert_eq!(n,0);
        }
    }
    #[test]
    fn full_document_exact_and_privacy_preserved(){
        let mut s=Store::memory().unwrap();
        let r=run_with_headers(vec![task("private/png",b"\x89PNG\r\n\x1a\n",8),task("private/fail",b"",1)],cfg(),Cancellation::default()).unwrap();
        for paths in [Paths::Omit,Paths::IncludeLogical]{
            let expected=export_json(&r,Options{max_bytes:MAX_EXPORT_BYTES,paths}).unwrap();
            let id=s.save_analysis(&r,paths).unwrap();
            let actual=s.document(id).unwrap().unwrap();
            assert_eq!(actual,expected);assert!(actual.contains("malformed_header"));assert!(actual.contains("UnexpectedEof"));
            assert_eq!(actual.contains("private/"),paths==Paths::IncludeLogical);
        }
    }
    #[test]
    fn document_failure_rolls_back_rows_and_run(){
        let mut s=Store::memory().unwrap();
        s.conn.execute_batch("CREATE TRIGGER synthetic_doc_fail BEFORE INSERT ON report_document BEGIN SELECT RAISE(ABORT,'synthetic'); END;").unwrap();
        assert!(matches!(s.save_analysis(&sample(),Paths::Omit),Err(Error::Sql(_))));
        for table in ["analysis_run","source_entry","report_document"]{
            let n:i64=s.conn.query_row(&format!("SELECT count(*) FROM {table}"),[],|r|r.get(0)).unwrap();assert_eq!(n,0);
        }
    }
    #[test]
    fn document_required_and_immutable(){
        let mut s=Store::memory().unwrap();
        s.conn.execute("INSERT INTO analysis_run(kind,path_policy,planned,omissions) VALUES('analysis','omitted',0,0)",[]).unwrap();
        let id=s.conn.last_insert_rowid();
        assert!(s.conn.execute("UPDATE analysis_run SET sealed=1 WHERE id=?1",[id]).is_err());
        assert!(s.conn.execute("INSERT INTO report_document VALUES(?1,1,'{}')",[id]).is_err());
        assert_eq!(s.document(id).unwrap(),None);
        let id=s.save_analysis(&sample(),Paths::Omit).unwrap();
        assert!(s.conn.execute("UPDATE report_document SET payload='{}' WHERE run_id=?1",[id]).is_err());
        assert!(s.conn.execute("DELETE FROM report_document WHERE run_id=?1",[id]).is_err());
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

/// Read-only access to a closed, trusted database previously created by this
/// adapter. Not a general-purpose SQLite browser or an authenticity check.
pub struct Reader {store:Store}
impl Reader {
    /// Requires an absolute path in a trusted stable directory, with no active
    /// SQLite writer, journal/WAL/SHM sidecars or concurrent modification.
    /// Does not migrate, repair, create or overwrite a database. OS path races,
    /// malicious SQLite files and hostile storage are outside this contract.
    pub fn open_existing(path:&Path)->Result<Self,Error>{
        if !path.is_absolute(){return Err(Error::InvalidDestination);}
        let m=std::fs::symlink_metadata(path)?;
        if !m.is_file()||m.file_type().is_symlink(){return Err(Error::InvalidDestination);}
        #[cfg(windows)]
        {use std::os::windows::fs::MetadataExt;
            if m.file_attributes()&0x400!=0{return Err(Error::InvalidDestination);}}
        if m.len()>MAX_REOPEN_BYTES{return Err(Error::PhysicalLimit);}
        if m.len()<100{return Err(Error::InvalidDatabase);}
        for suffix in ["-journal","-wal","-shm"]{
            let mut p=path.as_os_str().to_os_string();p.push(suffix);
            match std::fs::symlink_metadata(std::path::PathBuf::from(p)){
                Ok(_)=>return Err(Error::ActiveSidecar),
                Err(e) if e.kind()==io::ErrorKind::NotFound=>{},
                Err(e)=>return Err(Error::Io(e)),
            }
        }
        let conn=Connection::open_with_flags(path,OpenFlags::SQLITE_OPEN_READ_ONLY|OpenFlags::SQLITE_OPEN_NO_MUTEX)?;
        conn.execute_batch("PRAGMA query_only=ON; PRAGMA trusted_schema=OFF; PRAGMA foreign_keys=ON;")?;
        let version:i64=conn.query_row("PRAGMA user_version",[],|r|r.get(0))?;
        if version!=4{return Err(Error::UnsupportedVersion);}
        let app:i64=conn.query_row("PRAGMA application_id",[],|r|r.get(0))?;
        if app!=APPLICATION_ID{return Err(Error::InvalidDatabase);}
        let reference=Store::memory()?;
        if schema_rows(&conn)?!=schema_rows(&reference.conn)?{return Err(Error::InvalidDatabase);}
        let ok:String=conn.query_row("PRAGMA integrity_check(1)",[],|r|r.get(0))?;
        if ok!="ok"{return Err(Error::InvalidDatabase);}
        {
            let mut stmt=conn.prepare("PRAGMA foreign_key_check")?;
            if stmt.exists([])?{return Err(Error::InvalidDatabase);}
        }
        let runs:i64=conn.query_row("SELECT count(*) FROM analysis_run",[],|r|r.get(0))?;
        if runs>MAX_RUNS{return Err(Error::RunLimit);}
        let used:i64=conn.query_row("SELECT coalesce(sum(length(CAST(payload AS BLOB))),0) FROM report_document",[],|r|r.get(0))?;
        if used>MAX_DOCUMENT_PAYLOAD{return Err(Error::PayloadLimit);}
        let entries:i64=conn.query_row("SELECT count(*) FROM source_entry",[],|r|r.get(0))?;
        if entries>MAX_TOTAL_ENTRIES{return Err(Error::EntryLimit);}
        let keys:i64=conn.query_row("SELECT coalesce(sum(length(logical_key)),0) FROM source_entry",[],|r|r.get(0))?;
        if keys>MAX_KEY_PAYLOAD{return Err(Error::KeyLimit);}
        let bad:i64=conn.query_row("SELECT count(*) FROM analysis_run r LEFT JOIN discovery_detail d ON d.run_id=r.id
            WHERE (r.kind='discovery' AND (d.run_id IS NULL OR d.files!=r.planned OR
            d.links+d.special+d.invalid_names+d.depth_skipped!=r.omissions))
            OR (r.kind='analysis' AND d.run_id IS NOT NULL)",[],|r|r.get(0))?;
        if bad!=0{return Err(Error::InvalidDatabase);}
        // A normal adapter never commits an unsealed run. Reject it rather
        // than pretending a partial database is a clean session history.
        let bad:i64=conn.query_row(
            "SELECT count(*) FROM analysis_run r WHERE r.sealed!=1 OR
             r.planned!=(SELECT count(*) FROM source_entry e WHERE e.run_id=r.id) OR
             (r.kind='analysis' AND NOT EXISTS(SELECT 1 FROM report_document d WHERE d.run_id=r.id)) OR
             (r.kind='discovery' AND EXISTS(SELECT 1 FROM report_document d WHERE d.run_id=r.id))",
             [],|r|r.get(0))?;
        if bad!=0{return Err(Error::InvalidDatabase);}
        let bad:i64=conn.query_row(
            "SELECT count(*) FROM report_document WHERE json_valid(payload)!=1",[],|r|r.get(0))?;
        if bad!=0{return Err(Error::InvalidDatabase);}
        let bad:i64=conn.query_row(
            "SELECT count(*) FROM report_document d JOIN analysis_run r ON r.id=d.run_id
             WHERE json_extract(d.payload,'$.schema_version') IS NOT d.schema_version
             OR json_extract(d.payload,'$.path_policy') IS NOT r.path_policy
             OR json_extract(d.payload,'$.summary.planned') IS NOT r.planned
             OR json_type(d.payload,'$.entries') IS NOT 'array'
             OR json_array_length(d.payload,'$.entries') IS NOT r.planned",[],|r|r.get(0))?;
        if bad!=0{return Err(Error::InvalidDatabase);}
        Ok(Self{store:Store{conn}})
    }
    pub fn sessions(&self,after:Option<i64>,limit:usize)->Result<Page<SessionRow,i64>,Error>{self.store.sessions(after,limit)}
    pub fn entries(&self,id:i64,after:Option<u32>,limit:usize,paths:Paths)->Result<Page<EntryRow,u32>,Error>{self.store.entries(id,after,limit,paths)}
    pub fn discovery_counts(&self,id:i64)->Result<Option<Counts>,Error>{self.store.discovery_counts(id)}
    pub fn summary(&self,id:i64)->Result<Option<Summary>,Error>{self.store.summary(id)}
    pub fn document(&self,id:i64)->Result<Option<String>,Error>{self.store.document(id)}
}
fn schema_rows(conn:&Connection)->Result<Vec<(String,String,String,Option<String>)>,Error>{
    let mut stmt=conn.prepare("SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name")?;
    let mut rows=stmt.query([])?;
    let mut result=Vec::new();
    while let Some(row)=rows.next()?{
        // The compiled schema is small; unexpected objects cannot grow the
        // comparison result indefinitely.
        if result.len()>=64{return Err(Error::InvalidDatabase);}
        result.push((row.get(0)?,row.get(1)?,row.get(2)?,row.get(3)?));
    }
    Ok(result)
}
#[cfg(test)]
mod reopen_tests {
    use super::*;
    use negrodroid_core::{Cancellation,orchestration::{run,Config},parallel::Task};
    use std::{fs,io::Cursor,path::PathBuf,sync::atomic::{AtomicUsize,Ordering}};
    static NEXT:AtomicUsize=AtomicUsize::new(0);
    struct Temp(PathBuf);
    impl Temp{
        fn new()->Self{
            loop{
                let p=std::env::temp_dir().join(format!("negrodroid-reopen-{}-{}",std::process::id(),NEXT.fetch_add(1,Ordering::Relaxed)));
                match fs::create_dir(&p){Ok(())=>return Self(p),Err(e) if e.kind()==io::ErrorKind::AlreadyExists=>continue,Err(e)=>panic!("{e}")}
            }
        }
        fn path(&self)->PathBuf{self.0.join("index.sqlite")}
    }
    impl Drop for Temp{fn drop(&mut self){let _=fs::remove_dir_all(&self.0);}}
    fn fixture(p:&Path)->(i64,String){
        let r=run(vec![Task{key:SourceKey::physical(1,"x").unwrap(),reader:Cursor::new(b"abc"),length:3}],
            Config{workers:1,batch_size:1,byte_budget:6},Cancellation::default()).unwrap();
        let mut s=Store::create_new(p).unwrap();let id=s.save_analysis(&r,Paths::Omit).unwrap();
        (id,s.document(id).unwrap().unwrap())
    }
    #[test]
    fn public_read_only_reopen_preserves_document_and_disk_bytes(){
        let t=Temp::new();let p=t.path();let(id,j)=fixture(&p);
        let before=fs::read(&p).unwrap();
        let reader=Reader::open_existing(&p).unwrap();
        assert_eq!(reader.document(id).unwrap(),Some(j));
        assert_eq!(reader.summary(id).unwrap().unwrap().observed,1);
        assert_eq!(reader.document(id+1).unwrap(),None);
        assert!(reader.store.conn.execute("CREATE TABLE forbidden(x)",[]).is_err());
        drop(reader);assert_eq!(fs::read(&p).unwrap(),before);
    }
    #[test]
    fn missing_relative_and_not_a_database_refused(){
        let t=Temp::new();let p=t.path();
        assert!(Reader::open_existing(&p).is_err());assert!(!p.exists());
        assert!(matches!(Reader::open_existing(Path::new("relative.sqlite")),Err(Error::InvalidDestination)));
        fs::write(&p,b"invalid").unwrap();
        assert!(matches!(Reader::open_existing(&p),Err(Error::InvalidDatabase)));
        assert_eq!(fs::read(&p).unwrap(),b"invalid");
    }
    #[test]
    fn old_version_refused_without_migration(){
        let t=Temp::new();let p=t.path();
        let c=Connection::open(&p).unwrap();
        c.execute_batch(include_str!("../../core/schema/index_v3.sql")).unwrap();drop(c);
        let before=fs::read(&p).unwrap();
        assert!(matches!(Reader::open_existing(&p),Err(Error::UnsupportedVersion)));
        assert_eq!(fs::read(&p).unwrap(),before);
    }
    #[test]
    fn schema_drift_is_rejected(){
        let t=Temp::new();let p=t.path();fixture(&p);
        let c=Connection::open(&p).unwrap();c.execute_batch("DROP TRIGGER document_no_update;").unwrap();drop(c);
        assert!(matches!(Reader::open_existing(&p),Err(Error::InvalidDatabase)));
    }
    #[test]
    fn incomplete_run_rejected(){
        let t=Temp::new();let p=t.path();fixture(&p);
        let c=Connection::open(&p).unwrap();
        c.execute("INSERT INTO analysis_run(kind,path_policy,planned,omissions) VALUES('analysis','omitted',1,0)",[]).unwrap();drop(c);
        assert!(matches!(Reader::open_existing(&p),Err(Error::InvalidDatabase)));
    }
    #[test]
    fn sidecar_refused_without_removal(){
        let t=Temp::new();let p=t.path();fixture(&p);
        let mut side=p.as_os_str().to_os_string();side.push("-wal");let side=PathBuf::from(side);
        fs::write(&side,b"fixture").unwrap();
        assert!(matches!(Reader::open_existing(&p),Err(Error::ActiveSidecar)));
        assert_eq!(fs::read(side).unwrap(),b"fixture");
    }
    #[test]
    fn physical_cap_before_sqlite_open(){
        let t=Temp::new();let p=t.path();let f=OpenOptions::new().create_new(true).write(true).open(&p).unwrap();
        f.set_len(MAX_REOPEN_BYTES+1).unwrap();drop(f);
        assert!(matches!(Reader::open_existing(&p),Err(Error::PhysicalLimit)));
    }
    #[cfg(unix)]
    #[test]
    fn symlink_destination_rejected(){
        let t=Temp::new();let p=t.path();fixture(&p);
        let link=t.0.join("alias");std::os::unix::fs::symlink(&p,&link).unwrap();
        assert!(matches!(Reader::open_existing(&link),Err(Error::InvalidDestination)));
    }
}

#[cfg(test)]
mod discovery_storage_tests{
    use super::*;
    use negrodroid_core::inventory::{Inventory,Entry};
    fn fixture()->Discovery{
        let mut inventory=Inventory::new(2,4096);
        for (name,length) in [("private/a",0),("private/b",u64::MAX)]{
            inventory.insert(SourceKey::physical(9,name).unwrap(),Entry{declared_length:Some(length),format_hint:FormatHint::Unknown,coverage:Coverage::Unexamined,observation:None}).unwrap();
        }
        Discovery{inventory,counts:Counts{visited:6,files:2,directories:1,links:1,special:1,invalid_names:1,depth_skipped:1}}
    }
    #[test]
    fn counters_and_unexamined_rows_preserved(){
        let mut s=Store::memory().unwrap();let d=fixture();let id=s.save_discovery(&d,Paths::Omit).unwrap();
        assert_eq!(s.discovery_counts(id).unwrap(),Some(d.counts));
        assert_eq!(s.summary(id).unwrap().unwrap().state,"discovery_with_omissions");
        assert_eq!(s.document(id).unwrap(),None);
        let n:i64=s.conn.query_row("SELECT count(*) FROM source_entry WHERE status='unexamined' AND sha256 IS NULL AND charged_bytes IS NULL AND logical_key IS NULL",[],|r|r.get(0)).unwrap();assert_eq!(n,2);
        let length:Vec<u8>=s.conn.query_row("SELECT declared_length FROM source_entry WHERE ordinal=2",[],|r|r.get(0)).unwrap();assert_eq!(length,u64::MAX.to_be_bytes());
    }
    #[test]
    fn invalid_counts_and_metadata_rejected(){
        let mut s=Store::memory().unwrap();let mut d=fixture();d.counts.visited=usize::MAX;
        assert!(matches!(s.save_discovery(&d,Paths::Omit),Err(Error::InvalidDiscovery)));
        d.counts=fixture().counts;d.counts.files=1;
        assert!(matches!(s.save_discovery(&d,Paths::Omit),Err(Error::InvalidDiscovery)));
        let mut inventory=Inventory::new(1,4096);
        inventory.insert(SourceKey::physical(1,"x").unwrap(),Entry{declared_length:Some(1),format_hint:FormatHint::Zip,coverage:Coverage::Unexamined,observation:None}).unwrap();
        let d=Discovery{inventory,counts:Counts{visited:1,files:1,..Counts::default()}};
        assert!(matches!(s.save_discovery(&d,Paths::Omit),Err(Error::InvalidDiscovery)));
        let n:i64=s.conn.query_row("SELECT count(*) FROM analysis_run",[],|r|r.get(0)).unwrap();assert_eq!(n,0);
    }
    #[test]
    fn empty_discovery_is_not_analysis_completion(){
        let mut s=Store::memory().unwrap();
        let d=Discovery{inventory:Inventory::new(0,0),counts:Counts::default()};
        let id=s.save_discovery(&d,Paths::Omit).unwrap();
        assert_eq!(s.summary(id).unwrap().unwrap().state,"discovery_no_reported_omissions");
        assert_eq!(s.discovery_counts(id).unwrap(),Some(Counts::default()));
    }
    #[test]
    fn discovery_detail_failure_rolls_back_all_rows(){
        let mut s=Store::memory().unwrap();
        s.conn.execute_batch("CREATE TRIGGER synthetic_discovery_fail BEFORE INSERT ON discovery_detail BEGIN SELECT RAISE(ABORT,'synthetic'); END;").unwrap();
        assert!(matches!(s.save_discovery(&fixture(),Paths::Omit),Err(Error::Sql(_))));
        for table in ["analysis_run","source_entry","discovery_detail"]{
            let n:i64=s.conn.query_row(&format!("SELECT count(*) FROM {table}"),[],|r|r.get(0)).unwrap();assert_eq!(n,0);
        }
    }
    #[test]
    fn discovery_detail_required_and_key_policy(){
        let mut s=Store::memory().unwrap();
        s.conn.execute("INSERT INTO analysis_run(kind,path_policy,planned,omissions) VALUES('discovery','omitted',0,0)",[]).unwrap();
        let id=s.conn.last_insert_rowid();
        assert!(s.conn.execute("UPDATE analysis_run SET sealed=1 WHERE id=?1",[id]).is_err());
        let id=s.save_discovery(&fixture(),Paths::IncludeLogical).unwrap();
        let n:i64=s.conn.query_row("SELECT count(*) FROM source_entry WHERE run_id=?1 AND logical_key IS NOT NULL",[id],|r|r.get(0)).unwrap();assert_eq!(n,2);
        assert!(s.conn.execute("DELETE FROM discovery_detail WHERE run_id=?1",[id]).is_err());
    }
}

#[cfg(test)]
mod session_tests{
    use super::*;
    use negrodroid_core::{inventory::{Inventory,Entry},Cancellation,orchestration::{run,Config},parallel::Task};
    use std::io::Cursor;
    fn discovery()->Discovery{
        let mut inventory=Inventory::new(3,4096);
        for (name,length) in [("z",1),("private/a",u64::MAX),("b",0)]{
            inventory.insert(SourceKey::physical(7,name).unwrap(),Entry{declared_length:Some(length),format_hint:FormatHint::Unknown,coverage:Coverage::Unexamined,observation:None}).unwrap();
        }
        Discovery{inventory,counts:Counts{visited:3,files:3,..Counts::default()}}
    }
    fn analysis()->Report{
        run(vec![Task{key:SourceKey::physical(9,"a").unwrap().member("b/c").unwrap(),reader:Cursor::new(b"abc"),length:3}],
            Config{workers:1,batch_size:1,byte_budget:6},Cancellation::default()).unwrap()
    }
    #[test]
    fn session_pages_have_stable_order_and_no_overlap(){
        let mut s=Store::memory().unwrap();
        let a=s.save_discovery(&discovery(),Paths::Omit).unwrap();
        let b=s.save_analysis(&analysis(),Paths::IncludeLogical).unwrap();
        let c=s.save_discovery(&discovery(),Paths::Omit).unwrap();
        let first=s.sessions(None,2).unwrap();
        assert_eq!(first.rows.iter().map(|r|r.id).collect::<Vec<_>>(),vec![a,b]);
        assert_eq!(first.next,Some(b));assert_eq!(first.rows[0].kind,SessionKind::Discovery);
        assert_eq!(first.rows[0].state,SessionState::DiscoveryNoReportedOmissions);
        assert_eq!(first.rows[1].observed,1);assert_eq!(first.rows[1].stored_paths,Paths::IncludeLogical);
        let last=s.sessions(first.next,2).unwrap();assert_eq!(last.rows[0].id,c);assert_eq!(last.next,None);
        assert!(s.sessions(Some(c),2).unwrap().rows.is_empty());
    }
    #[test]
    fn entry_pages_exact_unsigned_and_paths_opt_in(){
        let mut s=Store::memory().unwrap();let id=s.save_discovery(&discovery(),Paths::IncludeLogical).unwrap();
        let first=s.entries(id,None,2,Paths::Omit).unwrap();
        assert_eq!(first.next,Some(2));assert_eq!(first.rows[0].declared_length,0);
        assert_eq!(first.rows[1].declared_length,u64::MAX);
        assert!(first.rows.iter().all(|r|r.logical_key.is_none()&&r.sha256.is_none()&&r.charged_bytes.is_none()&&r.status==EntryStatus::Unexamined));
        let last=s.entries(id,first.next,2,Paths::IncludeLogical).unwrap();
        assert_eq!(last.next,None);assert_eq!(last.rows[0].logical_key.as_ref().unwrap().relative_path(),"z");
        let id=s.save_discovery(&discovery(),Paths::Omit).unwrap();
        assert!(s.entries(id,None,3,Paths::IncludeLogical).unwrap().rows.iter().all(|r|r.logical_key.is_none()));
    }
    #[test]
    fn analysis_digest_and_nested_key_round_trip(){
        let mut s=Store::memory().unwrap();let r=analysis();let id=s.save_analysis(&r,Paths::IncludeLogical).unwrap();
        let row=s.entries(id,None,1,Paths::IncludeLogical).unwrap().rows.pop().unwrap();
        let (key,entry)=r.inventory.iter().next().unwrap();
        assert_eq!(row.logical_key.as_ref(),Some(key));assert_eq!(row.status,EntryStatus::Observed);
        assert_eq!(row.sha256,Some(*entry.observation.unwrap().sha256.bytes()));assert_eq!(row.charged_bytes,Some(6));
    }
    #[test]
    fn invalid_pages_and_unsealed_sessions_refused(){
        let mut s=Store::memory().unwrap();
        for limit in [0,MAX_PAGE_SIZE+1,usize::MAX]{assert!(matches!(s.sessions(None,limit),Err(Error::InvalidPage)));}
        assert!(matches!(s.sessions(Some(-1),1),Err(Error::InvalidPage)));
        assert!(matches!(s.entries(99,None,1,Paths::Omit),Err(Error::UnknownSession)));
        s.conn.execute("INSERT INTO analysis_run(kind,path_policy,planned,omissions) VALUES('discovery','omitted',0,0)",[]).unwrap();
        let id=s.conn.last_insert_rowid();
        assert!(s.sessions(None,1).unwrap().rows.is_empty());
        assert!(matches!(s.entries(id,None,1,Paths::Omit),Err(Error::UnknownSession)));
    }
    #[test]
    fn key_decoder_rejects_truncation_versions_and_trailing_bytes(){
        let key=SourceKey::physical(u64::MAX,"配置/a").unwrap().member("b").unwrap();
        let bytes=encode_key(&key);assert_eq!(decode_key(&bytes).unwrap(),key);
        for n in 0..bytes.len(){assert!(decode_key(&bytes[..n]).is_err());}
        let mut bad=bytes.clone();bad[0]=2;assert!(decode_key(&bad).is_err());
        let mut bad=bytes;bad.push(0);assert!(decode_key(&bad).is_err());
    }
    #[test]
    fn empty_session_and_exact_page_boundary(){
        let mut s=Store::memory().unwrap();
        let id=s.save_discovery(&Discovery{inventory:Inventory::new(0,0),counts:Counts::default()},Paths::Omit).unwrap();
        let p=s.entries(id,None,1,Paths::Omit).unwrap();assert!(p.rows.is_empty());assert_eq!(p.next,None);
        let id=s.save_discovery(&discovery(),Paths::Omit).unwrap();
        let p=s.entries(id,None,3,Paths::Omit).unwrap();assert_eq!(p.rows.len(),3);assert_eq!(p.next,None);
    }
}

#[cfg(test)]
mod final_guard_tests{
    use super::*;
    #[test]
    fn replace_cannot_unseal_even_without_recursive_triggers(){
        let s=Store::memory().unwrap();
        s.conn.execute_batch("PRAGMA recursive_triggers=OFF;
            INSERT INTO analysis_run(id,kind,path_policy,planned,omissions) VALUES(1,'discovery','omitted',0,0);
            INSERT INTO discovery_detail VALUES(1,0,0,0,0,0,0,0);
            UPDATE analysis_run SET sealed=1 WHERE id=1;").unwrap();
        assert!(s.conn.execute("INSERT OR REPLACE INTO analysis_run(id,kind,path_policy,planned,omissions) VALUES(1,'analysis','omitted',0,0)",[]).is_err());
        assert_eq!(s.summary(1).unwrap().unwrap().state,"discovery_no_reported_omissions");
    }
    #[test]
    fn duplicate_source_and_detail_cannot_be_replaced_before_sealing(){
        let s=Store::memory().unwrap();
        s.conn.execute_batch("PRAGMA recursive_triggers=OFF;
            INSERT INTO analysis_run(id,kind,path_policy,planned,omissions) VALUES(1,'discovery','logical_opt_in',2,0);
            INSERT INTO source_entry VALUES(1,1,X'01',X'0000000000000001','unknown','unexamined',NULL,NULL);
            INSERT INTO discovery_detail VALUES(1,2,2,0,0,0,0,0);").unwrap();
        for stmt in [
            "INSERT OR REPLACE INTO source_entry VALUES(1,1,X'02',X'0000000000000002','unknown','unexamined',NULL,NULL)",
            "INSERT OR REPLACE INTO source_entry VALUES(1,2,X'01',X'0000000000000002','unknown','unexamined',NULL,NULL)",
            "INSERT OR REPLACE INTO discovery_detail VALUES(1,3,2,1,0,0,0,0)"
        ]{assert!(s.conn.execute(stmt,[]).is_err());}
    }
    #[test]
    fn invalid_format_and_observation_charge_rejected(){
        let s=Store::memory().unwrap();
        s.conn.execute("INSERT INTO analysis_run(id,kind,path_policy,planned,omissions) VALUES(1,'analysis','omitted',1,0)",[]).unwrap();
        for stmt in [
            "INSERT INTO source_entry VALUES(1,1,NULL,X'0000000000000001','invented','failed',NULL,X'0000000000000000')",
            "INSERT INTO source_entry VALUES(1,1,NULL,X'0000000000000001','png','not_started',NULL,X'0000000000000000')",
            "INSERT INTO source_entry VALUES(1,1,NULL,X'0000000000000002','unknown','observed',zeroblob(32),X'0000000000000001')"
        ]{assert!(s.conn.execute(stmt,[]).is_err());}
    }
}
