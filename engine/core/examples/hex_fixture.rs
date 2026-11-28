//! Deterministic synthetic F2.2 parity fixtures, no user inputs.
use negrodroid_core::hex::format;
use std::io::Write;
fn main(){
    let mode=std::env::args().nth(1).unwrap();
    let bytes:Vec<u8>=match mode.as_str(){
        "empty"=>vec![],
        "single"=>vec![255],
        "boundary"=>{let mut b=vec![0;17];b[0]=65;b[1]=32;b[2]=255;b[16]=90;b},
        "all"=> (0..=255).collect(),
        "max"=> (0..4096).map(|i|(i%256) as u8).collect(),
        _=>panic!("unknown synthetic fixture"),
    };
    std::io::stdout().lock().write_all(format(0,&bytes).unwrap().as_bytes()).unwrap();
}
