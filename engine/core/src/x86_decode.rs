//! Deliberately limited x86 legacy/long-mode decoder. An unsupported opcode
//! or prefix stops the window at its starting byte; no guessed length or
//! resynchronization. Static metadata only, not execution or full ISA proof.
use crate::ReadSession;
use std::io::{self,Read,Seek};
pub const MAX_BYTES:usize=4096;
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Mode{X86,X64}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Target{Address(u64),Overflow}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Base{None,Register(u8),Rip}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub struct Memory{pub base:Base,pub index:Option<u8>,pub scale:u8,pub displacement:i64,pub rip_target:Option<Target>}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Operand{Register(u8),HighByte(u8),Memory(Memory)}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum BinaryKind{Mov,Add,Or,Adc,Sbb,And,Sub,Xor,Cmp,Test}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum UnaryKind{Inc,Dec,Call,Jump,Push,Not,Neg,Mul,Imul,Div,Idiv}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub struct Immediate{pub encoded_bits:u8,pub raw:u64,pub value:u64}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Op{
    Nop,Return,Breakpoint,
    BinaryImmediate{kind:BinaryKind,width:u8,operand:Operand,immediate:Immediate},
    Unary{kind:UnaryKind,width:u8,operand:Operand},
    Binary{kind:BinaryKind,width:u8,destination:Operand,source:Operand},
    Lea{width:u8,destination:u8,memory:Memory},
    ExtendMove{signed:bool,destination_width:u8,source_width:u8,destination:u8,source:Operand},
    Multiply{width:u8,destination:u8,source:Operand},
    MultiplyImmediate{width:u8,destination:u8,source:Operand,immediate:Immediate},
    ConditionalMove{condition:u8,width:u8,destination:u8,source:Operand},
    SetCondition{condition:u8,destination:Operand},
    PushPop{pop:bool,register:u8,width:u8},
    IncDec{decrement:bool,register:u8},
    MoveImmediate{register:u8,width:u8,value:u64},
    Branch{call:bool,condition:Option<u8>,target:Target},
}
#[derive(Debug,Clone,PartialEq,Eq)]
pub struct Instruction{pub address:u64,pub bytes:Vec<u8>,pub op:Op}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Stop{Complete,Unsupported{offset:usize},Truncated{offset:usize}}
#[derive(Debug,Clone,PartialEq,Eq)]
pub struct Page{pub instructions:Vec<Instruction>,pub consumed:usize,pub stop:Stop}
#[derive(Debug,Clone,Copy,PartialEq,Eq)]
pub enum Error{Length,AddressOverflow}
fn validate(mode:Mode,pc:u64,n:usize)->Result<(),Error>{
    if n==0||n>MAX_BYTES{return Err(Error::Length);}
    let end=pc.checked_add(n as u64).ok_or(Error::AddressOverflow)?;
    if mode==Mode::X86&&end>u64::from(u32::MAX)+1{return Err(Error::AddressOverflow);}
    Ok(())
}
fn target(mode:Mode,next:u64,delta:i64)->Target{
    let v=i128::from(next)+i128::from(delta);
    let max=if mode==Mode::X86{i128::from(u32::MAX)}else{i128::from(u64::MAX)};
    if v<0||v>max{Target::Overflow}else{Target::Address(v as u64)}
}
#[derive(Debug,Clone,Copy)]
enum Local{Unsupported,Truncated}
fn take(b:&[u8],start:usize,n:usize)->Result<&[u8],Local>{
    b.get(start..start+n).ok_or(Local::Truncated)
}
fn modrm(mode:Mode,pc:u64,b:&[u8],mut i:usize,rex:u8)->Result<(usize,u8,Operand),Local>{
    let m=take(b,i,1)?[0];i+=1;
    let form=m>>6;let raw=m&7;
    let reg=((m>>3)&7)|(((rex>>2)&1)<<3);
    let extension=(rex&1)<<3;
    if form==3{return Ok((i,reg,Operand::Register(raw|extension)));}
    let mut base=Base::Register(raw|extension);
    let mut index=None;let mut scale=1;
    let mut disp32=form==2;
    if raw==4{
        let sib=take(b,i,1)?[0];i+=1;
        let ix=(sib>>3)&7;
        if ix!=4||rex&2!=0{index=Some(ix|(((rex>>1)&1)<<3));scale=1<<(sib>>6);}
        let bs=sib&7;
        base=if form==0&&bs==5{disp32=true;Base::None}else{Base::Register(bs|extension)};
    }else if form==0&&raw==5{
        disp32=true;
        base=if mode==Mode::X64{Base::Rip}else{Base::None};
    }
    let displacement=if disp32{
        let v=u32::from_le_bytes(take(b,i,4)?.try_into().unwrap());i+=4;
        if mode==Mode::X86&&base==Base::None{i64::from(v)}else{i64::from(v as i32)}
    }else if form==1{
        let v=take(b,i,1)?[0] as i8;i+=1;i64::from(v)
    }else{0};
    // Provisional RIP target; trailing-immediate forms must finish it at instruction end.
    let rip_target=if base==Base::Rip{Some(target(mode,pc+i as u64,displacement))}else{None};
    Ok((i,reg,Operand::Memory(Memory{base,index,scale,displacement,rip_target})))
}
fn finish_rip(mode:Mode,pc:u64,end:usize,operand:Operand)->Operand{
    match operand{
        Operand::Memory(mut m) if m.base==Base::Rip=>{
            m.rip_target=Some(target(mode,pc+end as u64,m.displacement));
            Operand::Memory(m)
        }
        _=>operand
    }
}
fn immediate(b:&[u8],i:usize,n:usize,width:u8)->Result<Immediate,Local>{
    let raw=match n{1=>u64::from(take(b,i,1)?[0]),2=>u64::from(u16::from_le_bytes(take(b,i,2)?.try_into().unwrap())),4=>u64::from(u32::from_le_bytes(take(b,i,4)?.try_into().unwrap())),_=>return Err(Local::Unsupported)};
    let extended=if n==1{(raw as i8 as i64) as u64}else if width==64{(raw as i32 as i64) as u64}else{raw};
    Ok(Immediate{encoded_bits:(n*8) as u8,raw,value:match width{8=>extended&255,16=>extended&65535,32=>extended&0xffff_ffff,_=>extended}})
}
// HighByte stores the parent register index (0=AH, 1=CH, 2=DH, 3=BH).
fn byte_register(index:u8,rex:u8)->Operand{
    if rex==0&&(4..8).contains(&index){Operand::HighByte(index-4)}else{Operand::Register(index)}
}
fn byte_operand(operand:Operand,rex:u8)->Operand{
    match operand{Operand::Register(index)=>byte_register(index,rex),_=>operand}
}
fn one(mode:Mode,pc:u64,b:&[u8])->Result<(usize,Op),Local>{
    let mut i=0;
    let mut rex=0u8;
    let override16=b[0]==0x66;
    if override16{i+=1;}
    if mode==Mode::X64&&b.get(i).is_some_and(|v|(0x40..=0x4f).contains(v)){
        rex=b[i];i+=1;
    }
    let opcode=*b.get(i).ok_or(Local::Truncated)?;i+=1;
    // Only one REX and only on the forms explicitly supported below.
    // One 66 before optional single REX on selected operand-width forms.
    let operand_width=if rex&8!=0{64}else if override16{16}else{32};
    if (0xb0..=0xb7).contains(&opcode){
        let raw=u64::from(take(b,i,1)?[0]);
        return Ok((i+1,Op::BinaryImmediate{kind:BinaryKind::Mov,width:8,operand:byte_register((opcode&7)|((rex&1)<<3),rex),immediate:Immediate{encoded_bits:8,raw,value:raw}}));
    }
    if (0xb8..=0xbf).contains(&opcode){
        let width=operand_width;
        let n=match width{64=>8,16=>2,_=>4};
        let raw=take(b,i,n)?;
        let mut padded=[0u8;8];padded[..n].copy_from_slice(raw);
        return Ok((i+n,Op::MoveImmediate{register:(opcode&7)|((rex&1)<<3),width,value:u64::from_le_bytes(padded)}));
    }
    if (0x50..=0x5f).contains(&opcode){
        return Ok((i,Op::PushPop{pop:opcode>=0x58,register:(opcode&7)|((rex&1)<<3),width:if override16{16}else if mode==Mode::X64{64}else{32}}));
    }
    let binary=match opcode{
        0x88..=0x8b=>Some(BinaryKind::Mov),0x00..=0x03=>Some(BinaryKind::Add),
        0x08..=0x0b=>Some(BinaryKind::Or),0x10..=0x13=>Some(BinaryKind::Adc),0x18..=0x1b=>Some(BinaryKind::Sbb),0x20..=0x23=>Some(BinaryKind::And),
        0x28..=0x2b=>Some(BinaryKind::Sub),0x30..=0x33=>Some(BinaryKind::Xor),
        0x38..=0x3b=>Some(BinaryKind::Cmp),0x84|0x85=>Some(BinaryKind::Test),_=>None
    };
    if let Some(kind)=binary{
        let (n,reg,rm)=modrm(mode,pc,b,i,rex)?;
        let width=if opcode&1==0{8}else{operand_width};
        let (reg,rm)=if width==8{(byte_register(reg,rex),byte_operand(rm,rex))}else{(Operand::Register(reg),rm)};
        let (destination,source)=if opcode&2!=0{(reg,rm)}else{(rm,reg)};
        return Ok((n,Op::Binary{kind,width,destination,source}));
    }
    if opcode==0x8d{
        let (n,reg,rm)=modrm(mode,pc,b,i,rex)?;
        let Operand::Memory(memory)=rm else{return Err(Local::Unsupported);};
        return Ok((n,Op::Lea{width:operand_width,destination:reg,memory}));
    }
    // Group selectors are the raw three ModRM bits, not extended by REX.R.
    // This subset conservatively excludes REX.R on group opcodes.
    if matches!(opcode,0x80|0x81|0x83|0xc6|0xc7|0xf6|0xf7|0xff){
        if rex&4!=0{return Err(Local::Unsupported);}
        let selector=(take(b,i,1)?[0]>>3)&7;
        let width=if matches!(opcode,0x80|0xc6|0xf6){8}else{operand_width};
        if opcode==0xff{
            let kind=match selector{0=>UnaryKind::Inc,1=>UnaryKind::Dec,2=>UnaryKind::Call,4=>UnaryKind::Jump,6=>UnaryKind::Push,_=>return Err(Local::Unsupported)};
            let (end,_,operand)=modrm(mode,pc,b,i,rex)?;
            if override16&&matches!(kind,UnaryKind::Call|UnaryKind::Jump){return Err(Local::Unsupported);}
            let width=if matches!(kind,UnaryKind::Call|UnaryKind::Jump|UnaryKind::Push)&&mode==Mode::X64{if override16{16}else{64}}else{width};
            return Ok((end,Op::Unary{kind,width,operand}));
        }
        if matches!(opcode,0xf6|0xf7)&&selector>=2{
            let kind=match selector{2=>UnaryKind::Not,3=>UnaryKind::Neg,4=>UnaryKind::Mul,5=>UnaryKind::Imul,6=>UnaryKind::Div,_=>UnaryKind::Idiv};
            let (end,_,operand)=modrm(mode,pc,b,i,rex)?;
            return Ok((end,Op::Unary{kind,width,operand:if width==8{byte_operand(operand,rex)}else{operand}}));
        }
        let kind=match opcode{
            0x80|0x81|0x83=>[BinaryKind::Add,BinaryKind::Or,BinaryKind::Adc,BinaryKind::Sbb,BinaryKind::And,BinaryKind::Sub,BinaryKind::Xor,BinaryKind::Cmp][selector as usize],
            0xc6|0xc7 if selector==0=>BinaryKind::Mov,
            0xf6|0xf7 if selector==0=>BinaryKind::Test,
            _=>return Err(Local::Unsupported)
        };
        let (at,_,operand)=modrm(mode,pc,b,i,rex)?;
        let operand=if width==8{byte_operand(operand,rex)}else{operand};
        let n=if width==8||opcode==0x83{1}else if width==16{2}else{4};
        let value=immediate(b,at,n,width)?;
        let end=at+n;
        return Ok((end,Op::BinaryImmediate{kind,width,operand:finish_rip(mode,pc,end,operand),immediate:value}));
    }
    if matches!(opcode,0x05|0x0d|0x15|0x1d|0x25|0x2d|0x35|0x3d|0xa9){
        let kind=match opcode{0x05=>BinaryKind::Add,0x0d=>BinaryKind::Or,0x15=>BinaryKind::Adc,0x1d=>BinaryKind::Sbb,
            0x25=>BinaryKind::And,0x2d=>BinaryKind::Sub,0x35=>BinaryKind::Xor,0x3d=>BinaryKind::Cmp,_=>BinaryKind::Test};
        let width=operand_width;
        let n=if width==16{2}else{4};
        let value=immediate(b,i,n,width)?;
        return Ok((i+n,Op::BinaryImmediate{kind,width,operand:Operand::Register(0),immediate:value}));
    }
    // Selected two-byte legacy map; no mandatory F2/F3 or vector maps.
    if opcode==0x0f{
        let secondary=take(b,i,1)?[0];
        if matches!(secondary,0xb6|0xb7|0xbe|0xbf|0xaf|0x40..=0x4f|0x90..=0x9f){
            i+=1;
            // SETcc has a reserved/ignored reg field; accept canonical /0 only.
            if (0x90..=0x9f).contains(&secondary)&&(rex&4!=0||take(b,i,1)?[0]&0x38!=0){
                return Err(Local::Unsupported);
            }
            let (end,reg,rm)=modrm(mode,pc,b,i,rex)?;
            let op=match secondary{
                0xb6|0xb7|0xbe|0xbf=>{
                    let source_width=if secondary&1==0{8}else{16};
                    if source_width>=operand_width{return Err(Local::Unsupported);}
                    Op::ExtendMove{signed:secondary&8!=0,destination_width:operand_width,source_width,destination:reg,source:if source_width==8{byte_operand(rm,rex)}else{rm}}
                },
                0xaf=>Op::Multiply{width:operand_width,destination:reg,source:rm},
                0x40..=0x4f=>Op::ConditionalMove{condition:secondary&15,width:operand_width,destination:reg,source:rm},
                _=>Op::SetCondition{condition:secondary&15,destination:byte_operand(rm,rex)}
            };
            return Ok((end,op));
        }
    }
    if matches!(opcode,0x69|0x6b){
        let (at,reg,rm)=modrm(mode,pc,b,i,rex)?;
        let n=if opcode==0x6b{1}else if operand_width==16{2}else{4};
        let value=immediate(b,at,n,operand_width)?;
        let end=at+n;
        return Ok((end,Op::MultiplyImmediate{width:operand_width,destination:reg,source:finish_rip(mode,pc,end,rm),immediate:value}));
    }
    if rex!=0||override16{return Err(Local::Unsupported);}
    match opcode{
        0x90=>Ok((i,Op::Nop)),
        0xc3=>Ok((i,Op::Return)),
        0xcc=>Ok((i,Op::Breakpoint)),
        0x40..=0x4f if mode==Mode::X86=>Ok((i,Op::IncDec{decrement:opcode>=0x48,register:opcode&7})),
        0xe8|0xe9=>{
            let d=i32::from_le_bytes(take(b,i,4)?.try_into().unwrap());
            let n=i+4;
            Ok((n,Op::Branch{call:opcode==0xe8,condition:None,target:target(mode,pc+n as u64,i64::from(d))}))
        },
        0xeb|0x70..=0x7f=>{
            let d=take(b,i,1)?[0] as i8;
            let n=i+1;
            Ok((n,Op::Branch{call:false,condition:if opcode==0xeb{None}else{Some(opcode&15)},target:target(mode,pc+n as u64,i64::from(d))}))
        },
        0x0f=>{
            let next=take(b,i,1)?[0];i+=1;
            if !(0x80..=0x8f).contains(&next){return Err(Local::Unsupported);}
            let d=i32::from_le_bytes(take(b,i,4)?.try_into().unwrap());
            let n=i+4;
            Ok((n,Op::Branch{call:false,condition:Some(next&15),target:target(mode,pc+n as u64,i64::from(d))}))
        },
        _=>Err(Local::Unsupported)
    }
}
/// Return the verified prefix only, with exact stopping offset. A partial
/// window is never represented as complete. All reads are bounded.
pub fn decode(mode:Mode,pc:u64,bytes:&[u8])->Result<Page,Error>{
    validate(mode,pc,bytes.len())?;
    let mut instructions=Vec::new();let mut i=0;
    while i<bytes.len(){
        match one(mode,pc+i as u64,&bytes[i..]){
            Ok((n,op))=>{
                instructions.push(Instruction{address:pc+i as u64,bytes:bytes[i..i+n].to_vec(),op});
                i+=n;
            },
            Err(Local::Unsupported)=>return Ok(Page{instructions,consumed:i,stop:Stop::Unsupported{offset:i}}),
            Err(Local::Truncated)=>return Ok(Page{instructions,consumed:i,stop:Stop::Truncated{offset:i}}),
        }
    }
    Ok(Page{instructions,consumed:i,stop:Stop::Complete})
}
pub fn read<R:Read+Seek>(s:&mut ReadSession<R>,offset:u64,mode:Mode,pc:u64,size:usize)->io::Result<Page>{
    s.cancellation.check()?;
    validate(mode,pc,size).map_err(|_|io::Error::new(io::ErrorKind::InvalidInput,"invalid x86 window"))?;
    let w=s.read_window(offset,size)?;
    let p=decode(mode,pc,&w.bytes).map_err(|_|io::Error::new(io::ErrorKind::InvalidData,"invalid x86 window"))?;
    s.cancellation.check()?;Ok(p)
}
