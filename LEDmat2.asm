IOsetup:
    LD A, 0x4F
    OUT (02), A
    LD A, 0x0F
    OUT (03), A
    RET

display:
    LD DE, 0x0F00
    JUMP:
        LD A, (0x00F0)
        ADD A, 0x10
        OUT (0x01), A
        LD A, (0x00F1)
        ADD A, 0x20
        OUT (0x01), A
        LD A, (0x00F2)
        ADD A, 0x40
        OUT (0x01), A
        LD A, (0x00F3)
        ADD A, 0x80
        OUT (0x01), A
        DEC DE
        JP NZ JUMP
    RET

START:
    CALL IOsetup
    LD A, 0x00
    LD B, 0x00

LOOP:
    LD (0x00F0), A
    INC A
    LD (0x00F1), A
    INC A
    LD (0x00F2), A
    INC A
    LD (0x00F3), A
    INC A
    CALL display
    LD C, 0xFF
    LD B, A
    SUB A, 0x0D
    LD A, B
    JP M, LOOP
    JP START




; End of program

