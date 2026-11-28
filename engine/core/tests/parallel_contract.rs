use negrodroid_core::{Cancellation, parallel::{run, Task, Status, BatchError, MAX_WORKERS}};
use negrodroid_core::inventory::{Coverage, Inventory, SourceKey};
use negrodroid_core::format::FormatHint;
use std::{io::{self, Cursor, Read, Seek, SeekFrom}, sync::{Arc, Barrier, atomic::{AtomicUsize, Ordering}}};

fn task(name: &str, data: &[u8], length: u64) -> Task<Cursor<Vec<u8>>> {
    Task { key: SourceKey::physical(1,name).unwrap(), reader: Cursor::new(data.to_vec()), length }
}
#[test]
fn worker_counts_produce_identical_ordered_inventory() {
    let input = || vec![task("z",b"MZ",2),task("a",b"PK\x03\x04",4),task("m",b"",0)];
    let one = run(input(),1,100,Cancellation::default()).unwrap();
    let many = run(input(),4,100,Cancellation::default()).unwrap();
    assert_eq!(one,many);
    assert_eq!(many.reserved_bytes,12);
    assert_eq!(many.outcomes[0].key.relative_path(),"a");
    assert_eq!(many.outcomes[0].entry.format_hint,FormatHint::Zip);
    let mut inventory = Inventory::new(3,100);
    for item in many.outcomes { assert_eq!(item.status,Status::Observed); inventory.insert(item.key,item.entry).unwrap(); }
    assert_eq!(inventory.len(),3);
}
#[test]
fn invalid_workers_and_empty_batch() {
    for n in [0,MAX_WORKERS+1] {
        assert_eq!(run(vec![task("a",b"a",1)],n,10,Cancellation::default()),Err(BatchError::WorkerLimit));
    }
    assert!(run(Vec::<Task<Cursor<Vec<u8>>>>::new(),2,0,Cancellation::default()).unwrap().outcomes.is_empty());
}
#[test]
fn rejects_duplicate_and_overflow() {
    assert_eq!(run(vec![task("a",b"a",1),task("a",b"b",1)],2,100,Cancellation::default()),Err(BatchError::Duplicate));
    assert_eq!(run(vec![task("x",b"",u64::MAX)],1,u64::MAX,Cancellation::default()),Err(BatchError::ReadBudget));
}
struct Reader { inner: Cursor<Vec<u8>>, reads: Arc<AtomicUsize>, barrier: Option<Arc<Barrier>>, cancel: Option<Cancellation> }
impl Read for Reader {
    fn read(&mut self, buf: &mut [u8]) -> io::Result<usize> {
        self.reads.fetch_add(1,Ordering::SeqCst);
        if let Some(b) = self.barrier.take() { b.wait(); }
        if let Some(c) = self.cancel.take() { c.cancel(); }
        self.inner.read(buf)
    }
}
impl Seek for Reader { fn seek(&mut self,p: SeekFrom)->io::Result<u64> { self.inner.seek(p) } }
fn tracked(name: &str, reads: Arc<AtomicUsize>, barrier: Option<Arc<Barrier>>, cancel: Option<Cancellation>) -> Task<Reader> {
    Task { key: SourceKey::physical(1,name).unwrap(), length: 1,
        reader: Reader { inner: Cursor::new(vec![1]), reads, barrier, cancel } }
}
#[test]
fn global_budget_rejected_before_any_read() {
    let reads = Arc::new(AtomicUsize::new(0));
    let t = vec![tracked("a",reads.clone(),None,None),tracked("b",reads.clone(),None,None)];
    assert_eq!(run(t,2,3,Cancellation::default()),Err(BatchError::ReadBudget));
    assert_eq!(reads.load(Ordering::SeqCst),0);
}
#[test]
fn independent_workers_overlap() {
    let reads = Arc::new(AtomicUsize::new(0));
    let b = Arc::new(Barrier::new(2));
    let t = vec![tracked("a",reads.clone(),Some(b.clone()),None),tracked("b",reads.clone(),Some(b),None)];
    let result = run(t,2,4,Cancellation::default()).unwrap();
    assert!(result.outcomes.iter().all(|o| o.status == Status::Observed && o.charged_bytes == 2));
    assert_eq!(reads.load(Ordering::SeqCst),4);
}
#[test]
fn pre_cancelled_work_is_not_started() {
    let c = Cancellation::default(); c.cancel();
    let r = run(vec![task("a",b"x",1)],1,2,c).unwrap();
    let o = &r.outcomes[0];
    assert_eq!(o.status,Status::NotStarted);
    assert_eq!(o.entry.coverage,Coverage::Unexamined);
    assert_eq!(o.charged_bytes,0);
    assert!(o.entry.observation.is_none());
}
#[test]
fn cancellation_during_read_distinguishes_next_item() {
    let c = Cancellation::default();
    let reads = Arc::new(AtomicUsize::new(0));
    let t = vec![tracked("a",reads.clone(),None,Some(c.clone())),tracked("b",reads.clone(),None,None)];
    let r = run(t,1,4,c).unwrap();
    assert_eq!(r.outcomes[0].status,Status::Cancelled);
    assert_eq!(r.outcomes[0].entry.coverage,Coverage::Cancelled);
    assert!(r.outcomes[0].entry.observation.is_none());
    assert_eq!(r.outcomes[1].status,Status::NotStarted);
    assert_eq!(reads.load(Ordering::SeqCst),1);
}
#[test]
fn truncated_reader_does_not_poison_other_items() {
    let r = run(vec![task("a",b"x",2),task("b",b"y",1)],2,6,Cancellation::default()).unwrap();
    assert_eq!(r.outcomes[0].status,Status::Failed(io::ErrorKind::UnexpectedEof));
    assert_eq!(r.outcomes[0].entry.coverage,Coverage::Failed);
    assert!(r.outcomes[0].entry.observation.is_none());
    assert_eq!(r.outcomes[1].status,Status::Observed);
}
#[test]
fn distant_pe_signature_fits_conservative_reservation() {
    let mut b = vec![0;1024];
    b[..2].copy_from_slice(b"MZ");
    b[60..64].copy_from_slice(&768u32.to_le_bytes());
    b[768..772].copy_from_slice(b"PE\0\0");
    let r = run(vec![task("p",&b,1024)],1,1540,Cancellation::default()).unwrap();
    assert_eq!(r.reserved_bytes,1540);
    assert_eq!(r.outcomes[0].charged_bytes,1540);
    assert_eq!(r.outcomes[0].entry.format_hint,FormatHint::PortableExecutable);
    assert_eq!(r.outcomes[0].status,Status::Observed);
}
