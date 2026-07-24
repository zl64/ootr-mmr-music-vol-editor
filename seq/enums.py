from enum import Enum, auto
import struct


class SeqVersion(Enum):
    OCARINA_OF_TIME = auto()
    MAJORAS_MASK = auto()


class SeqSection(Enum):
    HEADER = auto()
    CHANNEL = auto()
    NOTE_LAYER = auto()


ALL_VERSIONS = tuple(SeqVersion)
ALL_SECTIONS = tuple(SeqSection)


class Endian(Enum):
    BIG = '>'
    LITTLE = '<'


class DataType(Enum):
    U8 = ('B', False)
    S8 = ('b', True)
    U16 = ('H', False)
    S16 = ('h', True)
    COMPRESSED_U16 = (None, False)

    def __init__(self, fmt: str | None, is_signed: bool) -> None:
        self.fmt: str = fmt
        self.size: int = struct.calcsize('=' + fmt) if fmt else None
        self.is_signed: bool = is_signed