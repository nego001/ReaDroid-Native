//! Bounded read-only hexadecimal formatting. F2.2 Java prefix parity at
//! offset zero; nonzero offsets refer to a caller-authorized byte window.
use crate::{ReadSession,MAX_WINDOW_BYTES};
use std::{fmt::Write,io::{self,Read,Seek}};
pub const MAX_HEX_BYTES:usize=4096;
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Error{WindowLimit,OffsetOverflow}
/// Format 16 bytes per row, uppercase hex, printable ASCII only. Minimum
/// eight offset digits, growing beyond 32 bits without truncation. Does not
/// claim file integrity, CRC, encoding detection or full-file coverage.
pub fn format(offset:u64,bytes:&[u8])->Result<String,Error>{
    if bytes.len()>MAX_HEX_BYTES{return Err(Error::WindowLimit);}
    if !bytes.is_empty()&&offset.checked_add((bytes.len()-1) as u64).is_none(){return Err(Error::OffsetOverflow);}
    let mut out=String::with_capacity(bytes.len()*5+32);
    for (row,chunk) in bytes.chunks(16).enumerate(){
        let address=offset+row as u64*16;
        write!(&mut out,"{address:08X}  ").expect("String writer");
        for i in 0..16{
            if let Some(b)=chunk.get(i){write!(&mut out,"{b:02X} ").expect("String writer");}
            else{out.push_str("   ");}
        }
        out.push_str(" |");
        for &b in chunk{out.push(if (32..=126).contains(&b){char::from(b)}else{'.'});}
        out.push_str("|\n");
    }
    Ok(out)
}
#[derive(Debug,PartialEq,Eq)]
pub struct Preview{
    pub offset:u64,pub source_length:u64,pub shown:usize,pub has_before:bool,pub has_after:bool,pub dump:String,
}
/// Read at most 4096 bytes from an existing authorized ReadSession. A short
/// final page is allowed; out-of-range offsets and zero requested size fail.
/// This reads only the specified window and never opens a path or writes.
pub fn preview<R:Read+Seek>(session:&mut ReadSession<R>,offset:u64,requested:usize)->io::Result<Preview>{
    if requested==0||requested>MAX_HEX_BYTES||requested>MAX_WINDOW_BYTES||offset>session.len(){
        return Err(io::Error::new(io::ErrorKind::InvalidInput,"invalid hex window"));
    }
    let size=(session.len()-offset).min(requested as u64) as usize;
    let window=session.read_window(offset,size)?;
    let dump=format(offset,&window.bytes).map_err(|_|io::Error::new(io::ErrorKind::InvalidData,"hex formatting limit"))?;
    Ok(Preview{offset,source_length:session.len(),shown:size,has_before:offset>0,
        has_after:offset+(size as u64)<session.len(),dump})
}
