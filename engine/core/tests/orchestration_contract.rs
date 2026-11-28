use negrodroid_core::{Cancellation, orchestration::{run, Config, RunError, RunState},
    parallel::{Task, Status, BatchError, MAX_BATCH_TASKS}, inventory::{SourceKey, Coverage}};
use std::{io::{self, Cursor, Read, Seek, SeekFrom}, sync::{Arc, atomic::{AtomicUsize, Ordering}}};

fn config(batch_size: usize, byte_budget: u64) -> Config { Config { workers: 2, batch_size, byte_budget } }
fn task(name: &str, data: &[u8], length: u64) -> Task<Cursor<Vec<u8>>> {
    Task { key: SourceKey::physical(1,name).unwrap(), reader: Cursor::new(data.to_vec()), length }
}
#[test]
fn chunk_sizes_preserve_inventory_and_diagnostics() {
    let input = || vec![task("z",b"x",1),task("a",b"y",1),task("m",b"z",1)];
    let a = run(input(),config(1,6),Cancellation::default()).unwrap();
    let b = run(input(),config(3,6),Cancellation::default()).unwrap();
    assert!(a.inventory.iter().eq(b.inventory.iter()));
    assert_eq!(a.diagnostics,b.diagnostics);
    assert_eq!(a.summary.batches,3);
    assert_eq!(b.summary.batches,1);
    assert_eq!(a.summary.observed,3);
    assert_eq!(a.summary.charged_bytes,6);
    assert_eq!(a.summary.state(),RunState::Complete);
}
#[test]
fn empty_scope_is_complete_without_work() {
    let r = run(Vec::<Task<Cursor<Vec<u8>>>>::new(),config(1,0),Cancellation::default()).unwrap();
    assert_eq!(r.summary.state(),RunState::Complete);
    assert_eq!(r.summary.batches,0);
    assert!(r.inventory.is_empty());
}
#[test]
fn invalid_batch_configuration_is_rejected() {
    for size in [0,MAX_BATCH_TASKS+1] {
        assert!(matches!(run(vec![task("a",b"x",1)],config(size,2),Cancellation::default()),Err(RunError::InvalidBatchSize)));
    }
    let cfg = Config { workers: 0, ..config(1,2) };
    assert!(matches!(run(vec![task("a",b"x",1)],cfg,Cancellation::default()),Err(RunError::Analysis(BatchError::WorkerLimit))));
}
#[test]
fn scope_ceiling_applies_across_chunks() {
    let tasks = (0..=MAX_BATCH_TASKS).map(|i| task(&i.to_string(),b"",0)).collect();
    assert!(matches!(run(tasks,config(1,0),Cancellation::default()),Err(RunError::Analysis(BatchError::TaskLimit))));
}
struct Tracked { inner: Cursor<Vec<u8>>, reads: Arc<AtomicUsize>, cancel: Option<Cancellation> }
impl Read for Tracked {
    fn read(&mut self, buf: &mut [u8]) -> io::Result<usize> {
        self.reads.fetch_add(1,Ordering::SeqCst);
        if let Some(c) = self.cancel.take() { c.cancel(); }
        self.inner.read(buf)
    }
}
impl Seek for Tracked { fn seek(&mut self,p: SeekFrom)->io::Result<u64> { self.inner.seek(p) } }
fn tracked(name: &str, reads: Arc<AtomicUsize>, cancel: Option<Cancellation>) -> Task<Tracked> {
    Task { key: SourceKey::physical(1,name).unwrap(), length: 1,
        reader: Tracked { inner: Cursor::new(vec![1]), reads, cancel } }
}
#[test]
fn entire_scope_budget_checked_before_first_chunk() {
    let reads = Arc::new(AtomicUsize::new(0));
    let tasks = vec![tracked("a",reads.clone(),None),tracked("b",reads.clone(),None)];
    assert!(matches!(run(tasks,config(1,3),Cancellation::default()),Err(RunError::Analysis(BatchError::ReadBudget))));
    assert_eq!(reads.load(Ordering::SeqCst),0);
}
#[test]
fn duplicates_across_chunks_rejected_before_io() {
    let reads = Arc::new(AtomicUsize::new(0));
    let tasks = vec![tracked("a",reads.clone(),None),tracked("a",reads.clone(),None)];
    assert!(matches!(run(tasks,config(1,4),Cancellation::default()),Err(RunError::Analysis(BatchError::Duplicate))));
    assert_eq!(reads.load(Ordering::SeqCst),0);
}
#[test]
fn item_failure_preserves_later_chunks_and_diagnostics() {
    let r = run(vec![task("a",b"x",2),task("b",b"y",1)],config(1,6),Cancellation::default()).unwrap();
    assert_eq!(r.summary.state(),RunState::WithFailures);
    assert_eq!(r.summary.failed,1);
    assert_eq!(r.summary.observed,1);
    assert_eq!(r.inventory.len(),2);
    let k = SourceKey::physical(1,"a").unwrap();
    assert_eq!(r.diagnostics[&k].status,Status::Failed(io::ErrorKind::UnexpectedEof));
    assert!(r.inventory.get(&k).unwrap().observation.is_none());
}
#[test]
fn cancelled_scope_preserves_all_keys_and_no_hash() {
    let c = Cancellation::default(); c.cancel();
    let r = run(vec![task("a",b"x",1),task("b",b"y",1)],config(1,4),c).unwrap();
    assert_eq!(r.summary.state(),RunState::Cancelled);
    assert_eq!(r.summary.not_started,2);
    assert_eq!(r.summary.charged_bytes,0);
    assert!(r.inventory.iter().all(|(_,e)| e.coverage == Coverage::Unexamined && e.observation.is_none()));
}
#[test]
fn cancellation_during_first_chunk_preserves_later_keys() {
    let c = Cancellation::default();
    let reads = Arc::new(AtomicUsize::new(0));
    let tasks = vec![tracked("a",reads.clone(),Some(c.clone())),tracked("b",reads.clone(),None)];
    let r = run(tasks,config(1,4),c).unwrap();
    assert_eq!(r.summary.cancelled,1);
    assert_eq!(r.summary.not_started,1);
    assert_eq!(r.summary.charged_bytes,1);
    assert_eq!(r.summary.reserved_bytes,4);
    assert_eq!(r.summary.state(),RunState::Cancelled);
    assert_eq!(r.inventory.len(),2);
    assert_eq!(reads.load(Ordering::SeqCst),1);
}
