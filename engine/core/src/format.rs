//! Bounded magic-byte triage. A signature is a hint, not a validated file format.
use crate::ReadSession;
use std::io::{self, Read, Seek};

pub const PREFIX_LIMIT: usize = 512;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FormatHint {
    Unknown, Zip, DosMz, PortableExecutable, Elf, MachO, MachOFatOrJavaClass,
    Dex, Gzip, Zstd, SevenZip, Rar, OleCompound, Ar, Tar, Pdf, Png, Jpeg, Sqlite,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ProbeResult {
    pub hint: FormatHint,
    pub prefix_bytes: u64,
    /// Additional PE signature range, when actually examined.
    pub secondary_offset: Option<u64>,
}

/// Read only the bounded prefix and, for MZ, optionally four bytes at e_lfanew.
/// No decompression or interpretation of untrusted paths. ZIP does not imply APK,
/// JAR or MSIX; OLE does not imply MSI; Mach-O fat magic collides with Java class.
pub fn probe<R: Read + Seek>(s: &mut ReadSession<R>) -> io::Result<ProbeResult> {
    let n = s.len().min(PREFIX_LIMIT as u64) as usize;
    let prefix = s.read_window(0, n)?.bytes;
    let mut result = ProbeResult {
        hint: classify(&prefix),
        prefix_bytes: n as u64,
        secondary_offset: None,
    };
    if result.hint == FormatHint::DosMz && prefix.len() >= 64 {
        let offset = u32::from_le_bytes(prefix[60..64].try_into().unwrap()) as u64;
        if offset >= 64 && offset.checked_add(4).is_some_and(|end| end <= s.len()) {
            // Reuse bytes already read. Otherwise charge the actual second read.
            let signature = if offset + 4 <= n as u64 {
                prefix[offset as usize..offset as usize + 4].to_vec()
            } else {
                s.read_window(offset, 4)?.bytes
            };
            result.secondary_offset = Some(offset);
            if signature == b"PE\0\0" {
                result.hint = FormatHint::PortableExecutable;
            }
        }
    }
    Ok(result)
}

fn classify(p: &[u8]) -> FormatHint {
    use FormatHint::*;
    if p.starts_with(b"PK\x03\x04") || p.starts_with(b"PK\x05\x06") || p.starts_with(b"PK\x07\x08") { Zip }
    else if p.starts_with(b"MZ") { DosMz }
    else if p.starts_with(b"\x7fELF") { Elf }
    else if [b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe"].iter().any(|magic| p.starts_with(*magic)) { MachO }
    else if [b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca", b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca"].iter().any(|magic| p.starts_with(*magic)) { MachOFatOrJavaClass }
    else if p.len() >= 8 && p.starts_with(b"dex\n") && p[4..7].iter().all(u8::is_ascii_digit) && p[7] == 0 { Dex }
    else if p.starts_with(b"\x1f\x8b") { Gzip }
    else if p.starts_with(b"\x28\xb5\x2f\xfd") { Zstd }
    else if p.starts_with(b"7z\xbc\xaf\x27\x1c") { SevenZip }
    else if p.starts_with(b"Rar!\x1a\x07\x00") || p.starts_with(b"Rar!\x1a\x07\x01\x00") { Rar }
    else if p.starts_with(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1") { OleCompound }
    else if p.starts_with(b"!<arch>\n") { Ar }
    else if p.starts_with(b"%PDF-") { Pdf }
    else if p.starts_with(b"\x89PNG\r\n\x1a\n") { Png }
    else if p.starts_with(b"\xff\xd8\xff") { Jpeg }
    else if p.starts_with(b"SQLite format 3\0") { Sqlite }
    else if p.len() >= 512 && (&p[257..263] == b"ustar\0" || &p[257..263] == b"ustar ") { Tar }
    else { Unknown }
}
