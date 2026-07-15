# TODO:
# - Add support for channel volume editing via deltas?
#   Seems like it would be a lot of work... and I am lazy...


from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
import struct
import sys
import tempfile
import zipfile


class SeqVersion(Enum):
    OCARINA_OF_TIME = auto()
    MAJORAS_MASK = auto()


class SeqSection(Enum):
    HEADER = auto()
    CHANNEL = auto()
    NOTE_LAYER = auto()


ALL_VERSIONS = tuple(SeqVersion)
ALL_SECTIONS = tuple(SeqSection)


#region Sequence Parsing
@dataclass(frozen=True)
class BitField:
    opcode_mask: int
    arg_mask: int


BITFIELDS: dict[int, BitField] = {
    n: BitField(
        opcode_mask=0xFF ^ ((1 << n) - 1),
        arg_mask=(1 << n) - 1,
    )
    for n in (3, 4, 6)
}


class ArgType(Enum):
    U8  = ('>B', False)
    S8  = ('>b', True)
    U16 = ('>H', False)
    S16 = ('>h', True)
    VAR = (None, False)

    def __init__(self, fmt: str | None, is_signed: bool) -> None:
        self.fmt: str = fmt
        self.is_signed: bool = is_signed
        self.size: int | None = None if fmt is None else struct.calcsize(fmt)

    def read(self, data: bytes, offset: int) -> tuple[int, int]:
        if self is ArgType.VAR:
            return self._read_var(data, offset)
        return [
            struct.unpack_from(self.fmt, data, offset)[0],
            self.size,
        ]

    @staticmethod
    def _read_var(data: bytes, offset: int) -> tuple[int, int]:
        value = data[offset]

        if value & 0x80:
            value = ((value & 0x7F) << 8) | data[offset + 1]
            return value, 2

        return value, 1

    def write(self, data: bytearray, offset: int, value: int) -> int:
        if self is ArgType.VAR:
            return self._write_var(data, offset, value)
        struct.pack_into(self.fmt, data, offset, value)
        return self.size

    @staticmethod
    def _write_var(data: bytearray, offset: int, value: int) -> int:
        if value < 0x80:
            data[offset:offset+1] = bytes([value])
            return 1

        if value <= 0x7FFF:
            data[offset:offset+2] = bytes([
                ((value >> 8) & 0x7F) | 0x80,
                value & 0xFF,
            ])
            return 2

        raise ValueError(value)


@dataclass
class Spec:
    opcode: int
    name: str
    args: tuple[ArgType, ...] = ()
    bitmask: BitField | None = None
    sections: tuple[SeqSection, ...] = ALL_SECTIONS
    versions: tuple[SeqVersion, ...] = ALL_VERSIONS

    def matches(self, opcode: int, section: SeqSection, version: SeqVersion) -> bool:
        if section not in self.sections:
            return False

        if version not in self.versions:
            return False

        if self.bitmask is None:
            return opcode == self.opcode

        return (opcode & self.bitmask.opcode_mask) == self.opcode


@dataclass
class Arg:
    sequence: 'AudioSequence'
    offset: int


@dataclass
class TypedArg(Arg):
    type: ArgType

    @property
    def value(self) -> int:
        return self.sequence.read(self)

    @value.setter
    def value(self, value):
        self.sequence.write(self, value)


@dataclass
class BitArg(Arg):
    mask: int = 0

    @property
    def value(self) -> int:
        return self.sequence.read(self)

    @value.setter
    def value(self, value):
        self.sequence.write(self, value)


@dataclass
class Message:
    offset: int
    opcode: int
    name: str
    spec: Spec
    section: SeqSection
    args: list[Arg] = field(default_factory=list)

    @property
    def opcode_offset(self) -> int:
        return self.offset

    def get_arg(self, index: int) -> Arg | None:
        if 0 <= index < len(self.args):
            return self.args[index]
        return None


SPECS = [
    # Control Flow
    Spec(0xFF, 'end',),
    Spec(0xFE, 'delay1',),
    Spec(0xFD, 'delay',          args=(ArgType.VAR,),),
    Spec(0xFC, 'call',           args=(ArgType.U16,),),
    Spec(0xFB, 'jump',           args=(ArgType.U16,),),
    Spec(0xFA, 'beqz',           args=(ArgType.U16,),),
    Spec(0xF9, 'bltz',           args=(ArgType.U16,),),
    Spec(0xF8, 'loop',           args=(ArgType.U8,),),
    Spec(0xF7, 'loopend',),
    Spec(0xF6, 'break',),
    Spec(0xF5, 'bgez',           args=(ArgType.U16,),),
    Spec(0xF4, 'rjump',          args=(ArgType.U8,),),
    Spec(0xF3, 'rbeqz',          args=(ArgType.U8,),),
    Spec(0xF2, 'rbltz',          args=(ArgType.U8,),),

    # Non-Argbit
    Spec(0xF1, 'allocnotelist',  args=(ArgType.U8,),              sections=(SeqSection.HEADER,)),
    Spec(0xF0, 'freenotelist',   args=(ArgType.U8,),              sections=(SeqSection.HEADER,)),
    Spec(0xEF, 'ef',             args=(ArgType.S16, ArgType.U8),  sections=(SeqSection.HEADER,)),
    Spec(0xDF, 'transpose',      args=(ArgType.U8,),              sections=(SeqSection.HEADER,)),
    Spec(0xDE, 'rtranspose',     args=(ArgType.U8,),              sections=(SeqSection.HEADER,)),
    Spec(0xDD, 'tempo',          args=(ArgType.U8,),              sections=(SeqSection.HEADER,)),
    Spec(0xDC, 'tempochg',       args=(ArgType.U8,),              sections=(SeqSection.HEADER,)),
    Spec(0xDB, 'vol',            args=(ArgType.U8,),              sections=(SeqSection.HEADER,)),
    Spec(0xDA, 'volmode',        args=(ArgType.U8, ArgType.U16),  sections=(SeqSection.HEADER,)),
    Spec(0xD9, 'volscale',       args=(ArgType.U8,),              sections=(SeqSection.HEADER,)),
    Spec(0xD7, 'initchan',       args=(ArgType.U16,),             sections=(SeqSection.HEADER,)),
    Spec(0xD6, 'freechan',       args=(ArgType.U16,),             sections=(SeqSection.HEADER,)),
    Spec(0xD5, 'mutescale',      args=(ArgType.U8,),              sections=(SeqSection.HEADER,)),
    Spec(0xD4, 'mute',                                            sections=(SeqSection.HEADER,)),
    Spec(0xD3, 'mutebhv',        args=(ArgType.U8,),              sections=(SeqSection.HEADER,)),
    Spec(0xD2, 'ldshortvelarr',  args=(ArgType.U16,),             sections=(SeqSection.HEADER,)),
    Spec(0xD1, 'ldshortgatearr', args=(ArgType.U16,),             sections=(SeqSection.HEADER,)),
    Spec(0xD0, 'notealloc',      args=(ArgType.U8,),              sections=(SeqSection.HEADER,)),
    Spec(0xCE, 'rand',           args=(ArgType.U8,),              sections=(SeqSection.HEADER,)),
    Spec(0xCD, 'dyncall',        args=(ArgType.U16,),             sections=(SeqSection.HEADER,)),
    Spec(0xCC, 'ldi',            args=(ArgType.U8,),              sections=(SeqSection.HEADER,)),
    Spec(0xC9, 'and',            args=(ArgType.U8,),              sections=(SeqSection.HEADER,)),
    Spec(0xC8, 'sub',            args=(ArgType.U8,),              sections=(SeqSection.HEADER,)),
    Spec(0xC7, 'stseq',          args=(ArgType.U8, ArgType.U16,), sections=(SeqSection.HEADER,)),
    Spec(0xC6, 'stop',                                            sections=(SeqSection.HEADER,)),
    Spec(0xC5, 'scriptctr',      args=(ArgType.U16,),             sections=(SeqSection.HEADER,)),
    Spec(0xC4, 'runseq',         args=(ArgType.U8, ArgType.U8),   sections=(SeqSection.HEADER,)),
    # MM ONLY
    Spec(0xC3, 'c3',             args=(ArgType.U16,),             sections=(SeqSection.HEADER,), versions=(SeqVersion.MAJORAS_MASK,)),
    Spec(0xC2, 'c2',             args=(ArgType.S16,),             sections=(SeqSection.HEADER,), versions=(SeqVersion.MAJORAS_MASK,)),

    # Argbit
    Spec(0xB0, 'ldseq',          args=(ArgType.U8, ArgType.U16,), sections=(SeqSection.HEADER,), bitmask=BITFIELDS[4],),
    Spec(0xA0, 'rldchan',        args=(ArgType.S16,),             sections=(SeqSection.HEADER,), bitmask=BITFIELDS[4],),
    Spec(0x90, 'ldchan',         args=(ArgType.U16,),             sections=(SeqSection.HEADER,), bitmask=BITFIELDS[4],),
    Spec(0x80, 'ldio',                                            sections=(SeqSection.HEADER,), bitmask=BITFIELDS[3],),
    Spec(0x70, 'stio',                                            sections=(SeqSection.HEADER,), bitmask=BITFIELDS[3],),
    Spec(0x60, 'ldres',          args=(ArgType.U8, ArgType.U8,),  sections=(SeqSection.HEADER,), bitmask=BITFIELDS[4],),
    Spec(0x50, 'subio',                                           sections=(SeqSection.HEADER,), bitmask=BITFIELDS[3],),
    Spec(0x40, 'stopchan',                                        sections=(SeqSection.HEADER,), bitmask=BITFIELDS[4],),
    Spec(0x00, 'testchan',                                        sections=(SeqSection.HEADER,), bitmask=BITFIELDS[4],),
]


class Header:
    def __init__(self) -> None:
        self.messages: list[Message] = []

    def get_message(self, opcode: int) -> Message | None:
        for msg in self.messages:
            if msg.opcode == opcode:
                return msg
        return None

    def get_all_messages(self, opcode: int) -> list[Message]:
        return [
            msg
            for msg in self.messages
            if msg.opcode == opcode
        ]


class AudioSequence:
    def __init__(self, seq_path: Path, seq_version: SeqVersion):
        self.data = bytearray(seq_path.read_bytes())
        self.version = seq_version
        self.header = Header()

        self.messages: list[Message] = []

    def get_all(self, opcode: int, section: SeqSection) -> list[Message]:
        return [
            msg
            for msg in self.messages
            if msg.opcode == opcode
            and (section is not None or msg.section == section)
        ]

    def read(self, arg: Arg):
        if isinstance(arg, TypedArg):
            return arg.type.read(self.data, arg.offset)[0]

        if isinstance(arg, BitArg):
            return self.data[arg.offset] & arg.mask

        raise TypeError()

    def write(self, arg: Arg, value: int):
        if isinstance(arg, TypedArg):
            old_size = arg.type.read(self.data, arg.offset)[1]
            new_size = arg.type.write(self.data, arg.offset, value)

            if new_size != old_size:
                delta = new_size - old_size
                self.update_offsets(arg.offset, delta)

        elif isinstance(arg, BitArg):
            if value & ~arg.mask:
                raise ValueError(f"{value:#x} does not fit into bit field {arg.mask:#x}")

            byte = self.data[arg.offset]
            byte &= ~arg.mask
            byte |= value & arg.mask
            self.data[arg.offset] = byte

        else:
            raise TypeError()

    def update_offsets(self, offset: int, delta: int):
        ...

    def parse_header(self):
        pos = 0

        while True:
            msg_offset = pos
            opcode = self.data[pos]
            pos += 1

            for spec in SPECS:
                if spec.matches(opcode, SeqSection.HEADER, self.version):
                    break
            else:
                raise ValueError(f"Encountered unknown opcode {opcode:#x}")

            args = []

            if spec.bitmask:
                args.append(
                    BitArg(
                        sequence=self,
                        offset=msg_offset,
                        mask=spec.bitmask.arg_mask,
                    )
                )

            for arg_type in spec.args:
                size = arg_type.read(self.data, pos)[1]

                args.append(
                    TypedArg(
                        sequence=self,
                        type=arg_type,
                        offset=pos,
                    )
                )

                pos += size

            self.header.messages.append(
                Message(
                    offset=msg_offset,
                    opcode=opcode,
                    name=spec.name,
                    spec=spec,
                    section=SeqSection.HEADER,
                    args=args,
                )
            )

            if spec.opcode == 0xFF:
                break
#endregion Sequence Parsing


#region Archive Editing
class ArchiveHandler:
    def __init__(self, archive_path: Path):
        self.original_path: Path = archive_path
        self.sequences: list[Path] = []

        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def __enter__(self):
        self.unpack()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            if exc_type is None:
                self.pack()
        finally:
            self.temp_dir.cleanup()

    def unpack(self) -> None:
        with zipfile.ZipFile(self.original_path, 'r') as arc:
            arc.extractall(self.temp_path)

        for f in self.temp_path.rglob('*'):
            if f.is_file() and f.suffix.lower() in {'.aseq', '.seq', '.zseq'}:
                self.sequences.append(f)

    def pack(self):
        temp_archive = self.original_path.with_name(
            self.original_path.stem + 'tmp.zip'
        )

        try:
            with zipfile.ZipFile(temp_archive, 'w', zipfile.ZIP_DEFLATED) as arc:
                for f in self.temp_path.rglob('*'):
                    if f.is_file():
                        arc.write(f, f.relative_to(self.temp_path))

            temp_archive.replace(self.original_path)

        finally:
            if temp_archive.exists():
                temp_archive.unlink()


def modify_volume(seq_file: Path, seq_version: SeqVersion, new_volume: int):
    seq = AudioSequence(seq_file, seq_version)
    seq.parse_header()

    vol_msgs: list[Message] = seq.header.get_all_messages(0xDB)

    for msg in vol_msgs:
        arg = msg.get_arg(0)
        if arg:
            arg.value = new_volume

    seq_file.write_bytes(seq.data)
#endregion Archive Editing


def parse_volume(value: str) -> int:
    value = value.strip().lower()

    if value.endswith('%'):
        percent = float(value[:-1])

        if not 0 <= percent <= 200:
            raise ValueError()

        return round(percent / 200 * 255)

    number = int(value, 0)

    if not 0 <= number <= 255:
        raise ValueError()

    return number


def parse_args(argv: list[str]) -> tuple[Path, int]:
    if len(argv) != 3:
        raise ValueError()

    archive = Path(argv[1]).resolve()
    volume = parse_volume(argv[2])

    return archive, volume


if __name__ == '__main__':
    archive, new_volume = parse_args(sys.argv)

    ext = archive.suffix.lower()
    match ext:
        case '.ootrs':
            seq_version = SeqVersion.OCARINA_OF_TIME
        case '.mmrs':
            seq_version = SeqVersion.MAJORAS_MASK
        case _:
            raise ValueError()

    with ArchiveHandler(archive) as handler:
        for seq in handler.sequences:
            modify_volume(seq, seq_version, new_volume)

