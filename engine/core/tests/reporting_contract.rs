use negrodroid_core::{Cancellation, orchestration::{run,Config,Report}, parallel::{Task,Status},
    inventory::SourceKey, reporting::{export_json, Options, Paths, ExportError, MAX_EXPORT_BYTES}};
use std::io::Cursor;
fn task(key: SourceKey, data: &[u8], length:u64)->Task<Cursor<Vec<u8>>> {
    Task {key, reader:Cursor::new(data.to_vec()), length}
}
fn key(p:&str)->SourceKey { SourceKey::physical(7,p).unwrap() }
fn cfg()->Config {Config {workers:2,batch_size:2,byte_budget:10000}}
fn opt(paths:Paths)->Options {Options {max_bytes:MAX_EXPORT_BYTES,paths}}
fn sample()->Report {
    run(vec![task(key("private/token.txt"),b"abc",3)],cfg(),Cancellation::default()).unwrap()
}
#[test]
fn default_path_policy_omits_names_and_scope_id() {
    let out=export_json(&sample(),opt(Paths::Omit)).unwrap();
    assert!(!out.contains("private"));
    assert!(!out.contains("\"root\":"));
    assert!(!out.contains("\"relative_path\":"));
    assert!(out.contains("\"schema_version\":1"));
    assert!(out.contains("\"path_policy\":\"omitted\""));
    assert!(out.contains("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"));
}
#[test]
fn logical_paths_are_escaped_and_structured() {
    let k=key("arq\"á.zip").member("nested/配置.json").unwrap();
    let r=run(vec![task(k,b"x",1)],cfg(),Cancellation::default()).unwrap();
    let out=export_json(&r,opt(Paths::IncludeLogical)).unwrap();
    assert!(out.contains("\"relative_path\":\"arq\\\"á.zip\""));
    assert!(out.contains("\"members\":[\"nested/配置.json\"]"));
    assert!(out.contains("\"root\":\"7\""));
}
#[test]
fn output_is_deterministic_for_input_order() {
    let a=||task(key("a"),b"x",1); let b=||task(key("b"),b"y",1);
    let r1=run(vec![a(),b()],cfg(),Cancellation::default()).unwrap();
    let r2=run(vec![b(),a()],cfg(),Cancellation::default()).unwrap();
    assert_eq!(export_json(&r1,opt(Paths::IncludeLogical)),export_json(&r2,opt(Paths::IncludeLogical)));
}
#[test]
fn exact_output_budget_and_overflow() {
    let r=sample(); let out=export_json(&r,opt(Paths::Omit)).unwrap();
    assert_eq!(export_json(&r,Options {max_bytes:out.len(),paths:Paths::Omit}).unwrap(),out);
    assert_eq!(export_json(&r,Options {max_bytes:out.len()-1,paths:Paths::Omit}),Err(ExportError::OutputLimit));
    for n in [0,MAX_EXPORT_BYTES+1] {assert_eq!(export_json(&r,Options {max_bytes:n,paths:Paths::Omit}),Err(ExportError::InvalidLimit));}
}
#[test]
fn failures_and_cancellation_are_not_claimed_as_observed() {
    let r=run(vec![task(key("a"),b"x",2)],cfg(),Cancellation::default()).unwrap();
    let out=export_json(&r,opt(Paths::Omit)).unwrap();
    assert!(out.contains("\"state\":\"with_failures\""));
    assert!(out.contains("\"sha256\":null"));
    assert!(out.contains("\"error_kind\":\"UnexpectedEof\""));
    let c=Cancellation::default();c.cancel();
    let r=run(vec![task(key("a"),b"x",1)],cfg(),c).unwrap();
    let out=export_json(&r,opt(Paths::Omit)).unwrap();
    assert!(out.contains("\"state\":\"cancelled\""));
    assert!(out.contains("\"status\":\"not_started\""));
    assert!(out.contains("\"sha256\":null"));
}
#[test]
fn inconsistent_public_summary_is_rejected() {
    let mut r=sample();r.summary.observed=0;
    assert_eq!(export_json(&r,opt(Paths::Omit)),Err(ExportError::InconsistentReport));
}
#[test]
fn missing_or_mismatched_diagnostic_is_rejected() {
    let mut r=sample(); r.diagnostics.get_mut(&key("private/token.txt")).unwrap().status=Status::NotStarted;
    assert_eq!(export_json(&r,opt(Paths::Omit)),Err(ExportError::InconsistentReport));
    let mut r=sample();r.diagnostics.clear();
    assert_eq!(export_json(&r,opt(Paths::Omit)),Err(ExportError::InconsistentReport));
}
#[test]
fn empty_report_is_explicit_and_complete() {
    let r=run(Vec::<Task<Cursor<Vec<u8>>>>::new(),cfg(),Cancellation::default()).unwrap();
    let out=export_json(&r,opt(Paths::Omit)).unwrap();
    assert!(out.contains("\"planned\":0"));
    assert!(out.ends_with("\"entries\":[]}"));
    assert!(out.contains("signature_hint_not_structural_validation"));
}
#[test]
fn u64_length_preserved_without_float_rounding() {
    let length=9_007_199_254_740_993u64;
    let c=Cancellation::default();c.cancel();
    let r=run(vec![task(key("a"),b"",length)],Config {byte_budget:u64::MAX,..cfg()},c).unwrap();
    let out=export_json(&r,opt(Paths::Omit)).unwrap();
    assert!(out.contains("\"declared_length\":\"9007199254740993\""));
}
