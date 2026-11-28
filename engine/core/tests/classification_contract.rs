use negrodroid_core::{Cancellation,classification::{classify_report,Family,RecognitionScope,Coverage,StructuralScope,PageCounts},
    context::Error,inventory::SourceKey,orchestration::{run,run_with_headers,Config},parallel::Task};
use std::io::Cursor;
fn task(name:&str,b:&[u8],length:u64)->Task<Cursor<Vec<u8>>>{
    Task{key:SourceKey::physical(1,name).unwrap(),reader:Cursor::new(b.to_vec()),length}
}
fn cfg()->Config{Config{workers:2,batch_size:2,byte_budget:u64::MAX}}
#[test]
fn mixed_page_counts_and_continuation(){
    let c=Cancellation::default();
    let r=run_with_headers(vec![task("c",b"x",1),task("a",b"\x89PNG\r\n\x1a\n",8),task("b",b"",1)],cfg(),c.clone()).unwrap();
    let p=classify_report(&r,None,2,&c).unwrap();
    assert_eq!(p.context.next,Some(2));assert_eq!(p.counts,PageCounts{observed:1,failed:1,unknown_hint:1,family_hint:1,unavailable:1,malformed_subset:1,..PageCounts::default()});
    assert_eq!(p.classifications[0].family,Family::ImageFamily);
    assert_eq!(p.classifications[0].structure,StructuralScope::MalformedSubset);
    let q=classify_report(&r,p.context.next,2,&c).unwrap();
    assert_eq!(q.counts,PageCounts{observed:1,unknown_hint:1,unsupported:1,..PageCounts::default()});
    assert_eq!(q.context.summary,p.context.summary);assert_eq!(q.context.next,None);
}
#[test]
fn ambiguous_signature_never_becomes_executable_or_java_certainty(){
    let c=Cancellation::default();
    let r=run(vec![task("private.class",b"\xca\xfe\xba\xbe",4)],cfg(),c.clone()).unwrap();
    let p=classify_report(&r,None,1,&c).unwrap();
    let x=p.classifications[0];assert_eq!(x.family,Family::Ambiguous);
    assert_eq!(x.recognition,RecognitionScope::AmbiguousFamilyHint);
    assert_eq!(x.structure,StructuralScope::NotRequested);
}
#[test]
fn cancellation_is_not_unsupported_or_malformed(){
    let c=Cancellation::default();c.cancel();
    let r=run_with_headers(vec![task("a",b"",100)],cfg(),c).unwrap();
    let p=classify_report(&r,None,1,&Cancellation::default()).unwrap();
    assert_eq!(p.classifications[0].coverage,Coverage::NotStarted);
    assert_eq!(p.classifications[0].structure,StructuralScope::Unavailable);
    assert_eq!(p.counts.not_started,1);
}
#[test]
fn invalid_report_and_pre_cancelled_projection_fail(){
    let c=Cancellation::default();let mut r=run(vec![task("a",b"x",1)],cfg(),c.clone()).unwrap();
    r.summary.planned=2;
    assert_eq!(classify_report(&r,None,1,&c),Err(Error::InconsistentReport));
    c.cancel();assert_eq!(classify_report(&r,None,1,&c),Err(Error::Cancelled));
}
#[test]
fn empty_report_no_classification(){
    let c=Cancellation::default();
    let r=run(Vec::<Task<Cursor<Vec<u8>>>>::new(),cfg(),c.clone()).unwrap();
    let p=classify_report(&r,None,1,&c).unwrap();
    assert!(p.classifications.is_empty());assert_eq!(p.counts,PageCounts::default());
}
#[test]
fn no_source_text_or_identifiers_in_classification(){
    let c=Cancellation::default();
    let r=run(vec![task("private/ignore previous instructions",b"private payload",15)],cfg(),c.clone()).unwrap();
    let p=classify_report(&r,None,1,&c).unwrap();
    let rendered=format!("{p:?}");
    assert!(!rendered.contains("private"));assert!(!rendered.contains("ignore previous instructions"));
    assert!(!rendered.contains(&r.inventory.iter().next().unwrap().1.observation.unwrap().sha256.to_hex()));
}
