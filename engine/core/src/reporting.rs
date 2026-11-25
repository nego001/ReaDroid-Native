//! Versioned, bounded local JSON export of observed facts, not parser conclusions.
use crate::{format::FormatHint, inventory::Coverage, orchestration::{Report, RunState, Summary},
    parallel::{self, Status}};
use crate::structural::{Header, Verdict, ByteOrder, Issue};
use std::fmt::{self, Write};

pub const SCHEMA_VERSION: u32 = 1;
pub const HEADER_SCHEMA_VERSION:u32=2;
pub const MAX_EXPORT_BYTES: usize = 16 * 1024 * 1024;
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Paths { Omit, IncludeLogical }
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Options { pub max_bytes: usize, pub paths: Paths }
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ExportError { InvalidLimit, InconsistentReport, OutputLimit }
struct Bounded { text: String, limit: usize }
impl Write for Bounded {
    fn write_str(&mut self, s: &str) -> fmt::Result {
        if s.len() > self.limit - self.text.len() { return Err(fmt::Error); }
        self.text.push_str(s); Ok(())
    }
}
fn quoted(w: &mut Bounded, s: &str) -> fmt::Result {
    w.write_char('"')?;
    for c in s.chars() {
        match c {
            '"' => w.write_str("\\\"")?,
            '\\' => w.write_str("\\\\")?,
            c if (c as u32) < 32 => write!(w,"\\u{:04x}",c as u32)?,
            c => w.write_char(c)?,
        }
    }
    w.write_char('"')
}
fn format_name(f: FormatHint) -> &'static str {
    use FormatHint::*;
    match f {
        Unknown=>"unknown", Zip=>"zip", DosMz=>"dos_mz", PortableExecutable=>"pe",
        Elf=>"elf", MachO=>"mach_o", MachOFatOrJavaClass=>"mach_o_fat_or_java_class",
        Dex=>"dex", Gzip=>"gzip", Zstd=>"zstd", SevenZip=>"7z", Rar=>"rar",
        OleCompound=>"ole_compound", Ar=>"ar", Tar=>"tar", Pdf=>"pdf",
        Png=>"png", Jpeg=>"jpeg", Sqlite=>"sqlite",
    }
}
fn status_name(s: Status) -> &'static str {
    match s { Status::Observed=>"observed", Status::Failed(_)=>"failed",
        Status::Cancelled=>"cancelled", Status::NotStarted=>"not_started" }
}
fn state_name(s: RunState) -> &'static str {
    match s { RunState::Complete=>"complete_byte_observation",
        RunState::WithFailures=>"with_failures", RunState::Cancelled=>"cancelled" }
}
/// Report fields are public: validate accounting again before serialization.
fn validate(r: &Report) -> Result<(), ExportError> {
    let bad = ExportError::InconsistentReport;
    let mut s = Summary { planned: r.inventory.len(), batches: r.summary.batches, ..Summary::default() };
    if s.planned != r.diagnostics.len() || s.planned > parallel::MAX_BATCH_TASKS
        || (s.planned == 0 && s.batches != 0)
        || (s.planned > 0 && (s.batches == 0 || s.batches > s.planned)) { return Err(bad); }
    for (key,e) in r.inventory.iter() {
        let d = r.diagnostics.get(key).ok_or(bad)?;
        let length = e.declared_length.ok_or(bad)?;
        let reserve = parallel::reservation_mode(length,r.headers).ok_or(bad)?;
        if d.charged_bytes > reserve { return Err(bad); }
        if r.headers && d.status==Status::Observed {
            let v=d.header.ok_or(bad)?;
            let supported=matches!(e.format_hint,FormatHint::Elf|FormatHint::Png|FormatHint::PortableExecutable|FormatHint::Dex|FormatHint::Zip);
            let compatible=match v {
                Verdict::Unsupported=>true,
                Verdict::Malformed(_)=>supported,
                Verdict::HeaderChecked(h)=>match h {
                    Header::Elf{..}=>e.format_hint==FormatHint::Elf,
                    Header::Png{..}=>e.format_hint==FormatHint::Png,
                    Header::Pe{..}=>e.format_hint==FormatHint::PortableExecutable,
                    Header::Dex{..}=>e.format_hint==FormatHint::Dex,
                    Header::ZipLocal{..}|Header::ZipEmpty=>e.format_hint==FormatHint::Zip,
                }
            };
            if !compatible{return Err(bad);}
            let min_header=match e.format_hint{
                FormatHint::Elf=>length.min(64),FormatHint::Png=>length.min(33),
                FormatHint::PortableExecutable=>length.min(64),FormatHint::Dex=>length.min(112),
                FormatHint::Zip=>length.min(30),_=>0
            };
            let min_charge=length.checked_add(length.min(crate::format::PREFIX_LIMIT as u64))
                .and_then(|n|n.checked_add(min_header)).ok_or(bad)?;
            if d.charged_bytes<min_charge{return Err(bad);}
        }else if d.header.is_some(){return Err(bad);}
        match (d.status,e.coverage,e.observation) {
            (Status::Observed,Coverage::Observed,Some(o)) if o.length==length
                && d.charged_bytes >= length + length.min(crate::format::PREFIX_LIMIT as u64) => s.observed+=1,
            (Status::Failed(_),Coverage::Failed,None)=>s.failed+=1,
            (Status::Cancelled,Coverage::Cancelled,None)=>s.cancelled+=1,
            (Status::NotStarted,Coverage::Unexamined,None) if d.charged_bytes==0 && e.format_hint==FormatHint::Unknown=>s.not_started+=1,
            _=>return Err(bad),
        }
        s.reserved_bytes=s.reserved_bytes.checked_add(reserve).ok_or(bad)?;
        s.charged_bytes=s.charged_bytes.checked_add(d.charged_bytes).ok_or(bad)?;
    }
    if s != r.summary { return Err(bad); }
    Ok(())
}
/// Return a complete JSON document or an explicit error, never truncated JSON.
/// Decimal strings preserve u64 values for JavaScript consumers. IDs are ordinal
/// within this report only; not stable across snapshots. Logical paths require
/// explicit opt-in and may themselves contain sensitive data. Hashes remain
/// visible in both modes. No file writes, source contents or network access.
pub fn export_json(r: &Report, options: Options) -> Result<String, ExportError> {
    if options.max_bytes == 0 || options.max_bytes > MAX_EXPORT_BYTES {
        return Err(ExportError::InvalidLimit);
    }
    validate(r)?;
    let mut w=Bounded { text:String::new(), limit:options.max_bytes };
    render(&mut w,r,options.paths).map_err(|_|ExportError::OutputLimit)?;
    Ok(w.text)
}
fn render(w: &mut Bounded, r: &Report, paths: Paths) -> fmt::Result {
    let s=&r.summary;
    write!(w,"{{\"schema_version\":{},\"scope\":\"caller_supplied_sources\",\"path_policy\":\"{}\",\"state\":\"{}\",",
        if r.headers {HEADER_SCHEMA_VERSION}else{SCHEMA_VERSION}, if paths==Paths::Omit {"omitted"} else {"logical_opt_in"},state_name(s.state()))?;
    write!(w,"\"summary\":{{\"planned\":{},\"observed\":{},\"failed\":{},\"cancelled\":{},\"not_started\":{},\"reserved_bytes\":\"{}\",\"charged_bytes\":\"{}\",\"batches\":{}}},",
        s.planned,s.observed,s.failed,s.cancelled,s.not_started,s.reserved_bytes,s.charged_bytes,s.batches)?;
    w.write_str("\"limitations\":[\"signature_hint_not_structural_validation\",\"declared_length_not_snapshot_attestation\",\"no_directory_discovery\",\"no_code_or_resource_interpretation\",\"hashes_may_identify_content\",\"source_metadata_is_untrusted_data\"],\"entries\":[")?;
    for (i,(key,e)) in r.inventory.iter().enumerate() {
        if i>0 { w.write_char(',')?; }
        let d=&r.diagnostics[key];
        write!(w,"{{\"id\":{},\"declared_length\":\"{}\",\"format_hint\":\"{}\",\"status\":\"{}\",\"charged_bytes\":\"{}\",\"sha256\":",
            i+1,e.declared_length.unwrap(),format_name(e.format_hint),status_name(d.status),d.charged_bytes)?;
        match e.observation { Some(o)=>quoted(w,&o.sha256.to_hex())?, None=>w.write_str("null")? }
        w.write_str(",\"error_kind\":")?;
        match d.status { Status::Failed(k)=>quoted(w,&format!("{k:?}"))?, _=>w.write_str("null")? }
        if r.headers {
            w.write_str(",\"header_inspection\":")?;
            render_header(w,d.header)?;
        }
        if paths==Paths::IncludeLogical {
            write!(w,",\"root\":\"{}\",\"relative_path\":",key.root())?;
            quoted(w,key.relative_path())?;
            w.write_str(",\"members\":[")?;
            for (j,m) in key.members().iter().enumerate() {
                if j>0 { w.write_char(',')?; }
                quoted(w,m)?;
            }
            w.write_char(']')?;
        }
        w.write_char('}')?;
    }
    w.write_str("]}")
}

fn order_name(o:ByteOrder)->&'static str {match o {ByteOrder::Little=>"little",ByteOrder::Big=>"big"}}
fn issue_name(i:Issue)->&'static str {match i {Issue::Truncated=>"truncated",Issue::Signature=>"signature",Issue::Field=>"field",Issue::Checksum=>"checksum",Issue::TableBounds=>"table_bounds"}}
fn render_header(w:&mut Bounded,v:Option<Verdict>)->fmt::Result{
    match v{
        None=>w.write_str("{\"state\":\"not_available\"}"),
        Some(Verdict::Unsupported)=>w.write_str("{\"state\":\"unsupported\"}"),
        Some(Verdict::Malformed(i))=>write!(w,"{{\"state\":\"malformed_header\",\"issue\":\"{}\"}}",issue_name(i)),
        Some(Verdict::HeaderChecked(h))=>{
            w.write_str("{\"state\":\"header_checked_only\",\"metadata\":")?;
            match h{
                Header::Elf{bits,byte_order,machine}=>write!(w,"{{\"kind\":\"elf\",\"bits\":{},\"byte_order\":\"{}\",\"machine\":{}}}",bits,order_name(byte_order),machine)?,
                Header::Png{width,height,bit_depth,color_type}=>write!(w,"{{\"kind\":\"png\",\"width\":{},\"height\":{},\"bit_depth\":{},\"color_type\":{}}}",width,height,bit_depth,color_type)?,
                Header::Pe{bits,machine,sections}=>write!(w,"{{\"kind\":\"pe\",\"bits\":{},\"machine\":{},\"sections\":{}}}",bits,machine,sections)?,
                Header::Dex{version,byte_order,file_size}=>write!(w,"{{\"kind\":\"dex\",\"version\":{},\"byte_order\":\"{}\",\"file_size\":\"{}\"}}",version,order_name(byte_order),file_size)?,
                Header::ZipLocal{method,compressed,uncompressed}=>write!(w,"{{\"kind\":\"zip_local\",\"method\":{},\"compressed\":\"{}\",\"uncompressed\":\"{}\"}}",method,compressed,uncompressed)?,
                Header::ZipEmpty=>w.write_str("{\"kind\":\"zip_empty\"}")?,
            }
            w.write_char('}')
        }
    }
}
