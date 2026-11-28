//! Deterministic contiguous segmentation of classified evidence.
//! No ranking by risk, semantic inference, source text or network.
use crate::{Cancellation,classification::{classify_report,Family,RecognitionScope,Coverage,StructuralScope,PageCounts},
    context::{Evidence,Error,MAX_CONTEXT_ITEMS},orchestration::{Report,Summary,RunState}};

pub const SEGMENTATION_VERSION:u32=1;
pub const MAX_SEGMENT_ITEMS:usize=32;
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub struct Config {pub page_items:usize,pub segment_items:usize}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub struct Group {
    pub family:Family,pub recognition:RecognitionScope,pub coverage:Coverage,pub structure:StructuralScope,
}
#[derive(Debug,Clone,PartialEq,Eq)]
pub struct Segment {pub group:Group,pub items:Vec<Evidence>}
#[derive(Debug,Clone,PartialEq,Eq)]
pub struct SegmentedPage {
    pub version:u32,
    pub summary:Summary,
    pub state:RunState,
    /// Page-local counts, not full-report totals.
    pub counts:PageCounts,
    pub after:Option<usize>,
    pub included:usize,
    pub segments:Vec<Segment>,
    pub next:Option<usize>,
}
/// Group adjacent evidence with identical descriptive classification, splitting
/// on the segment size cap or page boundary. Never reorder, drop or duplicate
/// items. Cursor is report-local; keep the underlying report immutable.
/// This grouping is not a token or byte budget and is not a safety verdict.
pub fn segment_report(report:&Report,after:Option<usize>,config:Config,cancel:&Cancellation)->Result<SegmentedPage,Error>{
    if config.page_items==0||config.page_items>MAX_CONTEXT_ITEMS||
        config.segment_items==0||config.segment_items>MAX_SEGMENT_ITEMS{
        return Err(Error::InvalidPage);
    }
    let page=classify_report(report,after,config.page_items,cancel)?;
    if page.context.items.len()!=page.classifications.len(){return Err(Error::InconsistentReport);}
    let included=page.context.items.len();
    let mut segments:Vec<Segment>=Vec::new();
    for (e,c) in page.context.items.into_iter().zip(page.classifications){
        if cancel.is_cancelled(){return Err(Error::Cancelled);}
        if e.ordinal!=c.ordinal{return Err(Error::InconsistentReport);}
        let group=Group{family:c.family,recognition:c.recognition,coverage:c.coverage,structure:c.structure};
        if let Some(last)=segments.last_mut(){
            if last.group==group && last.items.len()<config.segment_items{
                last.items.push(e);
                continue;
            }
        }
        segments.push(Segment{group,items:vec![e]});
    }
    if cancel.is_cancelled(){return Err(Error::Cancelled);}
    Ok(SegmentedPage{version:SEGMENTATION_VERSION,summary:page.context.summary,state:page.context.state,
        counts:page.counts,after,included,segments,next:page.context.next})
}
