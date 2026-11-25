//! Isolated C ABI for the JNI shim. The safe core remains forbid(unsafe_code).
#![deny(unsafe_op_in_unsafe_fn)]
use negrodroid_core::hex::{format,MAX_HEX_BYTES};
use std::{panic::{catch_unwind,AssertUnwindSafe},slice,ptr};
const MAX_OUTPUT:usize=86*256+1;
const INVALID:i32=-1;
const SHORT:i32=-2;
const PANIC:i32=-3;

#[no_mangle]
pub extern "C" fn nd_hex_abi_version()->i32{1}

/// Returns ASCII byte length excluding the NUL terminator, or a negative
/// status. Output is untouched on ordinary validation/format failure.
/// # Safety
/// Input points to len readable bytes (may be null only if len=0).
/// Output points to cap writable bytes. Buffers must be valid, nonoverlapping,
/// owned by the caller and stable for this call. No pointer is retained.
/// The JNI shim supplies stack-owned bounded copies, not pinned JVM memory.
#[no_mangle]
pub unsafe extern "C" fn nd_hex_format(input:*const u8,len:usize,offset:i64,out:*mut u8,cap:usize)->i32{
    if len>MAX_HEX_BYTES||offset<0||out.is_null()||cap==0||cap>MAX_OUTPUT||
        (len>0&&(input.is_null()||offset.checked_add((len-1) as i64).is_none())){
        return INVALID;
    }
    let result=catch_unwind(AssertUnwindSafe(||{
        // SAFETY: caller contract above; empty slice avoids null pointer.
        let bytes=if len==0{&[]}else{unsafe{slice::from_raw_parts(input,len)}};
        let text=match format(offset as u64,bytes){Ok(t)=>t,Err(_)=>return INVALID};
        if text.len()>=cap{return SHORT;}
        // SAFETY: output has cap bytes; text is a separate owned allocation.
        unsafe{
            ptr::copy_nonoverlapping(text.as_ptr(),out,text.len());
            out.add(text.len()).write(0);
        }
        text.len() as i32
    }));
    result.unwrap_or(PANIC)
}
#[cfg(test)]
mod tests{
    use super::*;
    #[test]
    fn exact_and_nul(){
        let mut out=[0u8;MAX_OUTPUT];
        let b=[65u8,255];
        let n=unsafe{nd_hex_format(b.as_ptr(),2,0,out.as_mut_ptr(),out.len())};
        let expected=format(0,&b).unwrap();
        assert_eq!(n as usize,expected.len());assert_eq!(&out[..n as usize],expected.as_bytes());
        assert_eq!(out[n as usize],0);
    }
    #[test]
    fn invalid_and_short_do_not_write(){
        let mut out=[42u8;8];let b=[65u8];
        assert_eq!(unsafe{nd_hex_format(b.as_ptr(),1,0,out.as_mut_ptr(),out.len())},SHORT);
        assert_eq!(unsafe{nd_hex_format(b.as_ptr(),4097,0,out.as_mut_ptr(),out.len())},INVALID);
        assert_eq!(unsafe{nd_hex_format(b.as_ptr(),1,-1,out.as_mut_ptr(),out.len())},INVALID);
        assert_eq!(unsafe{nd_hex_format(b.as_ptr(),2,i64::MAX,out.as_mut_ptr(),out.len())},INVALID);
        assert_eq!(out,[42;8]);
    }
    #[test]
    fn empty_input_and_large_offset(){
        let mut out=[0u8;MAX_OUTPUT];
        assert_eq!(unsafe{nd_hex_format(ptr::null(),0,0,out.as_mut_ptr(),out.len())},0);
        let b=[65u8;4096];let n=unsafe{nd_hex_format(b.as_ptr(),b.len(),i64::MAX-4095,out.as_mut_ptr(),out.len())};
        assert!(n>0);assert_eq!(out[n as usize],0);
        assert!(std::str::from_utf8(&out[..n as usize]).unwrap().starts_with("7FFFFFFFFFFFF000"));
    }
}
