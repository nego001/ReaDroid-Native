.text
.global fixture
fixture:
.Lfixture:
 nop
 movz x0, #0x1234
 movk x0, #0xabcd, lsl #16
 add x1, sp, #16
 sub x2, x1, x0, lsr #3
 and x3, x2, #0xff
 orr x4, x3, x2, ror #5
 ubfm x5, x4, #4, #15
 extr x6, x5, x4, #8
 madd x7, x6, x5, x4
 sdiv x8, x7, x6
 lslv x9, x8, x7
 adr x10, .Lfixture
 adrp x11, .Lfixture
 ldr x12, [sp, #16]
 stur w13, [sp, #-4]
 ldp x14, x15, [sp, #32]
 fadd s0, s1, s2
 fsqrt d3, d4
 add v5.4s, v6.4s, v7.4s
 eor v8.16b, v9.16b, v10.16b
 cbz x0, done
 tbz x1, #39, done
 b.eq done
 bl done
 b done
 br x16
 blr x17
 ldr x18, literal
 .inst 0xffffffff
done:
 ret
 .p2align 3
literal:
 .quad 0x0123456789abcdef
