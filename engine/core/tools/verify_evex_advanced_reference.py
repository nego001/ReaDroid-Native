import re, subprocess, tempfile
from pathlib import Path
cases=[]
def add(asm, expected):
    cases.append((asm, bytes(expected)))
for size,typ,p1,bc,p2 in [(4,'DWORD',0x6c,16,0xda),(8,'QWORD',0xed,8,0xda)]:
    name='vaddps' if size==4 else 'vaddpd'
    for disp8 in range(-128,128):
        d=disp8*size
        # zero displacement is encoded without displacement in canonical assembly.
        modrm=0x08 if d==0 else 0x48
        add(f'{name} zmm1{{k2}}{{z}}, zmm2, {typ} PTR [rax{d:+d}]{{1to{bc}}}', [0x62,0xf1,p1,p2,0x58,modrm]+([] if d==0 else [disp8&255]))
    for d in [-129*size,128*size,1,-1]:
        add(f'{name} zmm1{{k2}}{{z}}, zmm2, {typ} PTR [rax{d:+d}]{{1to{bc}}}', [0x62,0xf1,p1,p2,0x58,0x88]+list(d.to_bytes(4,'little',signed=True)))
for name,opcode in [('kandw',0x41),('korw',0x45),('kxorw',0x47)]:
    for d in range(8):
        for a in range(8):
            for b in range(8):
                add(f'{name} k{d}, k{a}, k{b}',[0xc5,0x80|((~a&15)<<3)|4,opcode,0xc0|(d<<3)|b])
for d in range(8):
    for a in range(8):
        add(f'knotw k{d}, k{a}',[0xc5,0xf8,0x44,0xc0|(d<<3)|a])
with tempfile.TemporaryDirectory() as td:
    p=Path(td)
    (p/'ref.s').write_text('.intel_syntax noprefix\n.text\n'+''.join(f'case_{i:04d}:\n {a}\n' for i,(a,e) in enumerate(cases)))
    subprocess.run(['as','--64','-o',str(p/'ref.o'),str(p/'ref.s')],check=True)
    subprocess.run(['objcopy','-O','binary','-j','.text',str(p/'ref.o'),str(p/'ref.bin')],check=True)
    data=(p/'ref.bin').read_bytes()
    expected=b''.join(e for _,e in cases)
    if data!=expected:
        off=0
        for i,(a,e) in enumerate(cases):
            if data[off:off+len(e)]!=e:
                raise AssertionError((i,a,e.hex(' '),data[off:off+len(e)].hex(' ')))
            off+=len(e)
        raise AssertionError('length mismatch')
    disasm=subprocess.check_output(['objdump','-d','-Mintel','--insn-width=16',str(p/'ref.o')],text=True)
    count=len(re.findall(r'^\s*[0-9a-f]+:\s+(?:[0-9a-f]{2}\s+)+',disasm,re.M))
    assert count==len(cases),(count,len(cases))
    print(f'PASS: {len(cases)} assembly encodings; {count} disassembly rows; {len(data)} bytes')
    print('broadcast 520; ternary masks 1536; unary masks 64')
