use negrodroid_core::{Cancellation,ReadSession,x86_decode::{self,Mode,Op,Target,Stop,Error,MAX_BYTES}};
use std::io::{self,Cursor};
fn one(m:Mode,pc:u64,b:&[u8])->Op{x86_decode::decode(m,pc,b).unwrap().instructions[0].op}
#[test]
fn mixed_width_exact_raw_bytes(){
    let b=[0x90,0xb8,0x78,0x56,0x34,0x12,0x50,0x58,0xc3];
    let p=x86_decode::decode(Mode::X86,0x1000,&b).unwrap();
    assert_eq!(p.stop,Stop::Complete);assert_eq!(p.consumed,b.len());
    assert_eq!(p.instructions.iter().map(|i|i.address).collect::<Vec<_>>(),[0x1000,0x1001,0x1006,0x1007,0x1008]);
    assert_eq!(p.instructions[1].bytes,&b[1..6]);
    assert_eq!(p.instructions[1].op,Op::MoveImmediate{register:0,width:32,value:0x12345678});
}
#[test]
fn mode_distinguishes_rex_and_inc_dec(){
    assert_eq!(one(Mode::X86,0,&[0x48]),Op::IncDec{decrement:true,register:0});
    assert_eq!(x86_decode::decode(Mode::X64,0,&[0x48]).unwrap().stop,Stop::Truncated{offset:0});
    assert_eq!(one(Mode::X64,0,&[0x49,0xb8,1,2,3,4,5,6,7,8]),Op::MoveImmediate{register:8,width:64,value:0x0807060504030201});
    assert_eq!(one(Mode::X64,0,&[0x41,0xbf,1,0,0,0]),Op::MoveImmediate{register:15,width:32,value:1});
}
#[test]
fn push_pop_register_widths(){
    for mode in [Mode::X86,Mode::X64]{for pop in [false,true]{for reg in 0..8u8{
        assert_eq!(one(mode,0,&[0x50|((pop as u8)<<3)|reg]),Op::PushPop{pop,register:reg,width:if mode==Mode::X64{64}else{32}});
    }}}
    assert_eq!(one(Mode::X64,0,&[0x41,0x5f]),Op::PushPop{pop:true,register:15,width:64});
}
#[test]
fn signed_branch_relative_to_next_instruction(){
    assert_eq!(one(Mode::X64,0x1000,&[0xe8,1,0,0,0]),Op::Branch{call:true,condition:None,target:Target::Address(0x1006)});
    assert_eq!(one(Mode::X86,0x1000,&[0xe9,0xfb,0xff,0xff,0xff]),Op::Branch{call:false,condition:None,target:Target::Address(0x1000)});
    assert_eq!(one(Mode::X64,0x1000,&[0xeb,0xfe]),Op::Branch{call:false,condition:None,target:Target::Address(0x1000)});
}
#[test]
fn all_short_and_near_conditions(){
    for c in 0..16u8{
        assert_eq!(one(Mode::X64,0x1000,&[0x70|c,2]),Op::Branch{call:false,condition:Some(c),target:Target::Address(0x1004)});
        assert_eq!(one(Mode::X86,0x1000,&[0x0f,0x80|c,0xfa,0xff,0xff,0xff]),Op::Branch{call:false,condition:Some(c),target:Target::Address(0x1000)});
    }
}
#[test]
fn unsupported_never_guesses_length(){
    for suffix in [&[0x66,0x90][..],&[0x8f,0xc0,0x90],&[0x0f,0x1f,0x00],&[0x48,0x90],&[0xc5,0xf8,0x77],&[0xf2,0x90]]{
        let mut b=vec![0x90];b.extend(suffix);
        let p=x86_decode::decode(Mode::X64,0,&b).unwrap();
        assert_eq!(p.stop,Stop::Unsupported{offset:1});assert_eq!(p.consumed,1);assert_eq!(p.instructions.len(),1);
    }
}
#[test]
fn truncated_instruction_never_emits_partial(){
    let full=[0x49,0xb8,1,2,3,4,5,6,7,8];
    for n in 1..full.len(){let p=x86_decode::decode(Mode::X64,0,&full[..n]).unwrap();
        assert_eq!(p.stop,Stop::Truncated{offset:0});assert!(p.instructions.is_empty());}
    assert_eq!(x86_decode::decode(Mode::X86,0,&[0x90,0x0f]).unwrap().stop,Stop::Truncated{offset:1});
}
#[test]
fn target_overflow_and_window_limits(){
    assert_eq!(one(Mode::X86,0,&[0xeb,0x80]),Op::Branch{call:false,condition:None,target:Target::Overflow});
    assert_eq!(one(Mode::X86,u32::MAX as u64-1,&[0xeb,0]),Op::Branch{call:false,condition:None,target:Target::Overflow});
    assert_eq!(x86_decode::decode(Mode::X86,u32::MAX as u64,&[0x90,0x90]),Err(Error::AddressOverflow));
    assert_eq!(x86_decode::decode(Mode::X64,u64::MAX,&[0x90]),Err(Error::AddressOverflow));
    assert_eq!(x86_decode::decode(Mode::X64,0,&[]),Err(Error::Length));
    assert_eq!(x86_decode::decode(Mode::X64,0,&vec![0x90;MAX_BYTES+1]),Err(Error::Length));
}
#[test]
fn read_exact_budget_even_on_unsupported(){
    let c=Cancellation::default();let mut s=ReadSession::new(Cursor::new([0xff,0x90,0x8f,0xc0]),4,3,c.clone());
    let p=x86_decode::read(&mut s,1,Mode::X64,0x1000,3).unwrap();
    assert_eq!(p.stop,Stop::Unsupported{offset:1});assert_eq!(s.remaining_budget(),0);
    c.cancel();assert_eq!(x86_decode::read(&mut s,1,Mode::X64,0x1000,1).unwrap_err().kind(),io::ErrorKind::Interrupted);
}
#[test]
fn simple_words_and_rex_exclusion(){
    assert_eq!(one(Mode::X64,0,&[0x90]),Op::Nop);
    assert_eq!(one(Mode::X64,0,&[0xc3]),Op::Return);
    assert_eq!(one(Mode::X64,0,&[0xcc]),Op::Breakpoint);
    assert_eq!(x86_decode::decode(Mode::X64,0,&[0x40,0x41,0x50]).unwrap().stop,Stop::Unsupported{offset:0});
}
