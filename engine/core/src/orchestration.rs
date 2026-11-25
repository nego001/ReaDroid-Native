//! Coordinates read-only analysis in bounded batches; not a DAG or persistent scheduler.
use crate::{Cancellation, inventory::{Inventory, IndexError, SourceKey, MAX_INDEX_PATH_BYTES},
    parallel::{self, BatchError, Task, Status, MAX_BATCH_TASKS}};
use std::{collections::BTreeMap, io::{Read, Seek}};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Config {
    pub workers: usize,
    pub batch_size: usize,
    pub byte_budget: u64,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RunError { InvalidBatchSize, Analysis(BatchError), Inventory(IndexError), Accounting }
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RunState { Complete, WithFailures, Cancelled }
#[derive(Debug, Default, Clone, Copy, PartialEq, Eq)]
pub struct Summary {
    pub planned: usize,
    pub observed: usize,
    pub failed: usize,
    pub cancelled: usize,
    pub not_started: usize,
    pub reserved_bytes: u64,
    pub charged_bytes: u64,
    pub batches: usize,
}
impl Summary {
    pub fn state(&self) -> RunState {
        if self.cancelled > 0 || self.not_started > 0 { RunState::Cancelled }
        else if self.failed > 0 { RunState::WithFailures }
        else { RunState::Complete }
    }
}
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Diagnostic {
    pub status: Status,
    pub charged_bytes: u64,
}
pub struct Report {
    pub inventory: Inventory,
    pub diagnostics: BTreeMap<SourceKey, Diagnostic>,
    pub summary: Summary,
}
/// Admit the complete scope before any read, then process deterministic chunks.
/// A task failure does not suppress later items. Cancellation preserves every
/// admitted key, including unstarted items. Fatal batch errors return Err, never
/// a misleading complete report. The caller must provide stable, authorized
/// independent readers. The scope ceiling is still MAX_BATCH_TASKS; caller
/// handles, retained results and absolute RSS are not bounded by batch_size.
pub fn run<R: Read + Seek + Send>(mut tasks: Vec<Task<R>>, config: Config,
    cancel: Cancellation) -> Result<Report, RunError> {
    if config.batch_size == 0 || config.batch_size > MAX_BATCH_TASKS {
        return Err(RunError::InvalidBatchSize);
    }
    let reserved_bytes = parallel::preflight(&mut tasks, config.workers, config.byte_budget)
        .map_err(RunError::Analysis)?;
    let planned = tasks.len();
    let mut summary = Summary { planned, reserved_bytes, ..Summary::default() };
    let mut inventory = Inventory::new(planned, MAX_INDEX_PATH_BYTES);
    let mut diagnostics = BTreeMap::new();
    let mut remaining = reserved_bytes;
    let mut input = tasks.into_iter();
    loop {
        let chunk: Vec<_> = input.by_ref().take(config.batch_size).collect();
        if chunk.is_empty() { break; }
        let batch = parallel::run(chunk, config.workers, remaining, cancel.clone())
            .map_err(RunError::Analysis)?;
        remaining = remaining.checked_sub(batch.reserved_bytes).ok_or(RunError::Accounting)?;
        summary.batches += 1;
        for o in batch.outcomes {
            match o.status {
                Status::Observed => summary.observed += 1,
                Status::Failed(_) => summary.failed += 1,
                Status::Cancelled => summary.cancelled += 1,
                Status::NotStarted => summary.not_started += 1,
            }
            summary.charged_bytes = summary.charged_bytes.checked_add(o.charged_bytes)
                .ok_or(RunError::Accounting)?;
            let diagnostic = Diagnostic { status: o.status, charged_bytes: o.charged_bytes };
            inventory.insert(o.key.clone(), o.entry).map_err(RunError::Inventory)?;
            if diagnostics.insert(o.key, diagnostic).is_some() { return Err(RunError::Accounting); }
        }
    }
    if remaining != 0 || summary.charged_bytes > reserved_bytes || inventory.len() != planned
        || diagnostics.len() != planned
        || summary.observed + summary.failed + summary.cancelled + summary.not_started != planned {
        return Err(RunError::Accounting);
    }
    Ok(Report { inventory, diagnostics, summary })
}
