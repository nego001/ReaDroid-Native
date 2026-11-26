#![forbid(unsafe_code)]
//! Universal read-only byte source foundation. No format parser or JNI yet.
pub mod evidence;
pub mod format;
pub mod inventory;
pub mod parallel;
pub mod orchestration;
pub mod reporting;
pub mod capabilities;
pub mod structural;
pub mod discovery;
pub mod context;
pub mod classification;
pub mod segmentation;
pub mod context_budget;
pub mod context_guard;
pub mod context_export;
pub mod hex;
pub mod binary_pages;
pub mod binary_search;
pub mod text_encoding;
pub mod data_inspector;
pub mod binary_comparison;
pub mod virtual_overlay;
pub mod edit_history;
pub mod pe_structure;
pub mod elf_structure;
pub mod dex_structure;
pub mod elf_symbols;
pub mod pe_symbols;
pub mod dex_identifiers;
pub mod aarch64_decode;

use std::fs::File;
use std::io::{self, Read, Seek, SeekFrom};
use std::sync::{Arc, atomic::{AtomicBool, Ordering}};

pub const MAX_WINDOW_BYTES: usize = 1024 * 1024;
const IO_CHUNK: usize = 64 * 1024;

#[derive(Clone, Default)]
pub struct Cancellation(Arc<AtomicBool>);
impl Cancellation {
    pub fn cancel(&self) { self.0.store(true, Ordering::Release); }
    pub fn is_cancelled(&self) -> bool { self.0.load(Ordering::Acquire) }
    fn check(&self) -> io::Result<()> {
        if self.is_cancelled() {
            Err(io::Error::new(io::ErrorKind::Interrupted, "session cancelled"))
        } else { Ok(()) }
    }
}

/// Explicit byte range relative to the source; not a filesystem address.
#[derive(Debug, PartialEq, Eq)]
pub struct Window {
    pub offset: u64,
    pub bytes: Vec<u8>,
}

/// One sequential reader and one cumulative I/O budget. No shared cursor
/// between workers. An unsuccessful admitted read consumes its reservation.
/// This budget does not claim to limit total memory retained by callers.
pub struct ReadSession<R: Read + Seek> {
    reader: R,
    length: u64,
    remaining: u64,
    cancellation: Cancellation,
}

impl<R: Read + Seek> ReadSession<R> {
    /// The caller owns the input handle and supplies its known length.
    /// Sources must remain stable while being read; this is not a snapshot.
    pub fn new(reader: R, length: u64, budget: u64, cancellation: Cancellation) -> Self {
        Self { reader, length, remaining: budget, cancellation }
    }

    pub fn len(&self) -> u64 { self.length }
    pub fn is_empty(&self) -> bool { self.length == 0 }
    pub fn remaining_budget(&self) -> u64 { self.remaining }

    pub fn read_window(&mut self, offset: u64, size: usize) -> io::Result<Window> {
        self.cancellation.check()?;
        if size > MAX_WINDOW_BYTES {
            return Err(io::Error::new(io::ErrorKind::InvalidInput, "window exceeds 1 MiB"));
        }
        let size64 = size as u64;
        let end = offset.checked_add(size64)
            .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "range overflow"))?;
        if end > self.length {
            return Err(io::Error::new(io::ErrorKind::UnexpectedEof, "range outside source"));
        }
        if size64 > self.remaining {
            return Err(io::Error::new(io::ErrorKind::Other, "read budget exhausted"));
        }
        self.remaining -= size64;
        if size == 0 { return Ok(Window { offset, bytes: Vec::new() }); }
        self.reader.seek(SeekFrom::Start(offset))?;
        let mut bytes = vec![0; size];
        let mut filled = 0;
        while filled < size {
            self.cancellation.check()?;
            let end = (filled + IO_CHUNK).min(size);
            let n = self.reader.read(&mut bytes[filled..end])?;
            if n == 0 {
                return Err(io::Error::new(io::ErrorKind::UnexpectedEof, "source truncated"));
            }
            filled += n;
        }
        self.cancellation.check()?;
        Ok(Window { offset, bytes })
    }
}

impl ReadSession<File> {
    /// Accept an already opened, authorized file handle; no path traversal,
    /// directory scanning or write API. Regular files only.
    pub fn from_file(file: File, budget: u64, cancellation: Cancellation) -> io::Result<Self> {
        let metadata = file.metadata()?;
        if !metadata.is_file() {
            return Err(io::Error::new(io::ErrorKind::InvalidInput, "not a regular file"));
        }
        Ok(Self::new(file, metadata.len(), budget, cancellation))
    }
}
