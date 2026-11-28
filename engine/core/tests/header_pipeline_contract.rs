use negrodroid_core::{Cancellation,inventory::SourceKey,orchestration::{run,run_with_headers,Config,RunError},
    parallel::{Task,BatchError,Status},reporting::{export_json,Options,Paths,ExportError,MAX_EXPORT_BYTES},
    structural::{Verdict,Header,Issue}};
use std::io::Cursor;
fn key(p:&str)->SourceKey{SourceKey::physical(1,p).unwrap()}
fn task(p:&str,b:&[u8])->Task<Cursor<Vec<u8>>>{Task{key:key(p),length:b.len() as u64,reader:Cursor::new(b.to_vec())}}
fn cfg(budget:u64)->Config{Config{workers:2,batch_size:2,byte_budget:budget}}
fn opt()->Options{Options{max_bytes:MAX_EXPORT_BYTES,paths:Paths::Omit}}
fn png()->Vec<u8>{b"\x89PNG\r\n\x1a\n\x00\x00\x00\x0dIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89".to_vec()}
#[test]
fn legacy_schema_and_budget_unchanged(){
    let r=run(vec![task("x",&png())],cfg(66),Cancellation::default()).unwrap();
    assert!(!r.headers_enabled());assert_eq!(r.summary.charged_bytes,66);
    assert_eq!(r.diagnostics[&key("x")].header,None);
    let j=export_json(&r,opt()).unwrap();
    assert!(j.contains("\"schema_version\":1"));assert!(!j.contains("header_inspection"));
}
#[test]
fn header_mode_reserves_globally_and_exports_metadata(){
    let r=run_with_headers(vec![task("x",&png())],cfg(99),Cancellation::default()).unwrap();
    assert!(r.headers_enabled());assert_eq!(r.summary.reserved_bytes,99);assert_eq!(r.summary.charged_bytes,99);
    assert_eq!(r.diagnostics[&key("x")].header,Some(Verdict::HeaderChecked(Header::Png{width:1,height:1,bit_depth:8,color_type:6})));
    let j=export_json(&r,opt()).unwrap();
    assert!(j.contains("\"schema_version\":2"));assert!(j.contains("\"state\":\"header_checked_only\""));
    assert!(j.contains("\"width\":1"));assert!(!j.contains("\"relative_path\""));
}
#[test]
fn malformed_header_still_has_observed_hash(){
    let mut b=png();b[32]^=1;
    let r=run_with_headers(vec![task("x",&b)],cfg(99),Cancellation::default()).unwrap();
    assert_eq!(r.diagnostics[&key("x")].header,Some(Verdict::Malformed(Issue::Checksum)));
    assert_eq!(r.diagnostics[&key("x")].status,Status::Observed);
    assert!(r.inventory.get(&key("x")).unwrap().observation.is_some());
    assert!(export_json(&r,opt()).unwrap().contains("\"issue\":\"checksum\""));
}
#[test]
fn insufficient_budget_rejects_scope(){
    assert!(matches!(run_with_headers(vec![task("x",&png())],cfg(98),Cancellation::default()),Err(RunError::Analysis(BatchError::ReadBudget))));
}
#[test]
fn unsupported_format_still_observed(){
    let r=run_with_headers(vec![task("x",b"abc")],cfg(9),Cancellation::default()).unwrap();
    assert_eq!(r.summary.reserved_bytes,9);assert_eq!(r.summary.charged_bytes,6);
    assert_eq!(r.diagnostics[&key("x")].header,Some(Verdict::Unsupported));
    assert!(export_json(&r,opt()).unwrap().contains("\"header_inspection\":{\"state\":\"unsupported\"}"));
}
#[test]
fn cancellation_and_failure_have_no_header_claim(){
    let c=Cancellation::default();c.cancel();
    let r=run_with_headers(vec![task("x",&png())],cfg(99),c).unwrap();
    assert_eq!(r.diagnostics[&key("x")].header,None);
    assert!(export_json(&r,opt()).unwrap().contains("\"state\":\"not_available\""));
    let mut t=task("x",&png());t.length+=1;
    let r=run_with_headers(vec![t],cfg(102),Cancellation::default()).unwrap();
    assert!(matches!(r.diagnostics[&key("x")].status,Status::Failed(_)));
    assert_eq!(r.diagnostics[&key("x")].header,None);
}
#[test]
fn inconsistent_header_claim_rejected(){
    let mut r=run_with_headers(vec![task("x",&png())],cfg(99),Cancellation::default()).unwrap();
    r.diagnostics.get_mut(&key("x")).unwrap().header=None;
    assert_eq!(export_json(&r,opt()),Err(ExportError::InconsistentReport));
    r.diagnostics.get_mut(&key("x")).unwrap().header=Some(Verdict::HeaderChecked(Header::ZipEmpty));
    assert_eq!(export_json(&r,opt()),Err(ExportError::InconsistentReport));
}
#[test]
fn detailed_export_still_bounded(){
    let r=run_with_headers(vec![task("x",&png())],cfg(99),Cancellation::default()).unwrap();
    let j=export_json(&r,opt()).unwrap();
    assert_eq!(export_json(&r,Options{max_bytes:j.len()-1,paths:Paths::Omit}),Err(ExportError::OutputLimit));
}
