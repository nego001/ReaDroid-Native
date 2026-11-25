//! Exact UTF-8 byte budgeting for a private, typed JSON context candidate.
//! No tokenizer, model invocation, source strings, paths, digests or network.
use crate::{Cancellation,capabilities::describe,context::{Evidence,HeaderEvidence,Error as ContextError},
    classification::{Family,RecognitionScope,Coverage,StructuralScope},
    orchestration::{Report,RunState},segmentation::{segment_report,Config,SegmentedPage},
    structural::{Header,ByteOrder,Issue}};
use std::fmt::{self,Write};

pub const WIRE_VERSION:u32=1;
pub const MAX_CONTEXT_BYTES:usize=128*1024;
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Error{InvalidLimit,BudgetTooSmall,Context(ContextError)}
impl From<ContextError> for Error{fn from(e:ContextError)->Self{Self::Context(e)}}
#[derive(Debug,Clone,PartialEq,Eq)]
pub struct BudgetedPage{
    page:SegmentedPage,
    encoded_bytes:usize,
}
impl BudgetedPage{
    pub fn page(&self)->&SegmentedPage{&self.page}
    pub fn encoded_bytes(&self)->usize{self.encoded_bytes}
}
struct Counter{used:usize,limit:usize}
impl Write for Counter{
    fn write_str(&mut self,s:&str)->fmt::Result{
        let next=self.used.checked_add(s.len()).ok_or(fmt::Error)?;
        if next>self.limit{return Err(fmt::Error);}
        self.used=next;Ok(())
    }
}
fn state(v:RunState)->&'static str{
    match v{RunState::Complete=>"complete_byte_observation",RunState::WithFailures=>"with_failures",RunState::Cancelled=>"cancelled"}
}
fn family(v:Family)->&'static str{
    match v{Family::Unknown=>"unknown",Family::Ambiguous=>"ambiguous",Family::ExecutableFamily=>"executable_family",
        Family::BytecodeFamily=>"bytecode_family",Family::ArchiveFamily=>"archive_family",Family::CompressionFamily=>"compression_family",
        Family::CompoundDocumentFamily=>"compound_document_family",Family::DocumentFamily=>"document_family",
        Family::ImageFamily=>"image_family",Family::DatabaseFamily=>"database_family"}
}
fn recognition(v:RecognitionScope)->&'static str{
    match v{RecognitionScope::Unknown=>"unknown",RecognitionScope::FamilyHint=>"family_hint",RecognitionScope::AmbiguousFamilyHint=>"ambiguous_family_hint"}
}
fn coverage(v:Coverage)->&'static str{
    match v{Coverage::DeclaredBytesObserved=>"declared_bytes_observed",Coverage::ReadFailed=>"read_failed",
        Coverage::Interrupted=>"interrupted",Coverage::NotStarted=>"not_started"}
}
fn structure(v:StructuralScope)->&'static str{
    match v{StructuralScope::NotRequested=>"not_requested",StructuralScope::Unavailable=>"unavailable",
        StructuralScope::Unsupported=>"unsupported",StructuralScope::MalformedSubset=>"malformed_subset",StructuralScope::CheckedSubset=>"checked_subset"}
}
fn order(v:ByteOrder)->&'static str{match v{ByteOrder::Little=>"little",ByteOrder::Big=>"big"}}
fn issue(v:Issue)->&'static str{
    match v{Issue::Truncated=>"truncated",Issue::Signature=>"signature",Issue::Field=>"field",Issue::Checksum=>"checksum",Issue::TableBounds=>"table_bounds"}
}
fn cursor(w:&mut impl Write,v:Option<usize>)->fmt::Result{
    match v{Some(n)=>write!(w,"{n}"),None=>w.write_str("null")}
}
fn header(w:&mut impl Write,h:HeaderEvidence)->fmt::Result{
    match h{
        HeaderEvidence::NotRequested=>w.write_str(r#"{"state":"not_requested"}"#),
        HeaderEvidence::Unavailable=>w.write_str(r#"{"state":"unavailable"}"#),
        HeaderEvidence::Unsupported=>w.write_str(r#"{"state":"unsupported"}"#),
        HeaderEvidence::Malformed(i)=>write!(w,r#"{{"state":"malformed_subset","issue":"{}"}}"#,issue(i)),
        HeaderEvidence::CheckedSubset(h)=>{
            w.write_str(r#"{"state":"checked_subset","metadata":"#)?;
            match h{
                Header::Elf{bits,byte_order,machine}=>write!(w,r#"{{"kind":"elf","bits":{bits},"byte_order":"{}","machine":{machine}}}"#,order(byte_order))?,
                Header::Png{width,height,bit_depth,color_type}=>write!(w,r#"{{"kind":"png","width":{width},"height":{height},"bit_depth":{bit_depth},"color_type":{color_type}}}"#)?,
                Header::Pe{bits,machine,sections}=>write!(w,r#"{{"kind":"pe","bits":{bits},"machine":{machine},"sections":{sections}}}"#)?,
                Header::Dex{version,byte_order,file_size}=>write!(w,r#"{{"kind":"dex","version":{version},"byte_order":"{}","file_size":{file_size}}}"#,order(byte_order))?,
                Header::ZipLocal{method,compressed,uncompressed}=>write!(w,r#"{{"kind":"zip_local","method":{method},"compressed":{compressed},"uncompressed":{uncompressed}}}"#)?,
                Header::ZipEmpty=>w.write_str(r#"{"kind":"zip_empty"}"#)?,
            }
            w.write_char('}')
        }
    }
}
fn item(w:&mut impl Write,e:&Evidence)->fmt::Result{
    // All string values are static enum labels, not source-controlled strings.
    write!(w,r#"{{"ordinal":{},"format_hint":"{}","declared_length":"{}","charged_bytes":"{}","header":"#,
        e.ordinal,describe(e.format_hint).id,e.declared_length,e.charged_bytes)?;
    header(w,e.header)?;w.write_char('}')
}
/// Single canonical writer used for exact measurement and future export.
/// Input is internal to the budget module; public callers cannot inject strings.
pub(crate) fn write_page(w:&mut impl Write,p:&SegmentedPage)->fmt::Result{
    let s=p.summary;let c=p.counts;
    write!(w,r#"{{"wire_version":{},"scope":"static_evidence_only","state":"{}","summary":{{"planned":{},"observed":{},"failed":{},"cancelled":{},"not_started":{},"reserved_bytes":"{}","charged_bytes":"{}","batches":{}}},"page_counts":{{"observed":{},"failed":{},"cancelled":{},"not_started":{},"unknown_hint":{},"family_hint":{},"ambiguous_hint":{},"not_requested":{},"unavailable":{},"unsupported":{},"malformed_subset":{},"checked_subset":{}}},"after":"#,
        WIRE_VERSION,state(p.state),s.planned,s.observed,s.failed,s.cancelled,s.not_started,s.reserved_bytes,s.charged_bytes,s.batches,
        c.observed,c.failed,c.cancelled,c.not_started,c.unknown_hint,c.family_hint,c.ambiguous_hint,c.not_requested,c.unavailable,c.unsupported,c.malformed_subset,c.checked_subset)?;
    cursor(w,p.after)?;
    write!(w,r#","included":{},"next":"#,p.included)?;cursor(w,p.next)?;
    w.write_str(r#","limitations":["not_full_structure_validation","not_authenticity_or_safety","format_hints_only"],"segments":["#)?;
    for (i,seg) in p.segments.iter().enumerate(){
        if i>0{w.write_char(',')?;}
        let g=seg.group;
        write!(w,r#"{{"family":"{}","recognition":"{}","coverage":"{}","structure":"{}","items":["#,
            family(g.family),recognition(g.recognition),coverage(g.coverage),structure(g.structure))?;
        for (j,e) in seg.items.iter().enumerate(){
            if j>0{w.write_char(',')?;}item(w,e)?;
        }
        w.write_str("]}")?;
    }
    w.write_str("]}")
}
/// Measure an entire canonical document including framing, global summary,
/// local counts, groups, item metadata and cursor. If it does not fit, halve
/// the page size and retry (at most eight projections). This is deliberately
/// not a maximal-packing algorithm. No zero-progress successful page when
/// evidence remains. A too-small single-item or empty document returns Err.
pub fn budget_report(report:&Report,after:Option<usize>,mut config:Config,max_bytes:usize,cancel:&Cancellation)->Result<BudgetedPage,Error>{
    if max_bytes==0||max_bytes>MAX_CONTEXT_BYTES{return Err(Error::InvalidLimit);}
    loop{
        let p=segment_report(report,after,config,cancel)?;
        let mut w=Counter{used:0,limit:max_bytes};
        let fits=write_page(&mut w,&p).is_ok();
        if cancel.is_cancelled(){return Err(ContextError::Cancelled.into());}
        if fits{return Ok(BudgetedPage{page:p,encoded_bytes:w.used});}
        if p.included<=1{return Err(Error::BudgetTooSmall);}
        config.page_items=(p.included/2).max(1);
    }
}
#[cfg(test)]
mod tests{
    use super::*;
    use crate::{inventory::SourceKey,orchestration::{run,run_with_headers,Config as RunConfig},parallel::Task};
    use std::io::Cursor;
    fn config()->Config{Config{page_items:128,segment_items:32}}
    fn run_cfg()->RunConfig{RunConfig{workers:2,batch_size:16,byte_budget:u64::MAX}}
    fn uniform(n:usize)->Report{
        run((0..n).map(|i|Task{key:SourceKey::physical(1,&format!("private/{i:04}")).unwrap(),reader:Cursor::new(b"abc"),length:3}).collect(),run_cfg(),Cancellation::default()).unwrap()
    }
    fn render(b:&BudgetedPage)->String{
        let mut s=String::new();write_page(&mut s,b.page()).unwrap();s
    }
    #[test]
    fn exact_measurement_and_privacy(){
        let r=uniform(8);let b=budget_report(&r,None,config(),MAX_CONTEXT_BYTES,&Cancellation::default()).unwrap();
        let s=render(&b);assert_eq!(b.encoded_bytes(),s.len());assert!(s.starts_with(r#"{"wire_version":1,"scope":"static_evidence_only""#));
        assert!(!s.contains("private/"));assert!(!s.contains(&r.inventory.iter().next().unwrap().1.observation.unwrap().sha256.to_hex()));
        assert_eq!(b.page().included,8);
    }
    #[test]
    fn one_item_exact_boundary_and_no_progress_error(){
        let r=uniform(1);let c=Cancellation::default();let b=budget_report(&r,None,config(),MAX_CONTEXT_BYTES,&c).unwrap();
        let n=b.encoded_bytes();assert_eq!(budget_report(&r,None,config(),n,&c).unwrap(),b);
        assert_eq!(budget_report(&r,None,config(),n-1,&c),Err(Error::BudgetTooSmall));
    }
    #[test]
    fn small_budget_reduces_pages_and_preserves_every_ordinal(){
        let r=uniform(259);let c=Cancellation::default();
        let cap=budget_report(&r,None,Config{page_items:8,segment_items:32},MAX_CONTEXT_BYTES,&c).unwrap().encoded_bytes()+20;
        let mut after=None;let mut all=Vec::new();
        loop{
            let b=budget_report(&r,after,config(),cap,&c).unwrap();
            assert!(b.encoded_bytes()<=cap);assert!(b.page().included>0&&b.page().included<128);
            assert_eq!(render(&b).len(),b.encoded_bytes());assert_eq!(b.page().summary,r.summary);
            all.extend(b.page().segments.iter().flat_map(|s|s.items.iter().map(|e|e.ordinal)));
            assert!(all.len()<=259);
            match b.page().next{Some(n)=>after=Some(n),None=>break}
        }
        assert_eq!(all,(1..=259).collect::<Vec<_>>());
    }
    #[test]
    fn empty_document_still_requires_framing_budget(){
        let r=uniform(0);let c=Cancellation::default();
        let b=budget_report(&r,None,config(),MAX_CONTEXT_BYTES,&c).unwrap();
        assert_eq!(b.page().included,0);assert_eq!(b.page().next,None);
        assert_eq!(budget_report(&r,None,config(),b.encoded_bytes()-1,&c),Err(Error::BudgetTooSmall));
    }
    #[test]
    fn invalid_limits_and_cancelled_requests(){
        let r=uniform(1);let c=Cancellation::default();
        for n in [0,MAX_CONTEXT_BYTES+1,usize::MAX]{assert_eq!(budget_report(&r,None,config(),n,&c),Err(Error::InvalidLimit));}
        assert_eq!(budget_report(&r,None,Config{page_items:0,segment_items:1},1000,&c),Err(Error::Context(ContextError::InvalidPage)));
        c.cancel();assert_eq!(budget_report(&r,None,config(),1000,&c),Err(Error::Context(ContextError::Cancelled)));
    }
    #[test]
    fn structural_metadata_and_u64_decimal_strings_measured(){
        let c=Cancellation::default();
        let r=run_with_headers(vec![Task{key:SourceKey::physical(1,"x").unwrap(),reader:Cursor::new(b"\x89PNG\r\n\x1a\n".as_slice()),length:8}],run_cfg(),c.clone()).unwrap();
        let b=budget_report(&r,None,config(),MAX_CONTEXT_BYTES,&c).unwrap();
        assert!(render(&b).contains(r#""header":{"state":"malformed_subset","issue":"truncated"}"#));
        c.cancel();let r=run(vec![Task{key:SourceKey::physical(1,"x").unwrap(),reader:Cursor::new(b""),length:9_007_199_254_740_993}],run_cfg(),c).unwrap();
        let b=budget_report(&r,None,config(),MAX_CONTEXT_BYTES,&Cancellation::default()).unwrap();
        assert!(render(&b).contains(r#""declared_length":"9007199254740993""#));
    }
    #[test]
    fn all_header_variants_have_exact_measurement(){
        let cases=[Header::Elf{bits:64,byte_order:ByteOrder::Little,machine:62},
            Header::Png{width:u32::MAX,height:1,bit_depth:8,color_type:6},Header::Pe{bits:32,machine:332,sections:1},
            Header::Dex{version:35,byte_order:ByteOrder::Little,file_size:112},Header::ZipLocal{method:8,compressed:10,uncompressed:100},Header::ZipEmpty];
        for h in cases{
            let mut s=String::new();header(&mut s,HeaderEvidence::CheckedSubset(h)).unwrap();
            let mut c=Counter{used:0,limit:s.len()};header(&mut c,HeaderEvidence::CheckedSubset(h)).unwrap();
            assert_eq!(c.used,s.len());assert!(s.ends_with("}}"));
            let mut c=Counter{used:0,limit:s.len()-1};assert!(header(&mut c,HeaderEvidence::CheckedSubset(h)).is_err());
        }
    }
}
