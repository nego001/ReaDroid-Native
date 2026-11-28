//! Local typed context projection, not an AI client or instruction source.
//! No paths, hashes, raw bytes, arbitrary strings or error messages.
use crate::{Cancellation,format::FormatHint,orchestration::{Report,RunState,Summary},
    parallel::Status,reporting::{validate_report,ExportError},structural::{Header,Issue,Verdict}};
pub const CONTEXT_VERSION:u32=1;
pub const MAX_CONTEXT_ITEMS:usize=128;
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Error { InvalidPage, InconsistentReport, Cancelled }
impl From<ExportError> for Error{
    fn from(_:ExportError)->Self{Self::InconsistentReport}
}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Observation { ObservedDeclaredBytes, Failed, Cancelled, NotStarted }
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum HeaderEvidence { NotRequested, Unavailable, Unsupported, Malformed(Issue), CheckedSubset(Header) }
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub struct Evidence {
    /// Ordinal within the original report only; not a global identifier.
    pub ordinal:usize,
    pub declared_length:u64,
    pub format_hint:FormatHint,
    pub observation:Observation,
    pub charged_bytes:u64,
    pub header:HeaderEvidence,
}
#[derive(Debug,Clone,PartialEq,Eq)]
pub struct Context {
    pub version:u32,
    pub summary:Summary,
    pub state:RunState,
    pub items:Vec<Evidence>,
    pub next:Option<usize>,
}
/// Project one deterministic page from an already-produced report. The after
/// cursor is the preceding page's last ordinal; None initially. The report
/// must remain unchanged between pages. Evidence is not proof of safety.
pub fn project(report:&Report,after:Option<usize>,limit:usize,cancel:&Cancellation)->Result<Context,Error>{
    if limit==0||limit>MAX_CONTEXT_ITEMS||after.is_some_and(|n|n==0||n>report.inventory.len()){
        return Err(Error::InvalidPage);
    }
    if cancel.is_cancelled(){return Err(Error::Cancelled);}
    validate_report(report)?;
    let offset=after.unwrap_or(0);
    let mut items=Vec::with_capacity(limit.min(report.inventory.len()-offset));
    for (i,(key,entry)) in report.inventory.iter().enumerate().skip(offset).take(limit){
        if cancel.is_cancelled(){return Err(Error::Cancelled);}
        let d=report.diagnostics.get(key).ok_or(Error::InconsistentReport)?;
        let observation=match d.status{
            Status::Observed=>Observation::ObservedDeclaredBytes,
            Status::Failed(_)=>Observation::Failed,
            Status::Cancelled=>Observation::Cancelled,
            Status::NotStarted=>Observation::NotStarted,
        };
        let header=match d.header{
            Some(Verdict::HeaderChecked(h))=>HeaderEvidence::CheckedSubset(h),
            Some(Verdict::Malformed(i))=>HeaderEvidence::Malformed(i),
            Some(Verdict::Unsupported)=>HeaderEvidence::Unsupported,
            None if !report.headers_enabled()=>HeaderEvidence::NotRequested,
            None=>HeaderEvidence::Unavailable,
        };
        items.push(Evidence{ordinal:i+1,declared_length:entry.declared_length.ok_or(Error::InconsistentReport)?,
            format_hint:entry.format_hint,observation,charged_bytes:d.charged_bytes,header});
    }
    if cancel.is_cancelled(){return Err(Error::Cancelled);}
    let end=offset+items.len();
    Ok(Context{version:CONTEXT_VERSION,summary:report.summary,state:report.summary.state(),items,
        next:if end<report.inventory.len(){Some(end)}else{None}})
}
