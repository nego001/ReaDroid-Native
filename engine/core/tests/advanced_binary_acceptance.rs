//! Cross-module acceptance fixtures. Small snapshots are explicit test
//! fixtures, not a production adapter or whole-file materialization API.
use negrodroid_core::{
    Cancellation,ReadSession,
    binary_pages::Navigator,
    binary_search::{self,Pattern},
    text_encoding::{self,Encoding,Kind},
    data_inspector::{self,Type,Endian,Value},
    binary_comparison::{self,Difference},
    edit_history::{History,Limits},
};
use std::{fs::{self,File,OpenOptions},io::{self,Cursor,Write},path::PathBuf};

fn session(b:&[u8],budget:u64,c:Cancellation)->ReadSession<Cursor<&[u8]>>{
    ReadSession::new(Cursor::new(b),b.len() as u64,budget,c)
}
fn search_limits()->binary_search::Limits{binary_search::Limits{max_starts:64,max_matches:16}}
fn diff_limits()->binary_comparison::Limits{binary_comparison::Limits{max_positions:64,max_ranges:16}}
fn history_limits()->Limits{Limits{entries:8,payload_bytes:128}}
fn hits(b:&[u8],pattern:&str)->Vec<u64>{
    let mut s=session(b,b.len() as u64,Cancellation::default());
    binary_search::search(&mut s,&Pattern::parse(pattern).unwrap(),0..b.len() as u64,0,search_limits()).unwrap().matches
}
fn changed(a:&[u8],b:&[u8])->Vec<(u64,u64,Difference)>{
    let mut l=session(a,a.len() as u64,Cancellation::default());
    let mut r=session(b,b.len() as u64,Cancellation::default());
    let p=binary_comparison::compare(&mut l,&mut r,0..a.len().max(b.len()) as u64,0,diff_limits()).unwrap();
    assert_eq!(p.next_start,None);
    p.ranges.into_iter().map(|r|(r.start,r.end,r.kind)).collect()
}
#[test]
fn all_engines_round_trip_one_authorized_fixture(){
    let base=b"AB\x00\x00\x80\x3f\xc3\xa9END";
    let c=Cancellation::default();
    let mut navigation=Navigator::new(session(base,8,c.clone()),4).unwrap();
    let page=navigation.jump(3).unwrap();
    assert_eq!(page.location.offset,0);
    assert!(page.preview.dump.contains("41 42 00 00"));
    let page=navigation.next().unwrap().unwrap();
    assert_eq!(page.location.offset,4);
    assert_eq!(navigation.remaining_budget(),0);
    assert_eq!(hits(base,"00 ?? 80 3F"),vec![2]);
    let mut h=History::new(session(base,128,c),16,history_limits()).unwrap();
    assert_eq!(h.replace(0,2,&[0,0,0x80,0x3f],&[0,0,0,0x40]).unwrap().revision,1);
    let edited=h.read_window(0,base.len()).unwrap().bytes;
    assert_eq!(hits(&edited,"00 00 00 40"),vec![2]);
    assert!(hits(&edited,"00 ?? 80 3F").is_empty());
    let mut s=session(&edited,6,Cancellation::default());
    let scalar=data_inspector::read(&mut s,Type::F32,Endian::Little,2).unwrap();
    assert_eq!(scalar.value.as_f32(),Some(2.0));
    let text=text_encoding::read(&mut s,Encoding::Utf8,6,2).unwrap();
    assert_eq!(text.decoded.units[0].kind,Kind::Scalar('é'));
    assert_eq!(text.decoded.units[0].offset,6);
    assert_eq!(s.remaining_budget(),0);
    assert_eq!(changed(base,&edited),vec![(4,6,Difference::Changed)]);
    h.undo(1).unwrap();
    let undone=h.read_window(0,base.len()).unwrap().bytes;
    assert_eq!(undone,base);
    assert!(changed(base,&undone).is_empty());
    h.redo(2).unwrap();
    assert_eq!(h.read_window(0,base.len()).unwrap().bytes,edited);
    assert_eq!(h.state().revision,3);
    assert_eq!(h.remaining_budget(),128-12-3*base.len() as u64);
    assert_eq!(base,b"AB\x00\x00\x80\x3f\xc3\xa9END");
}
#[test]
fn paged_search_offsets_feed_precise_edit_and_diff(){
    let base=b"AAAABAAA";
    let c=Cancellation::default();
    let mut s=session(base,32,c.clone());
    let pat=Pattern::parse("41 41").unwrap();
    let mut cursor=0;
    let mut found=vec![];
    loop{
        let p=binary_search::search(&mut s,&pat,0..8,cursor,binary_search::Limits{max_starts:2,max_matches:1}).unwrap();
        found.extend(p.matches);
        match p.next_start{Some(n)=>{assert!(n>cursor);cursor=n},None=>break}
    }
    assert_eq!(found,vec![0,1,2,5,6]);
    let mut h=History::new(session(base,32,c),8,history_limits()).unwrap();
    h.replace(0,found[3],b"AA",b"XY").unwrap();
    let virtual_bytes=h.read_window(0,8).unwrap().bytes;
    assert_eq!(changed(base,&virtual_bytes),vec![(5,7,Difference::Changed)]);
    assert_eq!(hits(&virtual_bytes,"41 41"),vec![0,1,2]);
    let mut n=Navigator::new(session(&virtual_bytes,4,Cancellation::default()),4).unwrap();
    let page=n.jump(5).unwrap();
    assert_eq!(page.location.offset,4);
    assert!(page.preview.dump.contains("42 58 59 41"));
}
#[test]
fn failed_edits_and_failed_undo_keep_revision_and_history(){
    let base=b"ABCDE";
    let mut h=History::new(session(base,12,Cancellation::default()),5,history_limits()).unwrap();
    h.replace(0,0,b"AB",b"xy").unwrap();
    let state=h.state();
    assert!(h.replace(0,2,b"C",b"z").is_err());
    assert_eq!(h.remaining_budget(),10);
    assert!(h.replace(1,2,b"ZZ",b"zz").is_err());
    assert_eq!(h.state(),state);
    assert_eq!(h.remaining_budget(),8);
    let bytes=h.read_window(0,5).unwrap().bytes;
    assert_eq!(changed(base,&bytes),vec![(0,2,Difference::Changed)]);
    h.undo(1).unwrap();
    assert_eq!(h.remaining_budget(),1);
    let state=h.state();
    assert!(h.redo(2).is_err());
    assert_eq!(h.state(),state);
    assert_eq!(h.remaining_budget(),1);
}
#[test]
fn shared_cancellation_prevents_new_results_across_engines(){
    let base=b"ABCD";let c=Cancellation::default();
    let mut h=History::new(session(base,16,c.clone()),4,history_limits()).unwrap();
    h.replace(0,0,b"A",b"x").unwrap();
    let state=h.state();
    let mut n=Navigator::new(session(base,16,c.clone()),2).unwrap();
    n.jump(0).unwrap();
    let mut s=session(base,16,c.clone());
    let mut other=session(base,16,Cancellation::default());
    c.cancel();
    assert_eq!(h.undo(1).unwrap_err().kind(),io::ErrorKind::Interrupted);
    assert_eq!(h.state(),state);
    assert_eq!(n.next().unwrap_err().kind(),io::ErrorKind::Interrupted);
    assert_eq!(n.current(),Some(0));
    assert_eq!(binary_search::search(&mut s,&Pattern::parse("41").unwrap(),0..4,0,search_limits()).unwrap_err().kind(),io::ErrorKind::Interrupted);
    assert_eq!(text_encoding::read(&mut s,Encoding::Ascii,0,1).unwrap_err().kind(),io::ErrorKind::Interrupted);
    assert_eq!(data_inspector::read(&mut s,Type::U8,Endian::Big,0).unwrap_err().kind(),io::ErrorKind::Interrupted);
    assert_eq!(binary_comparison::compare(&mut other,&mut s,0..4,0,diff_limits()).unwrap_err().kind(),io::ErrorKind::Interrupted);
    assert_eq!(s.remaining_budget(),16);
    assert_eq!(other.remaining_budget(),16);
}
struct Scratch(PathBuf);
impl Drop for Scratch{fn drop(&mut self){let _=fs::remove_dir_all(&self.0);}}
#[test]
fn real_read_only_file_preserved_after_virtual_edit_and_history(){
    let stamp=std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos();
    let dir=std::env::temp_dir().join(format!("nd-u3-{}-{stamp}",std::process::id()));
    fs::create_dir(&dir).unwrap();
    let scratch=Scratch(dir);
    let path=scratch.0.join("fixture.bin");
    let base=b"ORIGINAL";
    {let mut f=OpenOptions::new().write(true).create_new(true).open(&path).unwrap();f.write_all(base).unwrap();f.sync_all().unwrap();}
    let c=Cancellation::default();
    {
        let mut h=History::new(ReadSession::from_file(File::open(&path).unwrap(),64,c).unwrap(),8,history_limits()).unwrap();
        h.replace(0,0,b"OR",b"XX").unwrap();
        let virtual_bytes=h.read_window(0,8).unwrap().bytes;
        assert_eq!(virtual_bytes,b"XXIGINAL");
        let mut l=ReadSession::from_file(File::open(&path).unwrap(),8,Cancellation::default()).unwrap();
        let mut r=session(&virtual_bytes,8,Cancellation::default());
        let diff=binary_comparison::compare(&mut l,&mut r,0..8,0,diff_limits()).unwrap();
        assert_eq!(diff.changed,2);assert_eq!(diff.equal,6);
        h.undo(1).unwrap();
        assert_eq!(h.read_window(0,8).unwrap().bytes,base);
        h.redo(2).unwrap();
    }
    assert_eq!(fs::read(&path).unwrap(),base);
    assert_eq!(fs::metadata(&path).unwrap().len(),8);
}
#[test]
fn numeric_and_text_boundaries_preserve_exact_source_coordinates(){
    let base=[0xff,0x41,0x00,0x3d,0xd8,0x00,0xde,0x01];
    let mut s=session(&base,16,Cancellation::default());
    let t=text_encoding::read(&mut s,Encoding::Utf16Le,1,6).unwrap();
    assert_eq!(t.decoded.units[0].offset,1);
    assert_eq!(t.decoded.units[1].offset,3);
    assert_eq!(t.decoded.units[1].kind,Kind::Scalar('😀'));
    let v=data_inspector::read(&mut s,Type::U32,Endian::Little,3).unwrap();
    assert_eq!(v.value,Value::Unsigned(0xde00d83d));
    let mut h=History::new(session(&base,16,Cancellation::default()),4,history_limits()).unwrap();
    h.replace(0,3,&base[3..7],&[0x42,0,0x43,0]).unwrap();
    let edited=h.read_window(0,8).unwrap().bytes;
    let text=text_encoding::decode(Encoding::Utf16Le,1,&edited[1..7]).unwrap();
    assert_eq!(text.units.iter().map(|u|u.kind).collect::<Vec<_>>(),vec![Kind::Scalar('A'),Kind::Scalar('B'),Kind::Scalar('C')]);
    assert_eq!(changed(&base,&edited),vec![(3,7,Difference::Changed)]);
}
