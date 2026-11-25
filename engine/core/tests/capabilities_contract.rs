use negrodroid_core::{capabilities::{*, Recognition, Support, Operation}, format::FormatHint};
use std::collections::BTreeSet;

#[test]
fn registry_has_unique_round_trippable_ids() {
    let ids: BTreeSet<_> = ALL_HINTS.into_iter().map(|h| describe(h).id).collect();
    assert_eq!(ids.len(),19);
    for h in ALL_HINTS { assert_eq!(by_id(describe(h).id),Some(describe(h))); }
}
#[test]
fn unknown_ids_do_not_guess_from_extensions() {
    for id in ["APK","apk","jar","exe","msi","dmg",""] { assert!(by_id(id).is_none()); }
    assert_eq!(describe(FormatHint::Unknown).recognition,Recognition::Unknown);
}
#[test]
fn ambiguous_magic_never_becomes_java_or_macho_certainty() {
    assert_eq!(describe(FormatHint::MachOFatOrJavaClass).recognition,Recognition::AmbiguousFamily);
    for h in ALL_HINTS { assert_eq!(support(h,Operation::ProbeSignature),Support::HintOnly); }
}
#[test]
fn raw_capabilities_do_not_require_known_format() {
    for h in ALL_HINTS {
        for op in [Operation::ReadRaw,Operation::HashDeclaredBytes,Operation::ExportEvidence] {
            assert_eq!(support(h,op),Support::GenericBytes);
        }
    }
}
#[test]
fn parser_and_mutation_capabilities_are_not_claimed() {
    for h in ALL_HINTS {
        for op in [Operation::ValidateStructure,Operation::ListMembers,Operation::InterpretResources,
            Operation::InterpretCode,Operation::Edit,Operation::Rebuild,Operation::VerifyStructure] {
            assert_eq!(support(h,op),Support::Unsupported);
        }
    }
}
#[test]
fn executing_inputs_is_out_of_scope() {
    for h in ALL_HINTS { assert_eq!(support(h,Operation::Execute),Support::OutOfScope); }
}
#[test]
fn family_ids_are_not_specific_container_claims() {
    use FormatHint::*;
    for (h,id) in [(Zip,"zip"),(OleCompound,"ole_compound"),(Ar,"ar"),(PortableExecutable,"pe")] {
        assert_eq!(describe(h).id,id);
        assert_eq!(describe(h).recognition,Recognition::FamilyHint);
    }
}
#[test]
fn registry_version_and_matrix_dimensions() {
    assert_eq!(REGISTRY_VERSION,3);
    assert_eq!(ALL_OPERATIONS.len(),13);
    assert_eq!(ALL_HINTS.len(),19);
}

#[test]
fn five_families_have_header_checks_not_full_validation(){
    for h in ALL_HINTS {
        let expected=if matches!(h,FormatHint::Elf|FormatHint::Png|FormatHint::PortableExecutable|FormatHint::Dex|FormatHint::Zip){Support::HeaderOnly}else{Support::Unsupported};
        assert_eq!(support(h,Operation::InspectHeader),expected);
        assert_eq!(support(h,Operation::ValidateStructure),Support::Unsupported);
    }
}
