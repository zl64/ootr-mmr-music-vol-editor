from dataclasses import dataclass, field

from .byte_stream import ByteStream
from .enums import DataType, SeqSection


@dataclass
class Operand:
    stream: ByteStream
    address: int
    data_type: DataType | None = None
    mask: int | None = None

    @property
    def is_masked(self) -> bool:
        return self.data_type is None and self.mask is not None

    @property
    def value(self) -> int:
        if not self.is_masked:
            return self.stream.read_at(self.data_type, self.address)[0]

        return self.stream[self.address] & self.mask

    @value.setter
    def value(self, x: int) -> None:
        if not self.is_masked:
            self.stream.write_at(self.data_type, self.address, x)
            return

        if x & ~self.mask:
            raise ValueError(x)

        byte = self.stream[self.address]
        byte &= ~self.mask
        byte |= x & self.mask
        self.stream[self.address] = byte


@dataclass
class Instruction:
    stream: ByteStream
    address: int
    opcode: int
    name: str
    section: SeqSection
    operands: list[Operand] = field(default_factory=list)
    is_pointer: bool = False

    def get_operand(self, index: int) -> Operand | None:
        if 0 <= index < len(self.operands):
            return self.operands[index]
        return None


INSTRUCTION_TYPES: dict[str, Instruction] = {}
