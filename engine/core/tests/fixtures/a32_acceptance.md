## A32 linked acceptance fixture
Original synthetic ARMv7 assembly, assembled locally and linked without execution. Reproduce from this directory:

```sh
clang --target=armv7-linux-gnueabihf -c a32_acceptance.s -o corpus.o
ld.lld -m armelf_linux_eabi -Ttext=0x1000 -e fixture corpus.o -o corpus.elf
llvm-objdump -d corpus.elf
readelf -r corpus.elf
```

Observed ELF32 little ARM, no remaining relocations. 27 words in [0x1000,0x106c), conditional branch and BL target 0x1068, deliberate unknown word 0xffffffff at 0x1064. The tests compare raw words, conditions, all typed operands, 26 internal splits, nonzero source offset, budget and cancellation. No execution or full ISA proof.
