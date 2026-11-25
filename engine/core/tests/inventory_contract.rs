use negrodroid_core::{Cancellation, ReadSession};
use negrodroid_core::evidence::observe_source;
use negrodroid_core::format::FormatHint;
use negrodroid_core::inventory::{Coverage, Entry, Inventory, IndexError, SourceKey, MAX_CONTAINER_DEPTH};
use std::io::Cursor;

fn pending() -> Entry {
    Entry { declared_length: None, format_hint: FormatHint::Unknown,
        coverage: Coverage::Unexamined, observation: None }
}
#[test]
fn physical_and_virtual_paths_are_distinct_structures() {
    let file = SourceKey::physical(1, "app.zip").unwrap();
    let nested = file.member("lib/nested.zip").unwrap().member("config.json").unwrap();
    assert_eq!(nested.relative_path(), "app.zip");
    assert_eq!(nested.members(), &["lib/nested.zip".to_owned(), "config.json".to_owned()]);
    assert_ne!(nested, SourceKey::physical(1, "app.zip!/lib/nested.zip!/config.json").unwrap());
}
#[test]
fn traversal_and_ambiguous_paths_rejected() {
    for p in ["", "/", "/etc/passwd", "../x", "a/../x", "a//b", "./x", "x/",
              "C:/x", "a\\b", "x\0y", "a\nb"] {
        assert_eq!(SourceKey::physical(1, p), Err(IndexError::InvalidPath));
        assert_eq!(SourceKey::physical(1, "root").unwrap().member(p), Err(IndexError::InvalidPath));
    }
    assert!(SourceKey::physical(1, "área/配置.json").is_ok());
}
#[test]
fn container_depth_bounded() {
    let mut k = SourceKey::physical(1, "outer.zip").unwrap();
    for _ in 0..MAX_CONTAINER_DEPTH { k = k.member("inner.zip").unwrap(); }
    assert_eq!(k.member("x"), Err(IndexError::DepthLimit));
}
#[test]
fn roots_do_not_alias_and_order_is_deterministic() {
    let mut i = Inventory::new(4, 100);
    for (r,p) in [(2,"a"),(1,"z"),(1,"a")] {
        i.insert(SourceKey::physical(r,p).unwrap(), pending()).unwrap();
    }
    let actual: Vec<_> = i.iter().map(|(k,_)| (k.root(),k.relative_path())).collect();
    assert_eq!(actual, [(1,"a"),(1,"z"),(2,"a")]);
}
#[test]
fn duplicate_cannot_overwrite_previous_evidence() {
    let k = SourceKey::physical(1,"x").unwrap();
    let mut i = Inventory::new(3,100);
    i.insert(k.clone(),pending()).unwrap();
    let mut changed = pending(); changed.coverage = Coverage::Failed;
    assert_eq!(i.insert(k.clone(),changed),Err(IndexError::Duplicate));
    assert_eq!(i.get(&k).unwrap().coverage,Coverage::Unexamined);
    assert_eq!(i.path_bytes(),1);
}
#[test]
fn count_and_byte_budget_fail_without_mutation() {
    let mut i = Inventory::new(2,3);
    i.insert(SourceKey::physical(1,"a").unwrap(),pending()).unwrap();
    assert_eq!(i.insert(SourceKey::physical(1,"abc").unwrap(),pending()),Err(IndexError::PathBudget));
    i.insert(SourceKey::physical(1,"bc").unwrap(),pending()).unwrap();
    assert_eq!(i.insert(SourceKey::physical(1,"d").unwrap(),pending()),Err(IndexError::EntryLimit));
    assert_eq!(i.len(),2);
    assert_eq!(i.path_bytes(),3);
}
#[test]
fn observation_requires_matching_declared_length_and_coverage() {
    let mut s = ReadSession::new(Cursor::new(b"abc"),3,3,Cancellation::default());
    let o = observe_source(&mut s).unwrap();
    let mut i = Inventory::new(3,100);
    let k = SourceKey::physical(1,"a").unwrap();
    let mut e = Entry { declared_length:Some(2),format_hint:FormatHint::Unknown,
        coverage:Coverage::Observed,observation:Some(o) };
    assert_eq!(i.insert(k.clone(),e.clone()),Err(IndexError::InconsistentObservation));
    e.declared_length = Some(3); e.coverage = Coverage::Partial;
    assert_eq!(i.insert(k.clone(),e.clone()),Err(IndexError::InconsistentObservation));
    e.coverage = Coverage::Observed;
    i.insert(k.clone(),e).unwrap();
    assert_eq!(i.get(&k).unwrap().observation,Some(o));
}
#[test]
fn missing_hash_cannot_be_marked_observed() {
    let mut i = Inventory::new(1,10);
    let mut e = pending(); e.coverage = Coverage::Observed;
    assert_eq!(i.insert(SourceKey::physical(1,"a").unwrap(),e),Err(IndexError::InconsistentObservation));
    assert!(i.is_empty());
}
