.syntax unified
.thumb
.text
.global fixture
.thumb_func
fixture:
 nop
 movs r0, #7
 lsrs r1, r0, #3
 adds r2, r1, r0
 eors r2, r1
 mov r8, r2
 ldrh r3, [r2, #6]
 ldrsb r3, [r2, r1]
 push {r0,r1,lr}
 movw r4, #0x1234
 movt r4, #0xabcd
 addw r5, r4, #0x789
 ldr.w r6, [r5, #0x123]
 ite eq
 moveq r0, #1
 movne r0, #2
 itt ne
 movwne r7, #0x5678
 addne r1, #1
 beq.w done
 bl done
 b.n done
 .inst.w 0xffffffff
done:
 pop {r0,r1,pc}
