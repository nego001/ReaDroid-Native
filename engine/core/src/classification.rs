//! Descriptive evidence classification. No risk scores, malware inference,
//! execution authority, semantic code interpretation or model calls.
use crate::{Cancellation,context::{self,Context,Evidence,HeaderEvidence,Observation,Error},
    capabilities::{describe,Recognition},format::FormatHint,orchestration::Report};

pub const CLASSIFICATION_VERSION:u32=1;
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Family { Unknown, Ambiguous, ExecutableFamily, BytecodeFamily, ArchiveFamily,
    CompressionFamily, CompoundDocumentFamily, DocumentFamily, ImageFamily, DatabaseFamily }
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum RecognitionScope { Unknown, FamilyHint, AmbiguousFamilyHint }
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Coverage { DeclaredBytesObserved, ReadFailed, Interrupted, NotStarted }
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum StructuralScope { NotRequested, Unavailable, Unsupported, MalformedSubset, CheckedSubset }
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub struct Classification {
    pub ordinal:usize,pub family:Family,pub recognition:RecognitionScope,
    pub coverage:Coverage,pub structure:StructuralScope,
}
#[derive(Debug,Default,Clone,Copy,PartialEq,Eq)]
pub struct PageCounts {
    pub observed:usize,pub failed:usize,pub cancelled:usize,pub not_started:usize,
    pub unknown_hint:usize,pub family_hint:usize,pub ambiguous_hint:usize,
    pub not_requested:usize,pub unavailable:usize,pub unsupported:usize,
    pub malformed_subset:usize,pub checked_subset:usize,
}
#[derive(Debug,Clone,PartialEq,Eq)]
pub struct ClassifiedPage {
    pub version:u32,pub context:Context,pub classifications:Vec<Classification>,
    /// Counts apply only to this page; Context.summary applies to the full run.
    pub counts:PageCounts,
}
fn family(h:FormatHint)->Family{
    use FormatHint::*;
    match h{
        Unknown=>Family::Unknown,MachOFatOrJavaClass=>Family::Ambiguous,
        DosMz|PortableExecutable|Elf|MachO=>Family::ExecutableFamily,
        Dex=>Family::BytecodeFamily,Zip|SevenZip|Rar|Ar|Tar=>Family::ArchiveFamily,
        Gzip|Zstd=>Family::CompressionFamily,OleCompound=>Family::CompoundDocumentFamily,
        Pdf=>Family::DocumentFamily,Png|Jpeg=>Family::ImageFamily,Sqlite=>Family::DatabaseFamily,
    }
}
fn classify(e:&Evidence)->Classification{
    let recognition=match describe(e.format_hint).recognition{
        Recognition::Unknown=>RecognitionScope::Unknown,
        Recognition::FamilyHint=>RecognitionScope::FamilyHint,
        Recognition::AmbiguousFamily=>RecognitionScope::AmbiguousFamilyHint,
    };
    let coverage=match e.observation{
        Observation::ObservedDeclaredBytes=>Coverage::DeclaredBytesObserved,
        Observation::Failed=>Coverage::ReadFailed,Observation::Cancelled=>Coverage::Interrupted,
        Observation::NotStarted=>Coverage::NotStarted,
    };
    let structure=match e.header{
        HeaderEvidence::NotRequested=>StructuralScope::NotRequested,
        HeaderEvidence::Unavailable=>StructuralScope::Unavailable,
        HeaderEvidence::Unsupported=>StructuralScope::Unsupported,
        HeaderEvidence::Malformed(_)=>StructuralScope::MalformedSubset,
        HeaderEvidence::CheckedSubset(_)=>StructuralScope::CheckedSubset,
    };
    Classification{ordinal:e.ordinal,family:family(e.format_hint),recognition,coverage,structure}
}
impl PageCounts{
    fn add(&mut self,c:Classification){
        match c.coverage{
            Coverage::DeclaredBytesObserved=>self.observed+=1,Coverage::ReadFailed=>self.failed+=1,
            Coverage::Interrupted=>self.cancelled+=1,Coverage::NotStarted=>self.not_started+=1,
        }
        match c.recognition{
            RecognitionScope::Unknown=>self.unknown_hint+=1,RecognitionScope::FamilyHint=>self.family_hint+=1,
            RecognitionScope::AmbiguousFamilyHint=>self.ambiguous_hint+=1,
        }
        match c.structure{
            StructuralScope::NotRequested=>self.not_requested+=1,StructuralScope::Unavailable=>self.unavailable+=1,
            StructuralScope::Unsupported=>self.unsupported+=1,StructuralScope::MalformedSubset=>self.malformed_subset+=1,
            StructuralScope::CheckedSubset=>self.checked_subset+=1,
        }
    }
}
/// Revalidate the source report through context::project. No input text or
/// arbitrary mutable Context accepted. Classification describes independent
/// dimensions: a malformed subset can coexist with observed declared bytes;
/// a family hint can coexist with a failed full read.
pub fn classify_report(report:&Report,after:Option<usize>,limit:usize,cancel:&Cancellation)->Result<ClassifiedPage,Error>{
    let context=context::project(report,after,limit,cancel)?;
    let mut classifications=Vec::with_capacity(context.items.len());
    let mut counts=PageCounts::default();
    for e in &context.items{
        if cancel.is_cancelled(){return Err(Error::Cancelled);}
        let c=classify(e);counts.add(c);classifications.push(c);
    }
    if cancel.is_cancelled(){return Err(Error::Cancelled);}
    Ok(ClassifiedPage{version:CLASSIFICATION_VERSION,context,classifications,counts})
}
#[cfg(test)]
mod tests{
    use super::*;
    use crate::{capabilities::ALL_HINTS,structural::{Header,Issue}};
    fn e(h:FormatHint)->Evidence{
        Evidence{ordinal:1,declared_length:0,format_hint:h,observation:Observation::ObservedDeclaredBytes,
            charged_bytes:0,header:HeaderEvidence::NotRequested}
    }
    #[test]
    fn all_registry_hints_classified_without_promoting_identity(){
        for hint in ALL_HINTS{
            let c=classify(&e(hint));
            match describe(hint).recognition{
                Recognition::Unknown=>assert_eq!((c.family,c.recognition),(Family::Unknown,RecognitionScope::Unknown)),
                Recognition::AmbiguousFamily=>assert_eq!((c.family,c.recognition),(Family::Ambiguous,RecognitionScope::AmbiguousFamilyHint)),
                Recognition::FamilyHint=>{
                    assert!(!matches!(c.family,Family::Unknown|Family::Ambiguous));
                    assert_eq!(c.recognition,RecognitionScope::FamilyHint);
                }
            }
        }
        assert_eq!(family(FormatHint::Zip),Family::ArchiveFamily);
        assert_eq!(family(FormatHint::Dex),Family::BytecodeFamily);
        assert_eq!(family(FormatHint::Gzip),Family::CompressionFamily);
        assert_eq!(family(FormatHint::OleCompound),Family::CompoundDocumentFamily);
    }
    #[test]
    fn independent_dimensions_preserve_malformed_and_checked_subset(){
        let mut x=e(FormatHint::Png);x.header=HeaderEvidence::Malformed(Issue::Checksum);
        let c=classify(&x);
        assert_eq!(c.coverage,Coverage::DeclaredBytesObserved);assert_eq!(c.structure,StructuralScope::MalformedSubset);
        x.header=HeaderEvidence::CheckedSubset(Header::Png{width:1,height:1,bit_depth:8,color_type:6});
        let c=classify(&x);assert_eq!(c.structure,StructuralScope::CheckedSubset);
        assert_eq!(c.recognition,RecognitionScope::FamilyHint);
    }
}
