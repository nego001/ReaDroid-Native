use negrodroid_core::{Cancellation, ReadSession, MAX_WINDOW_BYTES};
use std::io::{self, Cursor, Read, Seek, SeekFrom};

#[test]
fn reads_arbitrary_windows_without_mutating_input() {
    let input = [0, 1, 2, 3, 4, 5];
    let mut s = ReadSession::new(Cursor::new(&input), 6, 6, Cancellation::default());
    assert_eq!(s.read_window(4, 2).unwrap().bytes, [4, 5]);
    assert_eq!(s.read_window(0, 3).unwrap().bytes, [0, 1, 2]);
    assert_eq!(s.remaining_budget(), 1);
    assert_eq!(input, [0, 1, 2, 3, 4, 5]);
}

#[test]
fn rejects_bounds_overflow_and_window_limit_before_charging() {
    let mut s = ReadSession::new(Cursor::new([1u8]), 1, 10, Cancellation::default());
    assert!(s.read_window(0, MAX_WINDOW_BYTES + 1).is_err());
    assert!(s.read_window(u64::MAX, 1).is_err());
    assert!(s.read_window(1, 1).is_err());
    assert!(s.read_window(2, 0).is_err());
    assert_eq!(s.remaining_budget(), 10);
    assert!(s.read_window(1, 0).unwrap().bytes.is_empty());
}

#[test]
fn cumulative_budget_cannot_be_bypassed_by_repeating_ranges() {
    let mut s = ReadSession::new(Cursor::new([7u8; 4]), 4, 3, Cancellation::default());
    s.read_window(0, 2).unwrap();
    assert!(s.read_window(0, 2).is_err());
    assert_eq!(s.remaining_budget(), 1);
    s.read_window(0, 1).unwrap();
    assert_eq!(s.remaining_budget(), 0);
}

#[test]
fn cancellation_before_read_is_fail_closed() {
    let cancel = Cancellation::default();
    let mut s = ReadSession::new(Cursor::new([1u8; 2]), 2, 2, cancel.clone());
    cancel.cancel();
    assert_eq!(s.read_window(0, 1).unwrap_err().kind(), io::ErrorKind::Interrupted);
    assert_eq!(s.remaining_budget(), 2);
}

struct VirtualSource { position: u64, cancel: Option<Cancellation> }
impl Read for VirtualSource {
    fn read(&mut self, buf: &mut [u8]) -> io::Result<usize> {
        for b in buf.iter_mut() {
            *b = (self.position & 255) as u8;
            self.position += 1;
        }
        if let Some(c) = &self.cancel { c.cancel(); }
        Ok(buf.len())
    }
}
impl Seek for VirtualSource {
    fn seek(&mut self, pos: SeekFrom) -> io::Result<u64> {
        match pos {
            SeekFrom::Start(p) => { self.position = p; Ok(p) }
            _ => Err(io::Error::new(io::ErrorKind::Unsupported, "absolute seeks only")),
        }
    }
}

#[test]
fn offsets_above_four_gib_without_allocating_large_file() {
    let offset = (1u64 << 32) + 123;
    let mut s = ReadSession::new(VirtualSource { position: 0, cancel: None },
        offset + 3, 3, Cancellation::default());
    let window = s.read_window(offset, 3).unwrap();
    assert_eq!(window.offset, offset);
    assert_eq!(window.bytes, [123, 124, 125]);
}

#[test]
fn cancellation_during_read_never_returns_partial_success() {
    let cancel = Cancellation::default();
    let mut s = ReadSession::new(VirtualSource { position: 0, cancel: Some(cancel.clone()) },
        131072, 131072, cancel);
    assert_eq!(s.read_window(0, 131072).unwrap_err().kind(), io::ErrorKind::Interrupted);
    assert_eq!(s.remaining_budget(), 0);
}

#[test]
fn truncated_source_does_not_return_zero_filled_data() {
    let mut s = ReadSession::new(Cursor::new([1u8]), 3, 3, Cancellation::default());
    assert_eq!(s.read_window(0, 3).unwrap_err().kind(), io::ErrorKind::UnexpectedEof);
    assert_eq!(s.remaining_budget(), 0);
}

#[test]
fn real_file_handle_is_read_without_modification() {
    let path = std::env::temp_dir().join(format!("negrodroid-core-{}-fixture", std::process::id()));
    use std::io::Write;
    let mut fixture = std::fs::OpenOptions::new().write(true).create_new(true).open(&path).unwrap();
    fixture.write_all(b"0123456789").unwrap();
    drop(fixture);
    let mut s = ReadSession::from_file(std::fs::File::open(&path).unwrap(), 10, Cancellation::default()).unwrap();
    assert_eq!(s.len(), 10);
    assert_eq!(s.read_window(3, 4).unwrap().bytes, b"3456");
    drop(s);
    assert_eq!(std::fs::read(&path).unwrap(), b"0123456789");
    std::fs::remove_file(path).unwrap();
}
