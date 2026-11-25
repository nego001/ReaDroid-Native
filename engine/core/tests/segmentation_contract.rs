use negrodroid_core::{Cancellation,segmentation::{segment_report,Config,MAX_SEGMENT_ITEMS},
    classification::{Family,Coverage,StructuralScope},context::{Error,MAX_CONTEXT_ITEMS},
    inventory::SourceKey,orchestration::{run,run_with_headers,Config as RunConfig,Report,RunState},parallel::Task};
use std::io::Cursor;
fn task(name:&str,b:&[u8],length:u64)->Task<Cursor<Vec<u8>>>{
    Task{key:SourceKey::physical(1,name).unwrap(),reader:Cursor::new(b.to_vec()),length}
}
fn run_cfg()->RunConfig{RunConfig{workers:2,batch_size:16,byte_budget:u64::MAX}}
fn cfg(page_items:usize,segment_items:usize)->Config{Config{page_items,segment_items}}
fn uniform(n:usize)->Report{
    run((0..n).rev().map(|i|task(&format!("private/{i:04}"),b"x",1)).collect(),run_cfg(),Cancellation::default()).unwrap()
}
#[test]
fn splits_homogeneous_groups_at_configured_size(){
    let r=uniform(7);let c=Cancellation::default();
    let p=segment_report(&r,None,cfg(8,3),&c).unwrap();
    assert_eq!(p.segments.iter().map(|s|s.items.len()).collect::<Vec<_>>(),vec![3,3,1]);
    assert_eq!(p.segments.iter().flat_map(|s|s.items.iter().map(|e|e.ordinal)).collect::<Vec<_>>(),(1..=7).collect::<Vec<_>>());
    assert_eq!(p.included,7);assert_eq!(p.counts.observed,7);assert_eq!(p.next,None);
}
#[test]
fn mixed_groups_preserve_original_order_and_scope(){
    let c=Cancellation::default();
    let r=run_with_headers(vec![task("d",b"x",1),task("a",b"x",1),task("c",b"",1),
        task("b",b"\x89PNG\r\n\x1a\n",8)],run_cfg(),c.clone()).unwrap();
    let p=segment_report(&r,None,cfg(8,8),&c).unwrap();
    assert_eq!(p.segments.len(),4);
    assert_eq!(p.segments[0].group.family,Family::Unknown);
    assert_eq!(p.segments[1].group.family,Family::ImageFamily);
    assert_eq!(p.segments[1].group.structure,StructuralScope::MalformedSubset);
    assert_eq!(p.segments[1].group.coverage,Coverage::DeclaredBytesObserved);
    assert_eq!(p.segments[2].group.coverage,Coverage::ReadFailed);
    assert_eq!(p.segments[3].group,p.segments[0].group);
    assert_eq!(p.state,RunState::WithFailures);
    assert_eq!(p.counts.observed,3);assert_eq!(p.counts.failed,1);
}
#[test]
fn cursor_traversal_no_gaps_no_duplicates_with_page_splits(){
    let r=uniform(259);let c=Cancellation::default();
    let mut after=None;let mut all=Vec::new();let mut pages=0;
    loop{
        let p=segment_report(&r,after,cfg(MAX_CONTEXT_ITEMS,MAX_SEGMENT_ITEMS),&c).unwrap();
        assert_eq!(p.after,after);assert_eq!(p.summary,r.summary);
        assert!(p.segments.iter().all(|s|!s.items.is_empty()&&s.items.len()<=MAX_SEGMENT_ITEMS));
        assert_eq!(p.included,p.segments.iter().map(|s|s.items.len()).sum::<usize>());
        all.extend(p.segments.iter().flat_map(|s|s.items.iter().map(|e|e.ordinal)));
        pages+=1;
        match p.next{Some(n)=>after=Some(n),None=>break}
        assert!(pages<4);
    }
    assert_eq!(all,(1..=259).collect::<Vec<_>>());assert_eq!(pages,3);
}
#[test]
fn deterministic_and_privacy_preserved(){
    let r=uniform(3);let c=Cancellation::default();
    let a=segment_report(&r,None,cfg(3,2),&c).unwrap();
    assert_eq!(a,segment_report(&r,None,cfg(3,2),&c).unwrap());
    let text=format!("{a:?}");
    assert!(!text.contains("private/"));
    let hash=r.inventory.iter().next().unwrap().1.observation.unwrap().sha256.to_hex();
    assert!(!text.contains(&hash));
}
#[test]
fn limits_and_invalid_cursor_rejected(){
    let r=uniform(3);let c=Cancellation::default();
    for config in [cfg(0,1),cfg(MAX_CONTEXT_ITEMS+1,1),cfg(1,0),cfg(1,MAX_SEGMENT_ITEMS+1)]{
        assert_eq!(segment_report(&r,None,config,&c),Err(Error::InvalidPage));
    }
    assert_eq!(segment_report(&r,Some(4),cfg(1,1),&c),Err(Error::InvalidPage));
}
#[test]
fn empty_and_exact_terminal_cursor(){
    let r=uniform(0);let c=Cancellation::default();
    let p=segment_report(&r,None,cfg(1,1),&c).unwrap();
    assert!(p.segments.is_empty());assert_eq!(p.included,0);assert_eq!(p.next,None);
    let r=uniform(1);let p=segment_report(&r,Some(1),cfg(1,1),&c).unwrap();
    assert!(p.segments.is_empty());assert_eq!(p.summary.planned,1);
    assert_eq!(p.next,None);
}
#[test]
fn inconsistent_report_and_cancelled_projection_rejected(){
    let mut r=uniform(1);let c=Cancellation::default();r.summary.observed=0;
    assert_eq!(segment_report(&r,None,cfg(1,1),&c),Err(Error::InconsistentReport));
    c.cancel();assert_eq!(segment_report(&r,None,cfg(1,1),&c),Err(Error::Cancelled));
}
#[test]
fn not_started_evidence_keeps_exact_size(){
    let c=Cancellation::default();c.cancel();
    let n=9_007_199_254_740_993;
    let r=run_with_headers(vec![task("x",b"",n)],run_cfg(),c).unwrap();
    let p=segment_report(&r,None,cfg(1,1),&Cancellation::default()).unwrap();
    assert_eq!(p.segments[0].group.coverage,Coverage::NotStarted);
    assert_eq!(p.segments[0].group.structure,StructuralScope::Unavailable);
    assert_eq!(p.segments[0].items[0].declared_length,n);
    assert_eq!(p.state,RunState::Cancelled);
}
