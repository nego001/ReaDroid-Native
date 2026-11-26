use negrodroid_core::{Cancellation,ReadSession,edit_history::{History,Limits,MAX_HISTORY_ENTRIES,MAX_HISTORY_PAYLOAD}};
use std::io::{self,Cursor};
fn history(b:&[u8],budget:u64,cap:usize,entries:usize,payload_bytes:usize)->History<Cursor<&[u8]>>{
    History::new(ReadSession::new(Cursor::new(b),b.len() as u64,budget,Cancellation::default()),cap,Limits{entries,payload_bytes}).unwrap()
}
#[test]
fn overlapping_edits_undo_redo_monotonic_revisions(){
    let original=*b"ABCD";
    let mut h=history(&original,50,4,4,32);
    h.replace(0,1,b"BC",b"xy").unwrap();
    h.replace(1,2,b"yD",b"zw").unwrap();
    assert_eq!(h.read_window(0,4).unwrap().bytes,b"Axzw");
    let s=h.undo(2).unwrap();assert_eq!((s.revision,s.undo_count,s.redo_count),(3,1,1));
    assert_eq!(h.read_window(0,4).unwrap().bytes,b"AxyD");
    h.undo(3).unwrap();assert_eq!(h.read_window(0,4).unwrap().bytes,b"ABCD");
    h.redo(4).unwrap();h.redo(5).unwrap();
    assert_eq!(h.read_window(0,4).unwrap().bytes,b"Axzw");
    assert_eq!(h.state().revision,6);assert_eq!(&original,b"ABCD");
}
#[test]
fn successful_branch_discards_redo_only_after_commit(){
    let mut h=history(b"ABC",30,3,3,12);
    h.replace(0,0,b"A",b"x").unwrap();h.replace(1,1,b"B",b"y").unwrap();
    h.undo(2).unwrap();let before=h.state();
    assert!(h.replace(3,2,b"Z",b"w").is_err());assert_eq!(h.state(),before);
    h.replace(3,2,b"C",b"z").unwrap();
    assert_eq!((h.state().undo_count,h.state().redo_count,h.state().history_payload),(2,0,4));
    assert!(h.redo(4).is_err());assert_eq!(h.read_window(0,3).unwrap().bytes,b"xBz");
}
#[test]
fn noop_preserves_redo_and_revision(){
    let mut h=history(b"AB",20,2,1,2);
    h.replace(0,0,b"A",b"x").unwrap();h.undo(1).unwrap();let before=h.state();
    assert_eq!(h.replace(2,0,b"A",b"A").unwrap(),before);
    assert!(h.replace(2,0,b"Z",b"Z").is_err());assert_eq!(h.state(),before);
    h.redo(2).unwrap();assert_eq!(h.read_window(0,2).unwrap().bytes,b"xB");
}
#[test]
fn capacity_rejection_and_branch_reuse(){
    let mut h=history(b"ABC",30,3,2,4);
    h.replace(0,0,b"A",b"x").unwrap();h.replace(1,1,b"B",b"y").unwrap();
    let before=h.state();let budget=h.remaining_budget();
    assert!(h.replace(2,2,b"C",b"z").is_err());
    assert_eq!(h.state(),before);assert_eq!(h.remaining_budget(),budget);
    h.undo(2).unwrap();h.replace(3,2,b"C",b"z").unwrap();
    assert_eq!(h.state().history_payload,4);assert_eq!(h.state().redo_count,0);
}
#[test]
fn payload_limit_independent_of_entries(){
    let mut h=history(b"ABC",30,3,8,4);
    h.replace(0,0,b"AB",b"xy").unwrap();let s=h.state();
    assert!(h.replace(1,2,b"C",b"z").is_err());assert_eq!(h.state(),s);
    h.undo(1).unwrap();h.replace(2,2,b"C",b"z").unwrap();
    assert_eq!(h.state().history_payload,2);
}
#[test]
fn stale_revision_and_empty_history_reject_without_reads(){
    let mut h=history(b"ABC",10,3,2,8);
    assert!(h.undo(0).is_err());assert!(h.redo(0).is_err());
    h.replace(0,0,b"A",b"x").unwrap();let s=h.state();let b=h.remaining_budget();
    assert!(h.undo(0).is_err());assert!(h.redo(0).is_err());
    assert!(h.replace(0,1,b"B",b"z").is_err());
    assert_eq!(h.state(),s);assert_eq!(h.remaining_budget(),b);
}
#[test]
fn failed_undo_budget_preserves_journal(){
    let mut h=history(b"AB",2,2,2,8);
    h.replace(0,0,b"AB",b"xy").unwrap();let s=h.state();
    assert!(h.undo(1).is_err());assert_eq!(h.state(),s);
}
#[test]
fn cancelled_redo_preserves_journal(){
    let c=Cancellation::default();
    let mut h=History::new(ReadSession::new(Cursor::new(b"AB"),2,10,c.clone()),2,Limits{entries:4,payload_bytes:16}).unwrap();
    h.replace(0,0,b"A",b"x").unwrap();h.undo(1).unwrap();let s=h.state();
    c.cancel();
    assert_eq!(h.redo(2).unwrap_err().kind(),io::ErrorKind::Interrupted);
    assert_eq!(h.state(),s);
}
#[test]
fn failed_overlay_capacity_preserves_history(){
    let mut h=history(b"AB",20,1,4,16);
    h.replace(0,0,b"A",b"x").unwrap();let s=h.state();
    assert!(h.replace(1,1,b"B",b"y").is_err());assert_eq!(h.state(),s);
    assert_eq!(h.read_window(0,2).unwrap().bytes,b"xB");
}
#[test]
fn invalid_configuration_and_exhaustive_two_edit_oracle(){
    for limits in [Limits{entries:0,payload_bytes:2},Limits{entries:MAX_HISTORY_ENTRIES+1,payload_bytes:2},Limits{entries:1,payload_bytes:1},Limits{entries:1,payload_bytes:MAX_HISTORY_PAYLOAD+1}]{
        assert!(History::new(ReadSession::new(Cursor::new(b"A"),1,1,Cancellation::default()),1,limits).is_err());
    }
    for a in 0..4u8{for b in 0..4u8{for c in 0..4u8{
        let base=[a];let mut h=history(&base,16,1,4,16);
        h.replace(0,0,&[a],&[b]).unwrap();
        let s=h.state();h.replace(s.revision,0,&[b],&[c]).unwrap();
        assert_eq!(h.read_window(0,1).unwrap().bytes,[c]);
        while h.state().undo_count>0{let r=h.state().revision;h.undo(r).unwrap();}
        assert_eq!(h.read_window(0,1).unwrap().bytes,[a]);
        while h.state().redo_count>0{let r=h.state().revision;h.redo(r).unwrap();}
        assert_eq!(h.read_window(0,1).unwrap().bytes,[c]);
    }}}
}
