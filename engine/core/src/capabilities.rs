//! Static capability registry for the independent Rust core, not Android UI.
//! Recognition is a hint, never proof of structure or authorization to act.
use crate::format::FormatHint;

pub const REGISTRY_VERSION: u32 = 3;
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Operation {
    ProbeSignature, ReadRaw, HashDeclaredBytes, ExportEvidence,
    InspectHeader, ValidateStructure, ListMembers, InterpretResources, InterpretCode,
    Edit, Rebuild, VerifyStructure, Execute,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Support {
    /// Generic byte-level operation; caller must provide authorized stable input.
    GenericBytes,
    /// Only bounded signature hints, not a validated format.
    HintOnly,
    HeaderOnly,
    Unsupported,
    /// Outside the scope of the static analysis core.
    OutOfScope,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Recognition { Unknown, FamilyHint, AmbiguousFamily }
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Descriptor {
    pub hint: FormatHint,
    pub id: &'static str,
    pub recognition: Recognition,
}
pub const ALL_HINTS: [FormatHint; 19] = {
    use FormatHint::*;
    [Unknown, Zip, DosMz, PortableExecutable, Elf, MachO, MachOFatOrJavaClass,
        Dex, Gzip, Zstd, SevenZip, Rar, OleCompound, Ar, Tar, Pdf, Png, Jpeg, Sqlite]
};
pub const ALL_OPERATIONS: [Operation; 13] = {
    use Operation::*;
    [ProbeSignature, ReadRaw, HashDeclaredBytes, ExportEvidence, InspectHeader, ValidateStructure,
        ListMembers, InterpretResources, InterpretCode, Edit, Rebuild, VerifyStructure, Execute]
};
pub fn describe(hint: FormatHint) -> Descriptor {
    use FormatHint::*;
    use Recognition::{FamilyHint, AmbiguousFamily};
    let (id, recognition) = match hint {
        Unknown => ("unknown", Recognition::Unknown),
        Zip => ("zip", FamilyHint),
        DosMz => ("dos_mz", FamilyHint),
        PortableExecutable => ("pe", FamilyHint),
        Elf => ("elf", FamilyHint),
        MachO => ("mach_o", FamilyHint),
        MachOFatOrJavaClass => ("mach_o_fat_or_java_class", AmbiguousFamily),
        Dex => ("dex", FamilyHint),
        Gzip => ("gzip", FamilyHint),
        Zstd => ("zstd", FamilyHint),
        SevenZip => ("7z", FamilyHint),
        Rar => ("rar", FamilyHint),
        OleCompound => ("ole_compound", FamilyHint),
        Ar => ("ar", FamilyHint),
        Tar => ("tar", FamilyHint),
        Pdf => ("pdf", FamilyHint),
        Png => ("png", FamilyHint),
        Jpeg => ("jpeg", FamilyHint),
        Sqlite => ("sqlite", FamilyHint),
    };
    Descriptor { hint, id, recognition }
}
/// A capability describes implementation in this Rust library only.
/// It does not certify inputs or waive authorization, resource limits,
/// cancellation or export privacy policy. No operation dispatch occurs here.
pub fn support(hint: FormatHint, operation: Operation) -> Support {
    use Operation::*;
    match operation {
        ProbeSignature => Support::HintOnly,
        ReadRaw | HashDeclaredBytes | ExportEvidence => Support::GenericBytes,
        InspectHeader if matches!(hint, FormatHint::Elf | FormatHint::Png | FormatHint::PortableExecutable | FormatHint::Dex | FormatHint::Zip) => Support::HeaderOnly,
        InspectHeader => Support::Unsupported,
        ValidateStructure | ListMembers | InterpretResources | InterpretCode |
        Edit | Rebuild | VerifyStructure => Support::Unsupported,
        Execute => Support::OutOfScope,
    }
}
pub fn by_id(id: &str) -> Option<Descriptor> {
    ALL_HINTS.into_iter().map(describe).find(|d| d.id == id)
}
