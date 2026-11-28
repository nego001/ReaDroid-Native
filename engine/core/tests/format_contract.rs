use negrodroid_core::{Cancellation, ReadSession};
use negrodroid_core::format::{probe, FormatHint, PREFIX_LIMIT};
use std::io::Cursor;

fn hint(data: &[u8]) -> FormatHint {
    let n = data.len() as u64;
    let mut s = ReadSession::new(Cursor::new(data), n, n, Cancellation::default());
    probe(&mut s).unwrap().hint
}

#[test]
fn known_magic_families_are_only_hints() {
    use FormatHint::*;
    let cases: &[(&[u8], FormatHint)] = &[
        (b"PK\x03\x04", Zip), (b"PK\x05\x06", Zip),
        (b"\x7fELF", Elf), (b"MZ", DosMz),
        (b"\xcf\xfa\xed\xfe", MachO), (b"\xca\xfe\xba\xbe", MachOFatOrJavaClass),
        (b"dex\n035\0", Dex), (b"\x1f\x8b", Gzip),
        (b"\x28\xb5\x2f\xfd", Zstd), (b"7z\xbc\xaf\x27\x1c", SevenZip),
        (b"Rar!\x1a\x07\x00", Rar), (b"Rar!\x1a\x07\x01\x00", Rar),
        (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", OleCompound),
        (b"!<arch>\n", Ar), (b"%PDF-", Pdf),
        (b"\x89PNG\r\n\x1a\n", Png), (b"\xff\xd8\xff", Jpeg),
        (b"SQLite format 3\0", Sqlite),
    ];
    for &(bytes, expected) in cases { assert_eq!(hint(bytes), expected); }
}

#[test]
fn empty_short_and_extension_only_data_are_unknown() {
    for bytes in [&b""[..], &b"PK"[..], &b"program.exe"[..], &b"dex\nabc\0"[..]] {
        assert_eq!(hint(bytes), FormatHint::Unknown);
    }
}

fn pe(offset: usize, size: usize) -> Vec<u8> {
    let mut b = vec![0; size];
    b[..2].copy_from_slice(b"MZ");
    b[60..64].copy_from_slice(&(offset as u32).to_le_bytes());
    if offset >= 64 && offset.checked_add(4).is_some_and(|end| end <= size) { b[offset..offset+4].copy_from_slice(b"PE\0\0"); }
    b
}

#[test]
fn pe_signature_inside_prefix_costs_no_extra_read() {
    let b = pe(128, 1024);
    let mut s = ReadSession::new(Cursor::new(b), 1024, 512, Cancellation::default());
    let r = probe(&mut s).unwrap();
    assert_eq!(r.hint, FormatHint::PortableExecutable);
    assert_eq!(r.secondary_offset, Some(128));
    assert_eq!(s.remaining_budget(), 0);
}

#[test]
fn pe_signature_outside_prefix_costs_four_bytes() {
    let b = pe(768, 1024);
    let mut s = ReadSession::new(Cursor::new(b), 1024, 516, Cancellation::default());
    let r = probe(&mut s).unwrap();
    assert_eq!(r.hint, FormatHint::PortableExecutable);
    assert_eq!(r.secondary_offset, Some(768));
    assert_eq!(s.remaining_budget(), 0);
}

#[test]
fn malformed_pe_pointer_does_not_escape_bounds() {
    for offset in [0, 63, 1023, u32::MAX as usize] {
        assert_eq!(hint(&pe(offset, 1024)), FormatHint::DosMz);
    }
}

#[test]
fn wrong_pe_signature_remains_mz() {
    let mut b = pe(128, 1024);
    b[128] = b'X';
    assert_eq!(hint(&b), FormatHint::DosMz);
}

#[test]
fn pe_secondary_read_respects_budget() {
    let mut s = ReadSession::new(Cursor::new(pe(768, 1024)), 1024, 512, Cancellation::default());
    assert!(probe(&mut s).is_err());
    assert_eq!(s.remaining_budget(), 0);
}

#[test]
fn tar_marker_requires_full_header() {
    let mut b = [0; 512];
    b[257..263].copy_from_slice(b"ustar\0");
    assert_eq!(hint(&b), FormatHint::Tar);
    assert_eq!(hint(&b[..300]), FormatHint::Unknown);
}

#[test]
fn unknown_large_input_reads_only_prefix() {
    let b = vec![0; 8192];
    let mut s = ReadSession::new(Cursor::new(b), 8192, PREFIX_LIMIT as u64, Cancellation::default());
    let r = probe(&mut s).unwrap();
    assert_eq!(r.hint, FormatHint::Unknown);
    assert_eq!(r.prefix_bytes, PREFIX_LIMIT as u64);
    assert_eq!(s.remaining_budget(), 0);
}

#[test]
fn cancelled_or_truncated_input_is_error() {
    let c = Cancellation::default();
    c.cancel();
    let mut s = ReadSession::new(Cursor::new(b"MZ"), 2, 2, c);
    assert!(probe(&mut s).is_err());
    let mut s = ReadSession::new(Cursor::new(b"MZ"), 512, 512, Cancellation::default());
    assert!(probe(&mut s).is_err());
}
