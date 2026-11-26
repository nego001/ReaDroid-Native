use negrodroid_core::{Cancellation,ReadSession,virtual_overlay::{Overlay,MAX_EDIT_BYTES,MAX_PATCHED_BYTES}};
use std::{io::{self,Cursor,Read,Seek,SeekFrom},cell::RefCell,rc::Rc};
fn overlay(b:&[u8],budget:u64,cap:usize)->Overlay<Cursor<&[u8]>>{
    Overlay::new(ReadSession::new(Cursor::new(b),b.len() as u64,budget,Cancellation::default()),cap).unwrap()
}
#[test]
fn virtual_replacement_and_original_unchanged(){
    let bytes=*b"ABCDE";
    let mut o=overlay(&bytes,20,8);
    assert_eq!(o.replace(0,1,b"BC",b"xy").unwrap().patched_bytes,2);
    assert_eq!(o.read_window(0,5).unwrap().bytes,b"AxyDE");
    assert_eq!(&bytes,b"ABCDE");assert_eq!(o.remaining_budget(),13);
}
#[test]
fn overlap_and_restore_original_removes_patch(){
    let mut o=overlay(b"ABCDE",30,3);
    o.replace(0,1,b"BC",b"xy").unwrap();
    let state=o.replace(1,2,b"yD",b"Cz").unwrap();
    assert_eq!((state.revision,state.patched_bytes),(2,2));
    assert_eq!(o.read_window(0,5).unwrap().bytes,b"AxCzE");
    o.replace(2,1,b"xCz",b"BCD").unwrap();
    assert_eq!(o.state().patched_bytes,0);
}
#[test]
fn stale_and_mismatched_preconditions_atomic(){
    let mut o=overlay(b"ABCD",20,4);
    o.replace(0,1,b"B",b"x").unwrap();
    assert!(o.replace(0,0,b"A",b"z").is_err());
    assert_eq!(o.remaining_budget(),19);
    assert!(o.replace(1,0,b"AY",b"zz").is_err());
    assert_eq!(o.remaining_budget(),17);
    assert_eq!(o.state().revision,1);
    assert_eq!(o.read_window(0,4).unwrap().bytes,b"AxCD");
}
#[test]
fn capacity_net_change_and_rejected_edit(){
    let mut o=overlay(b"ABC",30,1);
    o.replace(0,0,b"A",b"x").unwrap();
    assert!(o.replace(1,1,b"B",b"y").is_err());
    assert_eq!(o.state().revision,1);
    assert_eq!(o.read_window(0,3).unwrap().bytes,b"xBC");
    let state=o.replace(1,0,b"xB",b"Ay").unwrap();
    assert_eq!(state.patched_bytes,1);
    assert_eq!(o.read_window(0,3).unwrap().bytes,b"AyC");
}
#[test]
fn noop_and_discard_revision(){
    let mut o=overlay(b"AB",20,2);
    assert_eq!(o.replace(0,0,b"AB",b"AB").unwrap().revision,0);
    o.replace(0,0,b"A",b"x").unwrap();
    assert!(o.discard(0).is_err());
    assert_eq!(o.discard(1).unwrap().revision,2);
    assert_eq!(o.discard(2).unwrap().revision,2);
    assert_eq!(o.read_window(0,2).unwrap().bytes,b"AB");
}
#[test]
fn invalid_ranges_lengths_and_capacity(){
    let mut o=overlay(b"AB",5,2);
    assert!(o.replace(0,0,b"",b"").is_err());
    assert!(o.replace(0,0,b"A",b"AB").is_err());
    assert!(o.replace(0,2,b"A",b"B").is_err());
    assert!(o.replace(0,u64::MAX,b"A",b"B").is_err());
    assert!(o.replace(0,0,&vec![0;MAX_EDIT_BYTES+1],&vec![1;MAX_EDIT_BYTES+1]).is_err());
    assert_eq!(o.remaining_budget(),5);
    for cap in [0,MAX_PATCHED_BYTES+1]{
        assert!(Overlay::new(ReadSession::new(Cursor::new(b"A"),1,1,Cancellation::default()),cap).is_err());
    }
}
#[test]
fn read_budget_failure_and_cancellation(){
    let c=Cancellation::default();
    let mut o=Overlay::new(ReadSession::new(Cursor::new(b"AB"),2,2,c.clone()),2).unwrap();
    o.replace(0,0,b"A",b"x").unwrap();
    assert!(o.replace(1,0,b"xB",b"yz").is_err());
    assert_eq!(o.remaining_budget(),1);
    c.cancel();
    assert_eq!(o.discard(1).unwrap_err().kind(),io::ErrorKind::Interrupted);
    assert_eq!(o.read_window(0,1).unwrap_err().kind(),io::ErrorKind::Interrupted);
    assert_eq!(o.state().patched_bytes,1);
}
struct Shared{bytes:Rc<RefCell<Vec<u8>>>,position:usize}
impl Read for Shared{
    fn read(&mut self,b:&mut [u8])->io::Result<usize>{
        let data=self.bytes.borrow();
        let n=b.len().min(data.len().saturating_sub(self.position));
        b[..n].copy_from_slice(&data[self.position..self.position+n]);self.position+=n;Ok(n)
    }
}
impl Seek for Shared{
    fn seek(&mut self,p:SeekFrom)->io::Result<u64>{
        if let SeekFrom::Start(n)=p{self.position=n as usize;Ok(n)}else{Err(io::ErrorKind::InvalidInput.into())}
    }
}
#[test]
fn observed_drift_rejects_without_mutating_overlay(){
    let bytes=Rc::new(RefCell::new(b"AB".to_vec()));
    let mut o=Overlay::new(ReadSession::new(Shared{bytes:bytes.clone(),position:0},2,10,Cancellation::default()),2).unwrap();
    o.replace(0,0,b"A",b"x").unwrap();
    bytes.borrow_mut()[0]=b'Z';
    assert_eq!(o.read_window(0,2).unwrap_err().kind(),io::ErrorKind::InvalidData);
    assert!(o.replace(1,0,b"x",b"Y").is_err());
    assert_eq!((o.state().revision,o.state().patched_bytes),(1,1));
}
#[test]
fn exhaustive_small_overlay_oracle(){
    for initial in 0..16u8{for target in 0..16u8{
        let b:Vec<u8>=(0..4).map(|i|(initial>>i)&1).collect();
        let t:Vec<u8>=(0..4).map(|i|(target>>i)&1).collect();
        let mut o=overlay(&b,16,4);
        let s=o.replace(0,0,&b,&t).unwrap();
        assert_eq!(s.patched_bytes,b.iter().zip(&t).filter(|(x,y)|x!=y).count());
        assert_eq!(o.read_window(0,4).unwrap().bytes,t);
        let s=o.replace(s.revision,0,&t,&b).unwrap();
        assert_eq!(s.patched_bytes,0);
        assert_eq!(o.read_window(0,4).unwrap().bytes,b);
    }}
}
