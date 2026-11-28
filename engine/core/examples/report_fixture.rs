//! Synthetic data only; generates reports for an independent JSON consumer.
use negrodroid_core::{Cancellation, inventory::SourceKey, orchestration::{run,run_with_headers,Config},
    parallel::Task, reporting::{export_json,Options,Paths,MAX_EXPORT_BYTES}};
use std::io::{self,Cursor,Write};

fn task(key: SourceKey, data: &[u8], length: u64) -> Task<Cursor<Vec<u8>>> {
    Task {key,reader:Cursor::new(data.to_vec()),length}
}
fn key(path:&str)->SourceKey { SourceKey::physical(9_007_199_254_740_993,path).unwrap() }
fn main() {
    let mode=std::env::args().nth(1).expect("fixture mode");
    let cancel=Cancellation::default();
    let (tasks,paths)=match mode.as_str() {
        "mixed_omit" | "mixed_include" => (
            vec![task(key("z-failed"),b"x",2),
                task(key("a-private-\"á.zip").member("nested/配置.json").unwrap(),b"abc",3),
                task(key("b-empty"),b"",0)],
            if mode=="mixed_include" {Paths::IncludeLogical} else {Paths::Omit}),
        "cancelled" => {
            cancel.cancel();
            (vec![task(key("large"),b"",9_007_199_254_740_993)],Paths::Omit)
        },
        "headers" => (vec![task(key("a"),b"\x89PNG\r\n\x1a\n\x00\x00\x00\x0dIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89",33),
            task(key("b"),b"PK\x03\x04",4),task(key("c"),b"abc",3)],Paths::Omit),
        "empty" => (Vec::new(),Paths::Omit),
        _ => panic!("unknown synthetic fixture"),
    };
    let config=Config {workers:2,batch_size:2,byte_budget:u64::MAX};
    let report=if mode=="headers" {run_with_headers(tasks,config,cancel)}else{run(tasks,config,cancel)}.unwrap();
    let output=export_json(&report,Options {max_bytes:MAX_EXPORT_BYTES,paths}).unwrap();
    io::stdout().lock().write_all(output.as_bytes()).unwrap();
}
