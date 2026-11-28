use negrodroid_core::{Cancellation,ReadSession,binary_pages::{Layout,Navigator,Error}};
use std::io::{Cursor,Read,Seek,SeekFrom,self};

#[test]
fn layout_boundaries_and_partial_tail(){
    let l=Layout::new(17,8).unwrap();
    assert_eq!(l.total_pages(),3);
    assert_eq!(l.containing(7).unwrap().offset,0);
    assert_eq!(l.containing(8).unwrap().index,1);
    let p=l.containing(16).unwrap();
    assert_eq!((p.offset,p.size,p.previous,p.next),(16,1,Some(1),None));
    assert_eq!(l.containing(17),Err(Error::OutsideSource));
    assert_eq!(l.page(3),Err(Error::OutsideSource));
}
#[test]
fn maximum_u64_layout_no_overflow(){
    let l=Layout::new(u64::MAX,4096).unwrap();
    let p=l.containing(u64::MAX-1).unwrap();
    assert_eq!(p.size,4095);
    assert_eq!(p.offset+(p.size as u64),u64::MAX);
    assert_eq!(p.next,None);
    let single=Layout::new(u64::MAX,1).unwrap();
    assert_eq!(single.total_pages(),u64::MAX);
    assert_eq!(single.page(u64::MAX-1).unwrap().offset,u64::MAX-1);
}
#[test]
fn invalid_page_sizes_and_empty_sentinel(){
    assert_eq!(Layout::new(0,0),Err(Error::InvalidPageSize));
    assert_eq!(Layout::new(1,4097),Err(Error::InvalidPageSize));
    let l=Layout::new(0,8).unwrap();
    assert_eq!(l.total_pages(),0);
    assert_eq!(l.containing(0).unwrap().size,0);
    assert_eq!(l.page(0),Err(Error::EmptySource));
    assert_eq!(l.containing(1),Err(Error::OutsideSource));
    let mut n=Navigator::new(ReadSession::new(Cursor::new([]),0,0,Cancellation::default()),8).unwrap();
    assert_eq!(n.next().unwrap().unwrap().preview.dump,"");
    assert_eq!(n.next().unwrap(),None);
}
#[test]
fn navigation_and_budget_charge_on_each_read(){
    let mut n=Navigator::new(ReadSession::new(Cursor::new(b"ABCDEFGHI"),9,13,Cancellation::default()),4).unwrap();
    assert_eq!(n.current(),None);
    assert_eq!(n.previous().unwrap(),None);
    assert_eq!(n.next().unwrap().unwrap().location.offset,0);
    assert_eq!(n.jump(7).unwrap().location.offset,4);
    assert_eq!(n.next().unwrap().unwrap().preview.shown,1);
    assert_eq!(n.next().unwrap(),None);
    assert_eq!(n.previous().unwrap().unwrap().location.offset,4);
    assert_eq!(n.remaining_budget(),0);
    assert!(n.page(0).is_err());
    assert_eq!(n.current(),Some(1));
}
#[test]
fn failed_or_cancelled_read_never_changes_cursor(){
    let c=Cancellation::default();
    let mut n=Navigator::new(ReadSession::new(Cursor::new(b"ABCD"),8,12,c.clone()),4).unwrap();
    n.page(0).unwrap();
    assert_eq!(n.page(1).unwrap_err().kind(),io::ErrorKind::UnexpectedEof);
    assert_eq!(n.current(),Some(0));assert_eq!(n.remaining_budget(),4);
    c.cancel();
    assert_eq!(n.page(0).unwrap_err().kind(),io::ErrorKind::Interrupted);
    assert_eq!(n.current(),Some(0));assert_eq!(n.remaining_budget(),4);
}
struct Sparse{position:u64}
impl Read for Sparse{fn read(&mut self,b:&mut [u8])->io::Result<usize>{b.fill(0x41);self.position+=b.len() as u64;Ok(b.len())}}
impl Seek for Sparse{fn seek(&mut self,p:SeekFrom)->io::Result<u64>{match p{SeekFrom::Start(n)=>{self.position=n;Ok(n)},_=>Err(io::ErrorKind::InvalidInput.into())}}}
#[test]
fn sparse_source_beyond_javascript_exact_integer(){
    let address=9_007_199_254_740_993u64;
    let mut n=Navigator::new(ReadSession::new(Sparse{position:0},address+64,64,Cancellation::default()),32).unwrap();
    let p=n.jump(address).unwrap();
    assert_eq!(p.location.offset,address-1);
    assert_eq!(p.preview.shown,32);
    assert!(p.preview.dump.starts_with(&format!("{:08X}  41",address-1)));
    assert_eq!(n.remaining_budget(),32);
}
#[test]
fn all_small_layouts_cover_without_overlap(){
    for len in 1..=129{
        for size in 1..=32{
            let l=Layout::new(len,size).unwrap();
            let mut end=0;
            for i in 0..l.total_pages(){
                let p=l.page(i).unwrap();
                assert_eq!(p.offset,end);assert!(p.size>0&&p.size<=size);
                end+=p.size as u64;
                assert_eq!(l.containing(end-1).unwrap(),p);
            }
            assert_eq!(end,len);
        }
    }
}
