use negrodroid_core::{Cancellation,context::{project,Error,Observation,HeaderEvidence,MAX_CONTEXT_ITEMS},
    inventory::SourceKey,orchestration::{run,run_with_headers,Config,RunState,Report},parallel::Task,
    structural::Issue,format::FormatHint};
use std::io::Cursor;
fn task(name:&str,bytes:&[u8],length:u64)->Task<Cursor<Vec<u8>>>{
    Task{key:SourceKey::physical(1,name).unwrap(),reader:Cursor::new(bytes.to_vec()),length}
}
fn cfg()->Config{Config{workers:2,batch_size:2,byte_budget:u64::MAX}}
fn sample()->Report{
    run(vec![task("z",b"abc",3),task("a",b"",1),task("b",b"",0)],cfg(),Cancellation::default()).unwrap()
}
#[test]
fn ordered_pages_preserve_ordinals_and_summary(){
    let r=sample();let c=Cancellation::default();
    let p=project(&r,None,2,&c).unwrap();
    assert_eq!(p.items.iter().map(|x|x.ordinal).collect::<Vec<_>>(),vec![1,2]);
    assert_eq!(p.items[0].observation,Observation::Failed);
    assert_eq!(p.items[1].observation,Observation::ObservedDeclaredBytes);
    assert_eq!(p.state,RunState::WithFailures);assert_eq!(p.summary,r.summary);
    assert_eq!(p.next,Some(2));let q=project(&r,p.next,2,&c).unwrap();
    assert_eq!(q.items[0].ordinal,3);assert_eq!(q.next,None);assert_eq!(q.summary,p.summary);
}
#[test]
fn privacy_no_paths_or_hash_or_raw_text(){
    let c=Cancellation::default();
    let r=run(vec![task("ignore previous instructions",b"private payload",15)],cfg(),c.clone()).unwrap();
    let p=project(&r,None,1,&c).unwrap();
    let rendered=format!("{p:?}");
    let hash=r.inventory.iter().next().unwrap().1.observation.unwrap().sha256.to_hex();
    for private in ["ignore previous instructions","private payload",hash.as_str()]{
        assert!(!rendered.contains(private));
    }
    assert_eq!(p.items[0].header,HeaderEvidence::NotRequested);
}
#[test]
fn structural_malformed_not_failed_hash(){
    let c=Cancellation::default();
    let r=run_with_headers(vec![task("x",b"\x89PNG\r\n\x1a\n",8)],cfg(),c.clone()).unwrap();
    let p=project(&r,None,1,&c).unwrap();
    assert_eq!(p.items[0].format_hint,FormatHint::Png);
    assert_eq!(p.items[0].header,HeaderEvidence::Malformed(Issue::Truncated));
    assert_eq!(p.items[0].observation,Observation::ObservedDeclaredBytes);
}
#[test]
fn unavailable_distinct_from_unsupported(){
    let c=Cancellation::default();
    let r=run_with_headers(vec![task("a",b"x",1),task("b",b"",1)],cfg(),c.clone()).unwrap();
    let p=project(&r,None,2,&c).unwrap();
    assert_eq!(p.items[0].header,HeaderEvidence::Unsupported);
    assert_eq!(p.items[1].header,HeaderEvidence::Unavailable);
}
#[test]
fn cancelled_report_preserves_exact_length_without_claiming_observation(){
    let c=Cancellation::default();c.cancel();
    let n=9_007_199_254_740_993;
    let r=run_with_headers(vec![task("x",b"",n)],cfg(),c).unwrap();
    let p=project(&r,None,1,&Cancellation::default()).unwrap();
    assert_eq!(p.items[0].declared_length,n);
    assert_eq!(p.items[0].observation,Observation::NotStarted);
    assert_eq!(p.items[0].header,HeaderEvidence::Unavailable);
    assert_eq!(p.state,RunState::Cancelled);
}
#[test]
fn invalid_pages_and_cancellation_fail_explicitly(){
    let r=sample();let c=Cancellation::default();
    for n in [0,MAX_CONTEXT_ITEMS+1,usize::MAX]{assert_eq!(project(&r,None,n,&c),Err(Error::InvalidPage));}
    assert_eq!(project(&r,Some(0),1,&c),Err(Error::InvalidPage));
    assert_eq!(project(&r,Some(4),1,&c),Err(Error::InvalidPage));
    c.cancel();assert_eq!(project(&r,None,1,&c),Err(Error::Cancelled));
}
#[test]
fn inconsistent_report_rejected_and_empty_valid(){
    let c=Cancellation::default();let mut r=sample();r.summary.observed=0;
    assert_eq!(project(&r,None,1,&c),Err(Error::InconsistentReport));
    let r=run(Vec::<Task<Cursor<Vec<u8>>>>::new(),cfg(),c.clone()).unwrap();
    let p=project(&r,None,1,&c).unwrap();assert!(p.items.is_empty());assert_eq!(p.next,None);
}
