START:
    LD A, 0x0F
    OUT (0x03), A

LOOP:
    IN A, (0x00)
    OUT (0x01), A
    JP LOOP