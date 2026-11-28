use negrodroid_core::{Cancellation,discovery::{discover,Limits,Error},inventory::{Coverage,SourceKey}};
use std::{fs,path::PathBuf,sync::atomic::{AtomicUsize,Ordering}};
static NEXT:AtomicUsize=AtomicUsize::new(0);
struct Temp(PathBuf);
impl Temp{
    fn new()->Self{
        loop{
            let p=std::env::temp_dir().join(format!("negrodroid-discovery-{}-{}",std::process::id(),NEXT.fetch_add(1,Ordering::Relaxed)));
            match fs::create_dir(&p){Ok(())=>return Self(p),Err(e) if e.kind()==std::io::ErrorKind::AlreadyExists=>continue,Err(e)=>panic!("{e}")}
        }
    }
}
impl Drop for Temp{fn drop(&mut self){let _=fs::remove_dir_all(&self.0);}}
fn limits()->Limits{Limits{max_entries:100,max_depth:8,max_path_bytes:4096}}
#[test]
fn metadata_only_sorted_inventory(){
    let t=Temp::new();fs::create_dir(t.0.join("nested")).unwrap();
    fs::write(t.0.join("z"),b"abc").unwrap();fs::write(t.0.join("nested/a"),b"x").unwrap();
    fs::write(t.0.join("a"),b"").unwrap();
    let r=discover(&t.0,42,limits(),&Cancellation::default()).unwrap();
    let names:Vec<_>=r.inventory.iter().map(|(k,_)|k.relative_path()).collect();
    assert_eq!(names,vec!["a","nested/a","z"]);assert_eq!(r.counts.visited,4);
    assert_eq!(r.counts.files,3);assert_eq!(r.counts.directories,1);assert!(r.counts.no_skips());
    for (_,e) in r.inventory.iter(){assert_eq!(e.coverage,Coverage::Unexamined);assert!(e.observation.is_none());}
    assert_eq!(r.inventory.get(&SourceKey::physical(42,"z").unwrap()).unwrap().declared_length,Some(3));
    assert_eq!(fs::read(t.0.join("z")).unwrap(),b"abc");
}
#[test]
fn empty_directory(){
    let t=Temp::new();let r=discover(&t.0,1,limits(),&Cancellation::default()).unwrap();
    assert!(r.inventory.is_empty());assert_eq!(r.counts.visited,0);assert!(r.counts.no_skips());
}
#[test]
fn depth_limit_marks_unvisited_subtree(){
    let t=Temp::new();fs::create_dir(t.0.join("nested")).unwrap();fs::write(t.0.join("nested/a"),b"x").unwrap();
    let r=discover(&t.0,1,Limits{max_depth:0,..limits()},&Cancellation::default()).unwrap();
    assert_eq!(r.counts.depth_skipped,1);assert!(!r.counts.no_skips());assert!(r.inventory.is_empty());
}
#[test]
fn entry_limit_counts_directories_and_files(){
    let t=Temp::new();fs::create_dir(t.0.join("nested")).unwrap();fs::write(t.0.join("a"),b"x").unwrap();
    assert!(matches!(discover(&t.0,1,Limits{max_entries:1,..limits()},&Cancellation::default()),Err(Error::EntryLimit)));
}
#[test]
fn path_budget_rejected(){
    let t=Temp::new();fs::write(t.0.join("long"),b"x").unwrap();
    assert!(matches!(discover(&t.0,1,Limits{max_path_bytes:3,..limits()},&Cancellation::default()),Err(Error::PathBudget)));
}
#[test]
fn invalid_limits_and_cancelled(){
    let t=Temp::new();
    assert!(matches!(discover(&t.0,1,Limits{max_entries:0,..limits()},&Cancellation::default()),Err(Error::InvalidLimits)));
    let c=Cancellation::default();c.cancel();
    assert!(matches!(discover(&t.0,1,limits(),&c),Err(Error::Cancelled)));
}
#[test]
fn invalid_root_and_missing_root(){
    let t=Temp::new();fs::write(t.0.join("a"),b"x").unwrap();
    assert!(matches!(discover(&t.0.join("a"),1,limits(),&Cancellation::default()),Err(Error::InvalidRoot)));
    assert!(matches!(discover(&t.0.join("missing"),1,limits(),&Cancellation::default()),Err(Error::Io(_))));
    assert!(matches!(discover(std::path::Path::new("."),1,limits(),&Cancellation::default()),Err(Error::InvalidRoot)));
}
#[test]
fn unicode_name_preserved(){
    let t=Temp::new();fs::write(t.0.join("配置.txt"),b"x").unwrap();
    let r=discover(&t.0,1,limits(),&Cancellation::default()).unwrap();
    assert_eq!(r.inventory.iter().next().unwrap().0.relative_path(),"配置.txt");
}
#[cfg(unix)]
#[test]
fn observed_links_and_cycles_not_followed(){
    use std::os::unix::fs::symlink;
    let t=Temp::new();let outside=Temp::new();fs::write(outside.0.join("secret"),b"x").unwrap();
    symlink(&outside.0,t.0.join("external")).unwrap();
    symlink(&t.0,t.0.join("cycle")).unwrap();symlink(t.0.join("missing"),t.0.join("broken")).unwrap();
    let r=discover(&t.0,1,limits(),&Cancellation::default()).unwrap();
    assert_eq!(r.counts.links,3);assert!(r.inventory.is_empty());assert!(!r.counts.no_skips());
    assert!(matches!(discover(&t.0.join("external"),1,limits(),&Cancellation::default()),Err(Error::InvalidRoot)));
}
#[cfg(unix)]
#[test]
fn invalid_logical_name_explicitly_skipped(){
    let t=Temp::new();
    fs::write(t.0.join("bad:name"),b"x").unwrap();
    let r=discover(&t.0,1,limits(),&Cancellation::default()).unwrap();
    assert_eq!(r.counts.invalid_names,1);assert!(r.inventory.is_empty());
}
#[cfg(target_os="linux")]
#[test]
fn invalid_utf8_directory_entry_explicitly_skipped(){
    use std::os::unix::ffi::OsStrExt;
    let t=Temp::new();fs::write(t.0.join(std::ffi::OsStr::from_bytes(b"bad\xff")),b"x").unwrap();
    let r=discover(&t.0,1,limits(),&Cancellation::default()).unwrap();
    assert_eq!(r.counts.invalid_names,1);assert!(r.inventory.is_empty());
}

#[test]
fn root_parent_traversal_refused_before_io(){
    let t=Temp::new();let p=t.0.join("missing").join("..");
    assert!(matches!(discover(&p,1,limits(),&Cancellation::default()),Err(Error::InvalidRoot)));
}
#[test]
fn real_directory_with_trailing_dot_still_works(){
    let t=Temp::new();fs::write(t.0.join("a"),b"x").unwrap();
    let r=discover(&t.0.join("."),1,limits(),&Cancellation::default()).unwrap();
    assert_eq!(r.counts.files,1);
}
#[cfg(unix)]
#[test]
fn root_symlink_with_separator_or_dot_is_refused(){
    use std::os::unix::fs::symlink;
    let t=Temp::new();let outside=Temp::new();fs::write(outside.0.join("secret"),b"x").unwrap();
    let link=t.0.join("external");symlink(&outside.0,&link).unwrap();
    let mut slash=link.as_os_str().to_os_string();slash.push("/");
    for root in [PathBuf::from(slash),link.join("."),link.join("./.")]{
        assert!(matches!(discover(&root,1,limits(),&Cancellation::default()),Err(Error::InvalidRoot)));
    }
}
#[cfg(unix)]
#[test]
fn special_socket_not_opened(){
    let t=Temp::new();
    let _socket=std::os::unix::net::UnixListener::bind(t.0.join("sock")).unwrap();
    let r=discover(&t.0,1,limits(),&Cancellation::default()).unwrap();
    assert_eq!(r.counts.special,1);assert!(r.inventory.is_empty());
}
