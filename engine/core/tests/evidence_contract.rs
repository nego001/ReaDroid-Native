use negrodroid_core::{Cancellation, ReadSession, MAX_WINDOW_BYTES};
use negrodroid_core::evidence::{observe_source, observe_range};
use std::io::{self, Cursor, Read, Seek, SeekFrom};

#[test]
fn standard_sha256_vectors() {
    for (data, expected) in [
        (&b""[..], "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
        (&b"abc"[..], "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"),
    ] {
        let mut s = ReadSession::new(Cursor::new(data), data.len() as u64,
            data.len() as u64, Cancellation::default());
        let result = observe_source(&mut s).unwrap();
        assert_eq!(result.length, data.len() as u64);
        assert_eq!(result.sha256.to_hex(), expected);
        assert_eq!(s.remaining_budget(), 0);
    }
}

#[test]
fn full_hash_streams_across_windows() {
    let data = vec![b'a'; 1_000_000];
    // NIST's million-'a' vector, tested separately from boundary crossing.
    let mut s = ReadSession::new(Cursor::new(&data), data.len() as u64,
        data.len() as u64, Cancellation::default());
    assert_eq!(observe_source(&mut s).unwrap().sha256.to_hex(),
        "cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0");
    let large = vec![7u8; MAX_WINDOW_BYTES + 37];
    let len = large.len() as u64;
    let mut s = ReadSession::new(Cursor::new(&large), len, len, Cancellation::default());
    let actual = observe_source(&mut s).unwrap();
    use sha2::{Digest, Sha256};
    assert_eq!(actual.sha256.bytes().as_slice(), Sha256::digest(&large).as_slice());
    assert_eq!(s.remaining_budget(), 0);
}

#[test]
fn range_has_exact_offset_and_digest() {
    let mut s = ReadSession::new(Cursor::new(b"xxabcyy"), 7, 3, Cancellation::default());
    let result = observe_range(&mut s, 2, 3).unwrap();
    assert_eq!(result.offset, 2);
    assert_eq!(result.length, 3);
    assert_eq!(result.sha256.to_hex(),
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
    assert_eq!(s.remaining_budget(), 0);
}

#[test]
fn budget_failure_does_not_consume_partial_full_hash() {
    let mut s = ReadSession::new(Cursor::new(b"abc"), 3, 2, Cancellation::default());
    assert!(observe_source(&mut s).is_err());
    assert_eq!(s.remaining_budget(), 2);
}

#[test]
fn truncation_and_cancelled_empty_input_are_not_success() {
    let mut s = ReadSession::new(Cursor::new(b"a"), 3, 3, Cancellation::default());
    assert_eq!(observe_source(&mut s).unwrap_err().kind(), io::ErrorKind::UnexpectedEof);
    let cancel = Cancellation::default();
    let mut s = ReadSession::new(Cursor::new(b""), 0, 0, cancel.clone());
    cancel.cancel();
    assert_eq!(observe_source(&mut s).unwrap_err().kind(), io::ErrorKind::Interrupted);
}

struct CancelOnRead { flag: Cancellation }
impl Read for CancelOnRead {
    fn read(&mut self, b: &mut [u8]) -> io::Result<usize> {
        b.fill(1);
        self.flag.cancel();
        Ok(b.len())
    }
}
impl Seek for CancelOnRead {
    fn seek(&mut self, p: SeekFrom) -> io::Result<u64> {
        match p {
            SeekFrom::Start(offset) => Ok(offset),
            _ => Err(io::Error::new(io::ErrorKind::Unsupported, "absolute only")),
        }
    }
}

#[test]
fn cancellation_during_hash_never_yields_digest() {
    let flag = Cancellation::default();
    let length = MAX_WINDOW_BYTES as u64 + 1;
    let mut s = ReadSession::new(CancelOnRead { flag: flag.clone() }, length, length, flag);
    assert_eq!(observe_source(&mut s).unwrap_err().kind(), io::ErrorKind::Interrupted);
    assert_eq!(s.remaining_budget(), 1);
}

#[test]
fn distinct_contents_have_distinct_observations() {
    let mut first = ReadSession::new(Cursor::new(b"abc"), 3, 3, Cancellation::default());
    let mut second = ReadSession::new(Cursor::new(b"abd"), 3, 3, Cancellation::default());
    assert_ne!(observe_source(&mut first).unwrap(), observe_source(&mut second).unwrap());
}
