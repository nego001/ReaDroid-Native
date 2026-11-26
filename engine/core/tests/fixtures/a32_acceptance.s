.syntax unified
.arm
.text
.global fixture
fixture:
 nop
 mov r0, #255
 add r1, r0, #1
 cmp r1, #7
 subne r2, r1, r0, lsr #3
 mov r3, r2, rrx
 add r4, r3, r2, lsl r1
 mul r5, r4, r3
 mla r6, r5, r4, r3
 umull r7, r8, r5, r6
 smlal r9, r10, r5, r6
 ldr r0, [sp, #16]
 strb r1, [sp, #-7]
 ldr r2, [r3, r4, lsl #2]
 ldr r2, [r3, #8]!
 strb r2, [r3], #-7
 stmdb sp!, {r0-r3,lr}
 ldmia sp!, {r0-r3,lr}
 ldrh r2, [r3, #172]
 ldrsb r2, [r3, r4]
 ldrsh r2, [r3, #-172]
 beq done
 bl done
 bx lr
 blx r3
 .inst 0xffffffff
done:
 bx lr
