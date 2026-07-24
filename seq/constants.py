from dataclasses import dataclass
from typing import Final


SEQ_NUM_CHANNELS: Final[int] = 16
TATUMS_PER_BEAT: Final[int] = 48
DEFAULT_TEMPO: Final[int] = 120


type WriteableBuffer = bytearray | memoryview
type ReadableBuffer = bytes | bytearray | memoryview


@dataclass(frozen=True)
class BitField:
    opcode_mask: int
    operand_mask: int


BITFIELDS: dict[int, BitField] = {
    n: BitField(
        opcode_mask=0xFF ^ ((1 << n) - 1),
        operand_mask=(1 << n) - 1,
    )
    for n in (3, 4, 6)
}
