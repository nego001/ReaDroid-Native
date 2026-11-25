//! In-memory, bounded inventory contract. Paths are logical source identifiers,
//! never authority to open or extract files. No disk crawling or persistence yet.
use crate::evidence::SourceObservation;
use crate::format::FormatHint;
use std::collections::BTreeMap;

pub const MAX_PATH_BYTES: usize = 4096;
pub const MAX_CONTAINER_DEPTH: usize = 8;
pub const MAX_INDEX_ENTRIES: usize = 100_000;
pub const MAX_INDEX_PATH_BYTES: usize = 32 * 1024 * 1024;

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
pub struct SourceKey {
    // Root is an opaque, locally assigned scope ID, not an absolute path.
    root: u64,
    relative_path: String,
    members: Vec<String>,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum IndexError { InvalidPath, DepthLimit, Duplicate, EntryLimit, PathBudget, InconsistentObservation }

fn check_path(path: &str) -> Result<(), IndexError> {
    if path.is_empty() || path.len() > MAX_PATH_BYTES ||
        path.contains('\\') || path.contains(':') ||
        path.chars().any(char::is_control) ||
        path.split('/').any(|s| s.is_empty() || s == "." || s == "..") {
        return Err(IndexError::InvalidPath);
    }
    Ok(())
}
impl SourceKey {
    pub fn physical(root: u64, relative_path: &str) -> Result<Self, IndexError> {
        check_path(relative_path)?;
        Ok(Self { root, relative_path: relative_path.to_owned(), members: Vec::new() })
    }
    pub fn member(&self, path: &str) -> Result<Self, IndexError> {
        if self.members.len() >= MAX_CONTAINER_DEPTH { return Err(IndexError::DepthLimit); }
        check_path(path)?;
        let mut next = self.clone();
        next.members.push(path.to_owned());
        Ok(next)
    }
    pub fn root(&self) -> u64 { self.root }
    pub fn relative_path(&self) -> &str { &self.relative_path }
    pub fn members(&self) -> &[String] { &self.members }
    fn path_bytes(&self) -> usize {
        self.relative_path.len() + self.members.iter().map(String::len).sum::<usize>()
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Coverage {
    Unexamined, Partial, Observed, Unsupported, Failed, Cancelled,
}
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Entry {
    pub declared_length: Option<u64>,
    pub format_hint: FormatHint,
    pub coverage: Coverage,
    pub observation: Option<SourceObservation>,
}
impl Entry {
    fn validate(&self) -> Result<(), IndexError> {
        match (self.coverage, self.observation) {
            (Coverage::Observed, Some(o)) if self.declared_length == Some(o.length) => Ok(()),
            (Coverage::Observed, _) | (_, Some(_)) => Err(IndexError::InconsistentObservation),
            _ => Ok(()),
        }
    }
}

pub struct Inventory {
    entries: BTreeMap<SourceKey, Entry>,
    entry_limit: usize,
    path_limit: usize,
    path_bytes: usize,
}
impl Inventory {
    pub fn new(entry_limit: usize, path_limit: usize) -> Self {
        Self {
            entries: BTreeMap::new(),
            entry_limit: entry_limit.min(MAX_INDEX_ENTRIES),
            path_limit: path_limit.min(MAX_INDEX_PATH_BYTES),
            path_bytes: 0,
        }
    }
    pub fn insert(&mut self, key: SourceKey, entry: Entry) -> Result<(), IndexError> {
        entry.validate()?;
        if self.entries.contains_key(&key) { return Err(IndexError::Duplicate); }
        if self.entries.len() >= self.entry_limit { return Err(IndexError::EntryLimit); }
        let bytes = key.path_bytes();
        if bytes > self.path_limit - self.path_bytes { return Err(IndexError::PathBudget); }
        self.entries.insert(key, entry);
        self.path_bytes += bytes;
        Ok(())
    }
    pub fn len(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self) -> bool { self.entries.is_empty() }
    pub fn path_bytes(&self) -> usize { self.path_bytes }
    pub fn get(&self, key: &SourceKey) -> Option<&Entry> { self.entries.get(key) }
    pub fn iter(&self) -> impl Iterator<Item = (&SourceKey, &Entry)> { self.entries.iter() }
}
