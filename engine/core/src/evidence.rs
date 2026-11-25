//! Cryptographic observations of bytes read, not proof of immutable storage.
use crate::{ReadSession, MAX_WINDOW_BYTES};
use sha2::{Digest, Sha256};
use std::io::{self, Read, Seek};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct Digest256([u8; 32]);

impl Digest256 {
    pub fn bytes(&self) -> &[u8; 32] { &self.0 }

    pub fn to_hex(self) -> String {
        const HEX: &[u8; 16] = b"0123456789abcdef";
        let mut text = String::with_capacity(64);
        for b in self.0 {
            text.push(HEX[(b >> 4) as usize] as char);
            text.push(HEX[(b & 15) as usize] as char);
        }
        text
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct SourceObservation {
    pub length: u64,
    pub sha256: Digest256,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct RangeObservation {
    /// Relative to the selected source, not a host filesystem address.
    pub offset: u64,
    pub length: u64,
    pub sha256: Digest256,
}

/// Hash exactly the declared source length with bounded windows and the
/// session's existing cumulative budget. The caller must provide a stable
/// source; concurrent modification or undeclared trailing bytes are not
/// ruled out. No digest is returned on cancellation or incomplete reads.
pub fn observe_source<R: Read + Seek>(session: &mut ReadSession<R>) -> io::Result<SourceObservation> {
    session.cancellation.check()?;
    let length = session.len();
    if length > session.remaining_budget() {
        return Err(io::Error::new(io::ErrorKind::Other, "insufficient budget for full source hash"));
    }
    let mut digest = Sha256::new();
    let mut offset = 0u64;
    while offset < length {
        let size = (length - offset).min(MAX_WINDOW_BYTES as u64) as usize;
        let window = session.read_window(offset, size)?;
        digest.update(&window.bytes);
        offset += size as u64;
    }
    session.cancellation.check()?;
    Ok(SourceObservation { length, sha256: Digest256(digest.finalize().into()) })
}

/// Hash one observed range. A matching range digest does not establish
/// membership in a previously observed source without a stable snapshot.
pub fn observe_range<R: Read + Seek>(
    session: &mut ReadSession<R>, offset: u64, size: usize,
) -> io::Result<RangeObservation> {
    let window = session.read_window(offset, size)?;
    let digest = Sha256::digest(&window.bytes);
    session.cancellation.check()?;
    Ok(RangeObservation {
        offset: window.offset,
        length: window.bytes.len() as u64,
        sha256: Digest256(digest.into()),
    })
}
