//! Bounded classic DEX header and map declaration inspection. No bytecode,
//! string data, class data, checksum/signature verification or execution.
use crate::ReadSession;
use std::{collections::BTreeSet,io::{self,Read,Seek}};
pub const MAX_MAP_ITEMS:usize=128;
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Issue{Truncated,Signature,Field,Bounds,MapOrder,DuplicateType,MapMismatch,Overlap}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Unsupported{Version,ReverseEndian,MapLimit}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub struct Table{pub count:u32,pub offset:u32}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub struct MapItem{pub kind:u16,pub count:u32,pub offset:u32}
#[derive(Debug,PartialEq,Eq)]
pub struct Dex{
    pub version:u16,pub file_size:u32,pub checksum_declared:u32,pub signature_declared:[u8;20],
    pub link:Table,pub data:Table,pub map_offset:u32,
    pub strings:Table,pub types:Table,pub prototypes:Table,pub fields:Table,pub methods:Table,pub classes:Table,
    pub map:Vec<MapItem>,
}
#[derive(Debug,PartialEq,Eq)]
pub enum Verdict{Checked(Dex),Malformed(Issue),Unsupported(Unsupported)}
fn u16_at(b:&[u8],i:usize)->u16{u16::from_le_bytes(b[i..i+2].try_into().unwrap())}
fn u32_at(b:&[u8],i:usize)->u32{u32::from_le_bytes(b[i..i+4].try_into().unwrap())}
fn table(b:&[u8],i:usize)->Table{Table{count:u32_at(b,i),offset:u32_at(b,i+4)}}
fn end(offset:u32,count:u32,width:u64)->u64{u64::from(offset)+u64::from(count)*width}
fn intersects(a:(u64,u64),b:(u64,u64))->bool{a.0<b.1&&b.0<a.1}
pub fn inspect<R:Read+Seek>(s:&mut ReadSession<R>)->io::Result<Verdict>{
    use Issue::*;
    s.cancellation.check()?;
    let length=s.len();
    if length<8{return Ok(Verdict::Malformed(Truncated));}
    let magic=s.read_window(0,8)?.bytes;
    if &magic[..4]!=b"dex\n"||magic[7]!=0{return Ok(Verdict::Malformed(Signature));}
    let version=match &magic[4..7]{
        b"035"=>35,b"037"=>37,b"038"=>38,b"039"=>39,b"040"=>40,
        _=>return Ok(Verdict::Unsupported(Unsupported::Version))
    };
    if length<112{return Ok(Verdict::Malformed(Truncated));}
    let mut h=magic;h.extend(s.read_window(8,104)?.bytes);
    match u32_at(&h,40){
        0x12345678=>{},0x78563412=>return Ok(Verdict::Unsupported(Unsupported::ReverseEndian)),
        _=>return Ok(Verdict::Malformed(Field))
    }
    let file_size=u32_at(&h,32);
    if u64::from(file_size)!=length||u32_at(&h,36)!=112{return Ok(Verdict::Malformed(Field));}
    let link=table(&h,44);let data=table(&h,104);let map_offset=u32_at(&h,52);
    if (link.count==0&&link.offset!=0)||(link.count!=0&&(link.offset<112||end(link.offset,link.count,1)>length)){
        return Ok(Verdict::Malformed(Bounds));
    }
    if data.count==0||data.offset<112||data.offset%4!=0||end(data.offset,data.count,1)!=length||
        map_offset<data.offset||map_offset%4!=0||u64::from(map_offset)+4>length{
        return Ok(Verdict::Malformed(Bounds));
    }
    let tables=[(1u16,table(&h,56),4u64),(2,table(&h,64),4),(3,table(&h,72),12),
        (4,table(&h,80),8),(5,table(&h,88),8),(6,table(&h,96),32)];
    let mut fixed=vec![(0u64,112u64)];
    for &(_,t,w) in &tables{
        if t.count==0{if t.offset!=0{return Ok(Verdict::Malformed(Field));}continue;}
        let e=end(t.offset,t.count,w);
        if t.offset<112||t.offset%4!=0||e>u64::from(data.offset){return Ok(Verdict::Malformed(Bounds));}
        let span=(u64::from(t.offset),e);
        if fixed.iter().any(|&r|intersects(r,span)){return Ok(Verdict::Malformed(Overlap));}
        fixed.push(span);
    }
    let count_bytes=s.read_window(u64::from(map_offset),4)?.bytes;
    let count=u32_at(&count_bytes,0) as usize;
    if count==0{return Ok(Verdict::Malformed(Field));}
    if count>MAX_MAP_ITEMS{return Ok(Verdict::Unsupported(Unsupported::MapLimit));}
    let map_end=u64::from(map_offset)+4+12*count as u64;
    if map_end>length{return Ok(Verdict::Malformed(Bounds));}
    let raw=s.read_window(u64::from(map_offset)+4,count*12)?.bytes;
    let mut seen=BTreeSet::new();let mut map=Vec::with_capacity(count);
    let mut previous=None;let mut known_end=0u64;
    for row in raw.chunks_exact(12){
        s.cancellation.check()?;
        let item=MapItem{kind:u16_at(row,0),count:u32_at(row,4),offset:u32_at(row,8)};
        if u16_at(row,2)!=0||item.count==0||u64::from(item.offset)>=length{return Ok(Verdict::Malformed(Field));}
        if !seen.insert(item.kind){return Ok(Verdict::Malformed(DuplicateType));}
        if previous.is_some_and(|p|item.offset<=p){return Ok(Verdict::Malformed(MapOrder));}
        if u64::from(item.offset)<known_end{return Ok(Verdict::Malformed(Overlap));}
        previous=Some(item.offset);
        known_end=match item.kind{
            0=>{if item.offset!=0||item.count!=1{return Ok(Verdict::Malformed(MapMismatch));}112},
            1..=6=>{
                let (_,t,w)=tables[(item.kind-1) as usize];
                if item.count!=t.count||item.offset!=t.offset{return Ok(Verdict::Malformed(MapMismatch));}
                end(item.offset,item.count,w)
            },
            0x1000=>{
                if item.offset!=map_offset||item.count!=1{return Ok(Verdict::Malformed(MapMismatch));}map_end
            },
            // Call-site and method-handle ID items have fixed size but no
            // classic header pair. This subset does not interpret their contents.
            7|8=>{
                if item.offset<112||item.offset%4!=0{return Ok(Verdict::Malformed(Bounds));}
                let e=end(item.offset,item.count,if item.kind==7{4}else{8});
                if e>length{return Ok(Verdict::Malformed(Bounds));}e
            },
            _=>{
                // Unknown and variable-width kinds are declarations only.
                if item.offset<data.offset{return Ok(Verdict::Malformed(Bounds));}
                u64::from(item.offset)+1
            }
        };
        map.push(item);
    }
    if !seen.contains(&0)||!seen.contains(&0x1000)||tables.iter().any(|(kind,t,_)|t.count!=0&&!seen.contains(kind)){
        return Ok(Verdict::Malformed(MapMismatch));
    }
    s.cancellation.check()?;
    Ok(Verdict::Checked(Dex{version,file_size,checksum_declared:u32_at(&h,8),signature_declared:h[12..32].try_into().unwrap(),
        link,data,map_offset,strings:tables[0].1,types:tables[1].1,prototypes:tables[2].1,
        fields:tables[3].1,methods:tables[4].1,classes:tables[5].1,map}))
}
