## A64 linked acceptance fixture

Source: `aarch64_acceptance.s` (original synthetic assembly). Generated locally using clang 17.0.0, LLD 17.0.0, llvm-objdump and readelf, no binary execution.

```sh
clang --target=aarch64-linux-gnu -c aarch64_acceptance.s -o corpus.o
ld.lld -m aarch64elf -Ttext=0x1000 -e fixture --no-relax corpus.o -o corpus.elf
llvm-objdump -d corpus.elf
readelf -r corpus.elf
```

Linked ELF had no relocations. The Rust fixture uses exactly 31 words at 0x1000..0x107c (exclusive), deliberately excludes alignment padding at 0x107c and literal data at 0x1080. Explicit unknown word at 0x1074. Known direct branch target 0x1078 and literal target 0x1080. Tests assert typed operands, raw words, addresses, all 30 internal page splits, budget and cancellation. This is a reproducible selected-subset acceptance fixture, not a claim of full A64 coverage or a differential test over all ISA encodings.
