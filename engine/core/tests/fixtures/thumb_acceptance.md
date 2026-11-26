## Thumb linked acceptance fixture

Original synthetic ARMv7 Thumb assembly. Assembled and linked locally using clang, ld.lld, llvm-objdump and readelf; no binary execution.

```sh
clang --target=armv7-linux-gnueabihf -c thumb_acceptance.s -o corpus.o
ld.lld -m armelf_linux_eabi -Ttext=0x1000 -e fixture corpus.o -o corpus.elf
llvm-objdump -d corpus.elf
readelf -r corpus.elf
```

Observed ELF32 little ARM, no remaining relocations. Exact interval [0x1000,0x1040), 32 halfwords, 24 instructions (8 wide), one deliberately unknown wide encoding at 0x103a. Target of three direct branches: 0x103e. ITE EQ and ITT NE contain a mix of 16/32-bit instructions. Tests compare raw words, width, address, operands, declared IT conditions, all 23 internal instruction splits, invalid cuts, bounded file reads and cancellation. No full legality/ISA proof or execution.
