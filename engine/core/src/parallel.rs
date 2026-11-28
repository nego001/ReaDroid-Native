//! Bounded, read-only batch analysis. Callers provide independent stable readers.
use crate::{Cancellation, ReadSession};
use crate::evidence::observe_source;
use crate::structural::{self, Verdict, MAX_HEADER_BYTES};
use crate::format::{probe, FormatHint, PREFIX_LIMIT};
use crate::inventory::{Coverage, Entry, SourceKey, MAX_INDEX_PATH_BYTES};
use std::{io::{self, Read, Seek}, thread};

pub const MAX_BATCH_TASKS: usize = 4096;
pub const MAX_WORKERS: usize = 16;

pub struct Task<R> {
    pub key: SourceKey,
    pub reader: R,
    pub length: u64,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BatchError { WorkerLimit, TaskLimit, PathBudget, Duplicate, ReadBudget, ThreadSpawn, WorkerPanic }
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Status { Observed, Failed(io::ErrorKind), Cancelled, NotStarted }
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Outcome {
    pub key: SourceKey,
    pub entry: Entry,
    pub status: Status,
    /// Admitted read requests, including failures; not physical disk I/O.
    pub charged_bytes: u64,
    pub header: Option<Verdict>,
}
#[derive(Debug, PartialEq, Eq)]
pub struct Batch {
    pub reserved_bytes: u64,
    pub outcomes: Vec<Outcome>,
}
pub(crate) fn reservation(length: u64) -> Option<u64> {
    length.checked_add(length.min(PREFIX_LIMIT as u64))?
        .checked_add(if length > PREFIX_LIMIT as u64 { 4 } else { 0 })
}
pub(crate) fn reservation_mode(length:u64, headers:bool)->Option<u64>{
    reservation(length)?.checked_add(if headers {length.min(MAX_HEADER_BYTES as u64)} else {0})
}
fn analyze<R: Read + Seek>(task: Task<R>, cancel: &Cancellation, headers:bool) -> Outcome {
    let Task { key, reader, length } = task;
    let mut entry = Entry { declared_length: Some(length), format_hint: FormatHint::Unknown,
        coverage: Coverage::Unexamined, observation: None };
    if cancel.is_cancelled() {
        return Outcome { key, entry, status: Status::NotStarted, charged_bytes: 0, header: None };
    }
    let budget = reservation_mode(length,headers).expect("preflight verified");
    let mut s = ReadSession::new(reader, length, budget, cancel.clone());
    let mut header=None;
    let result = probe(&mut s).and_then(|p| {
        entry.format_hint = p.hint;
        if headers { header=Some(structural::inspect(&mut s,p.hint)?); }
        observe_source(&mut s)
    });
    let status = match result {
        Ok(o) => { entry.coverage = Coverage::Observed; entry.observation = Some(o); Status::Observed }
        Err(e) if e.kind() == io::ErrorKind::Interrupted && cancel.is_cancelled() => {
            entry.coverage = Coverage::Cancelled; Status::Cancelled
        }
        Err(e) => { entry.coverage = Coverage::Failed; Status::Failed(e.kind()) }
    };
    if status != Status::Observed {header=None;}
    Outcome { key, entry, status, charged_bytes: budget - s.remaining_budget(), header }
}
/// All-or-nothing admission before reading. Static round-robin partitions,
/// independent cursors, fixed worker ceiling and key-ordered output.
/// Reserve worst-case probe + hash per item; unused reservations are not
/// redistributed. Cancellation is cooperative, not a deadline for OS I/O.
/// Caller-owned readers, handles and allocations are not bounded by this API.
pub fn run<R: Read + Seek + Send>(tasks: Vec<Task<R>>, workers: usize,
    byte_budget: u64, cancel: Cancellation) -> Result<Batch, BatchError> {
    run_mode(tasks,workers,byte_budget,cancel,false)
}
pub(crate) fn run_mode<R: Read + Seek + Send>(mut tasks: Vec<Task<R>>, workers: usize,
    byte_budget: u64, cancel: Cancellation, headers:bool) -> Result<Batch, BatchError> {
    let reserved_bytes = preflight_mode(&mut tasks, workers, byte_budget,headers)?;
    if tasks.is_empty() { return Ok(Batch { reserved_bytes, outcomes: Vec::new() }); }
    let count = workers.min(tasks.len());
    let mut partitions: Vec<Vec<Task<R>>> = (0..count).map(|_| Vec::new()).collect();
    for (i,t) in tasks.into_iter().enumerate() { partitions[i % count].push(t); }
    let mut outcomes = thread::scope(|scope| {
        let mut handles = Vec::with_capacity(count);
        let mut error = None;
        for part in partitions {
            let c = cancel.clone();
            match thread::Builder::new().spawn_scoped(scope, move || {
                part.into_iter().map(|t| analyze(t, &c, headers)).collect::<Vec<_>>()
            }) {
                Ok(h) => handles.push(h),
                Err(_) => { error = Some(BatchError::ThreadSpawn); break; }
            }
        }
        let mut results = Vec::new();
        for h in handles {
            match h.join() {
                Ok(mut v) => results.append(&mut v),
                Err(_) => { error = Some(BatchError::WorkerPanic); }
            }
        }
        match error { Some(e) => Err(e), None => Ok(results) }
    })?;
    outcomes.sort_unstable_by(|a,b| a.key.cmp(&b.key));
    Ok(Batch { reserved_bytes, outcomes })
}

/// Shared admission checks for a batch or the entire orchestration scope.
pub(crate) fn preflight_mode<R>(tasks: &mut [Task<R>], workers: usize, byte_budget: u64, headers:bool) -> Result<u64, BatchError> {
    if workers == 0 || workers > MAX_WORKERS { return Err(BatchError::WorkerLimit); }
    if tasks.len() > MAX_BATCH_TASKS { return Err(BatchError::TaskLimit); }
    tasks.sort_unstable_by(|a,b| a.key.cmp(&b.key));
    if tasks.windows(2).any(|w| w[0].key == w[1].key) { return Err(BatchError::Duplicate); }
    let mut path_bytes = 0usize;
    let mut reserved_bytes = 0u64;
    for t in tasks.iter() {
        let n = t.key.relative_path().len() + t.key.members().iter().map(String::len).sum::<usize>();
        path_bytes = path_bytes.checked_add(n).ok_or(BatchError::PathBudget)?;
        if path_bytes > MAX_INDEX_PATH_BYTES { return Err(BatchError::PathBudget); }
        reserved_bytes = reserved_bytes.checked_add(reservation_mode(t.length,headers).ok_or(BatchError::ReadBudget)?)
            .ok_or(BatchError::ReadBudget)?;
        if reserved_bytes > byte_budget { return Err(BatchError::ReadBudget); }
    }
    Ok(reserved_bytes)
}
