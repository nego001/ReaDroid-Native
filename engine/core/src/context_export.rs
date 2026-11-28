//! Explicit local context export. No file writes, model calls or network.
//! The caller must obtain appropriate authorization; the decision enum is
//! not a user-authentication mechanism. Exported evidence is untrusted data.
use crate::{Cancellation,context,context_budget,context_guard::PreparedContext};

#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Decision { Deny, AllowLocal }
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Error { Denied, Cancelled, Encoding(context_budget::Error) }
#[derive(Debug,Clone,PartialEq,Eq)]
pub struct ExportedContext {
    json:String,
    included:usize,
    next:Option<usize>,
}
impl ExportedContext{
    pub fn as_str(&self)->&str{&self.json}
    pub fn into_string(self)->String{self.json}
    pub fn encoded_bytes(&self)->usize{self.json.len()}
    pub fn included(&self)->usize{self.included}
    pub fn next(&self)->Option<usize>{self.next}
}
/// Return only complete compact JSON, from an opaque PreparedContext.
/// No arbitrary input JSON, source text, prompts or destination parameters.
/// The original budget includes all policy labels and framing. No implicit
/// upload, logging or file output. Caller owns subsequent handling.
pub fn export_json(prepared:&PreparedContext,decision:Decision,cancel:&Cancellation)->Result<ExportedContext,Error>{
    if decision!=Decision::AllowLocal{return Err(Error::Denied);}
    if cancel.is_cancelled(){return Err(Error::Cancelled);}
    let json=prepared.encode().map_err(Error::Encoding)?;
    if cancel.is_cancelled(){return Err(Error::Cancelled);}
    if json.len()!=prepared.encoded_bytes(){
        return Err(Error::Encoding(context_budget::Error::Context(context::Error::InconsistentReport)));
    }
    Ok(ExportedContext{json,included:prepared.included(),next:prepared.next()})
}
