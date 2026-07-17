# TODO:
# - Add support for modifying channel volume and expression.
#   The parsing is implemented, now just the functionality has
#   to actually be implemented.


from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
import struct
import sys
import tempfile
from typing import Callable, Collection
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


#region Spec
@dataclass
class Spec:
    opcode: int
    name: str
    args: tuple[ArgType, ...] = ()
    bitmask: BitField | None = None
    sections: tuple[SeqSection, ...] = ALL_SECTIONS
    versions: tuple[SeqVersion, ...] = ALL_VERSIONS
    is_pointer: bool = False

    def matches(self, opcode: int, section: SeqSection, version: SeqVersion) -> bool:
        if section not in self.sections:
            return False

        if version not in self.versions:
            return False

        if self.bitmask is None:
            return opcode == self.opcode

        return (opcode & self.bitmask.opcode_mask) == self.opcode


SPECS = [
    #region Control Flow
    Spec(0xFF, 'end',),
    Spec(0xFE, 'delay1',),
    Spec(0xFD, 'delay',          args=(ArgType.VAR,),),
    Spec(0xFC, 'call',           args=(ArgType.U16,), is_pointer=True,),
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
    #endregion Control Flow

    #region Header
    # Non-Argbit
    Spec(0xF1, 'allocnotelist',  args=(ArgType.U8,),              sections=(SeqSection.HEADER,)),
    Spec(0xF0, 'freenotelist',   args=(ArgType.U8,),              sections=(SeqSection.HEADER,)),
    Spec(0xEF, 'hd_EF',          args=(ArgType.S16, ArgType.U8),  sections=(SeqSection.HEADER,)),
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
    Spec(0xC3, 'hd_C3',          args=(ArgType.U16,),             sections=(SeqSection.HEADER,), versions=(SeqVersion.MAJORAS_MASK,)),
    Spec(0xC2, 'hd_C2',          args=(ArgType.S16,),             sections=(SeqSection.HEADER,), versions=(SeqVersion.MAJORAS_MASK,)),

    # Argbit
    Spec(0xB0, 'ldseq',          args=(ArgType.U8, ArgType.U16,), sections=(SeqSection.HEADER,), bitmask=BITFIELDS[4],),
    Spec(0xA0, 'rldchan',        args=(ArgType.S16,),             sections=(SeqSection.HEADER,), bitmask=BITFIELDS[4],),
    Spec(0x90, 'ldchan',         args=(ArgType.U16,),             sections=(SeqSection.HEADER,), bitmask=BITFIELDS[4], is_pointer=True,),
    Spec(0x80, 'ldio',                                            sections=(SeqSection.HEADER,), bitmask=BITFIELDS[3],),
    Spec(0x70, 'stio',                                            sections=(SeqSection.HEADER,), bitmask=BITFIELDS[3],),
    Spec(0x60, 'ldres',          args=(ArgType.U8, ArgType.U8,),  sections=(SeqSection.HEADER,), bitmask=BITFIELDS[4],),
    Spec(0x50, 'subio',                                           sections=(SeqSection.HEADER,), bitmask=BITFIELDS[3],),
    Spec(0x40, 'stopchan',                                        sections=(SeqSection.HEADER,), bitmask=BITFIELDS[4],),
    Spec(0x00, 'testchan',                                        sections=(SeqSection.HEADER,), bitmask=BITFIELDS[4],),
    #endregion Header

    #region Channel
    # Non-Argbit
    Spec(0xF1, 'allocnotelist', args=(ArgType.U8,),                         sections=(SeqSection.CHANNEL,),),
    Spec(0xF0, 'freenotelist',                                              sections=(SeqSection.CHANNEL,),),
    Spec(0xEE, 'bend2',         args=(ArgType.S8,),                         sections=(SeqSection.CHANNEL,),),
    Spec(0xED, 'gain',          args=(ArgType.U8,),                         sections=(SeqSection.CHANNEL,),),
    Spec(0xEC, 'resetparams',                                               sections=(SeqSection.CHANNEL,),),
    Spec(0xEB, 'fontinstr',     args=(ArgType.U8, ArgType.U8,),             sections=(SeqSection.CHANNEL,),),
    Spec(0xEA, 'stop',                                                      sections=(SeqSection.CHANNEL,),),
    Spec(0xE9, 'notepri',       args=(ArgType.U8,),                         sections=(SeqSection.CHANNEL,),),
    Spec(0xE8, 'params',        args=(ArgType.U8, ArgType.U8, ArgType.U8, ArgType.S8, ArgType.S8, ArgType.U8, ArgType.U8, ArgType.U8,), sections=(SeqSection.CHANNEL,),),
    Spec(0xE7, 'ldparams',      args=(ArgType.U16,),                        sections=(SeqSection.CHANNEL,),),
    Spec(0xE6, 'samplebook',    args=(ArgType.U8,),                         sections=(SeqSection.CHANNEL,),),
    Spec(0xE5, 'reverbidx',     args=(ArgType.U8,),                         sections=(SeqSection.CHANNEL,),),
    Spec(0xE4, 'dyncall',                                                   sections=(SeqSection.CHANNEL,),),
    Spec(0xE3, 'vibdelay',      args=(ArgType.U8,),                         sections=(SeqSection.CHANNEL,),),
    Spec(0xE2, 'vibdepthgrad',  args=(ArgType.U8, ArgType.U8, ArgType.U8,), sections=(SeqSection.CHANNEL,),),
    Spec(0xE1, 'vibfreqgrad',   args=(ArgType.U8, ArgType.U8, ArgType.U8,), sections=(SeqSection.CHANNEL,),),
    Spec(0xE0, 'volexp',        args=(ArgType.U8,),                         sections=(SeqSection.CHANNEL,),),
    Spec(0xDF, 'vol',           args=(ArgType.U8,),                         sections=(SeqSection.CHANNEL,),),
    Spec(0xDE, 'freqscale',     args=(ArgType.U16,),                        sections=(SeqSection.CHANNEL,),),
    Spec(0xDD, 'pan',           args=(ArgType.U8,),                         sections=(SeqSection.CHANNEL,),),
    Spec(0xDC, 'panweight',     args=(ArgType.U8,),                         sections=(SeqSection.CHANNEL,),),
    Spec(0xDB, 'transpose',     args=(ArgType.S8,),                         sections=(SeqSection.CHANNEL,),),
    Spec(0xDA, 'env',           args=(ArgType.U16,),                        sections=(SeqSection.CHANNEL,),),
    Spec(0xD9, 'releaserate',   args=(ArgType.U8,),                         sections=(SeqSection.CHANNEL,),),
    Spec(0xD8, 'vibdepth',      args=(ArgType.U8,),                         sections=(SeqSection.CHANNEL,),),
    Spec(0xD7, 'vibfreq',       args=(ArgType.U8,),                         sections=(SeqSection.CHANNEL,),),
    Spec(0xD4, 'reverb',        args=(ArgType.U8,),                         sections=(SeqSection.CHANNEL,),),
    Spec(0xD3, 'bend12',        args=(ArgType.S8,),                         sections=(SeqSection.CHANNEL,),),
    Spec(0xD2, 'sustain',       args=(ArgType.U8,),                         sections=(SeqSection.CHANNEL,),),
    Spec(0xD1, 'notealloc',     args=(ArgType.U8,),                         sections=(SeqSection.CHANNEL,),),
    Spec(0xD0, 'effects',       args=(ArgType.U8,),                         sections=(SeqSection.CHANNEL,),),
    Spec(0xCF, 'stptrtoseq',    args=(ArgType.U16,),                        sections=(SeqSection.CHANNEL,),),
    Spec(0xCE, 'ldptr',         args=(ArgType.U16,),                        sections=(SeqSection.CHANNEL,),),
    Spec(0xCD, 'stopchan',      args=(ArgType.U8,),                         sections=(SeqSection.CHANNEL,),),
    Spec(0xCC, 'ldi',           args=(ArgType.U8,),                         sections=(SeqSection.CHANNEL,),),
    Spec(0xCB, 'ldseq',         args=(ArgType.U16,),                        sections=(SeqSection.CHANNEL,),),
    Spec(0xCA, 'mutebhv',       args=(ArgType.U8,),                         sections=(SeqSection.CHANNEL,),),
    Spec(0xC9, 'and',           args=(ArgType.U8,),                         sections=(SeqSection.CHANNEL,),),
    Spec(0xC8, 'sub',           args=(ArgType.U8,),                         sections=(SeqSection.CHANNEL,),),
    Spec(0xC7, 'stseq',         args=(ArgType.U8, ArgType.U16,),            sections=(SeqSection.CHANNEL,),),
    Spec(0xC6, 'font',          args=(ArgType.U8,),                         sections=(SeqSection.CHANNEL,),),
    Spec(0xC5, 'dyntbllookup',                                              sections=(SeqSection.CHANNEL,),),
    Spec(0xC4, 'legato',                                                    sections=(SeqSection.CHANNEL,),),
    Spec(0xC3, 'nolegato',                                                  sections=(SeqSection.CHANNEL,),),
    Spec(0xC2, 'dyntbl',        args=(ArgType.U16,),                        sections=(SeqSection.CHANNEL,),),
    Spec(0xC1, 'instr',         args=(ArgType.U8,),                         sections=(SeqSection.CHANNEL,),),
    Spec(0xBE, 'ch_BE',         args=(ArgType.U8,),                         sections=(SeqSection.CHANNEL,), versions=(SeqVersion.MAJORAS_MASK,),),
    Spec(0xBD, 'randptr',       args=(ArgType.U16, ArgType.U16,),           sections=(SeqSection.CHANNEL,), versions=(SeqVersion.OCARINA_OF_TIME,),),
    Spec(0xBD, 'samplestart',   args=(ArgType.U8,),                         sections=(SeqSection.CHANNEL,), versions=(SeqVersion.MAJORAS_MASK,),),
    Spec(0xBC, 'ptradd',        args=(ArgType.U16,),                        sections=(SeqSection.CHANNEL,),),
    Spec(0xBB, 'combfilter',    args=(ArgType.U8, ArgType.U16,),            sections=(SeqSection.CHANNEL,),),
    Spec(0xBA, 'randgate',      args=(ArgType.U8,),                         sections=(SeqSection.CHANNEL,),),
    Spec(0xB9, 'randvel',       args=(ArgType.U8,),                         sections=(SeqSection.CHANNEL,),),
    Spec(0xB8, 'rand',          args=(ArgType.U8,),                         sections=(SeqSection.CHANNEL,),),
    Spec(0xB7, 'randtoptr',     args=(ArgType.U16,),                        sections=(SeqSection.CHANNEL,),),
    Spec(0xB6, 'dyntblv',                                                   sections=(SeqSection.CHANNEL,),),
    Spec(0xB5, 'dyntbltoptr',                                               sections=(SeqSection.CHANNEL,),),
    Spec(0xB4, 'ptrtodyntbl',                                               sections=(SeqSection.CHANNEL,),),
    Spec(0xB3, 'filter',        args=(ArgType.U8,),                         sections=(SeqSection.CHANNEL,),),
    Spec(0xB2, 'ldseqtoptr',    args=(ArgType.U16,),                        sections=(SeqSection.CHANNEL,),),
    Spec(0xB1, 'freefilter',                                                sections=(SeqSection.CHANNEL,),),
    Spec(0xB0, 'ldfilter',      args=(ArgType.U16,),                        sections=(SeqSection.CHANNEL,),),
    Spec(0xA8, 'randptr',       args=(ArgType.U16, ArgType.U16,),           sections=(SeqSection.CHANNEL,), versions=(SeqVersion.MAJORAS_MASK,),),
    Spec(0xA7, 'ch_A7',         args=(ArgType.U8,),                         sections=(SeqSection.CHANNEL,), versions=(SeqVersion.MAJORAS_MASK,),),
    Spec(0xA6, 'ch_A6',         args=(ArgType.U8, ArgType.S16,),            sections=(SeqSection.CHANNEL,), versions=(SeqVersion.MAJORAS_MASK,),),
    Spec(0xA5, 'ch_A5',                                                     sections=(SeqSection.CHANNEL,), versions=(SeqVersion.MAJORAS_MASK,),),
    Spec(0xA4, 'ch_A4',         args=(ArgType.U8,),                         sections=(SeqSection.CHANNEL,), versions=(SeqVersion.MAJORAS_MASK,),),
    Spec(0xA3, 'ch_A3',                                                     sections=(SeqSection.CHANNEL,), versions=(SeqVersion.MAJORAS_MASK,),),
    Spec(0xA2, 'ch_A2',         args=(ArgType.S16,),                        sections=(SeqSection.CHANNEL,), versions=(SeqVersion.MAJORAS_MASK,),),
    Spec(0xA1, 'ch_A1',                                                     sections=(SeqSection.CHANNEL,), versions=(SeqVersion.MAJORAS_MASK,),),
    Spec(0xA0, 'ch_A0',         args=(ArgType.S16,),                        sections=(SeqSection.CHANNEL,), versions=(SeqVersion.MAJORAS_MASK,),),

    # Argbit
    Spec(0x98, 'dynldlayer',                                                sections=(SeqSection.CHANNEL,), bitmask=BITFIELDS[3],),
    Spec(0x90, 'dellayer',                                                  sections=(SeqSection.CHANNEL,), bitmask=BITFIELDS[3],),
    Spec(0x88, 'ldlayer',       args=(ArgType.U16,),                         sections=(SeqSection.CHANNEL,), bitmask=BITFIELDS[3],),
    Spec(0x80, 'testlayer',                                                 sections=(SeqSection.CHANNEL,), bitmask=BITFIELDS[3],),
    Spec(0x78, 'rldlayer',      args=(ArgType.U16,),                        sections=(SeqSection.CHANNEL,), bitmask=BITFIELDS[3],),
    Spec(0x70, 'stio',                                                      sections=(SeqSection.CHANNEL,), bitmask=BITFIELDS[3],),
    Spec(0x60, 'ldio',                                                      sections=(SeqSection.CHANNEL,), bitmask=BITFIELDS[3],),
    Spec(0x50, 'subio',                                                     sections=(SeqSection.CHANNEL,), bitmask=BITFIELDS[3],),
    Spec(0x40, 'ldcio',         args=(ArgType.U8,),                         sections=(SeqSection.CHANNEL,), bitmask=BITFIELDS[4],),
    Spec(0x30, 'stcio',         args=(ArgType.U8,),                         sections=(SeqSection.CHANNEL,), bitmask=BITFIELDS[4],),
    Spec(0x20, 'ldchan',        args=(ArgType.U16,),                        sections=(SeqSection.CHANNEL,), bitmask=BITFIELDS[4], is_pointer=True,),
    Spec(0x18, 'ldsample',                                                  sections=(SeqSection.CHANNEL,), bitmask=BITFIELDS[3],),
    Spec(0x10, 'ldsample',                                                  sections=(SeqSection.CHANNEL,), bitmask=BITFIELDS[3],),
    Spec(0x00, 'cdelay',                                                    sections=(SeqSection.CHANNEL,), bitmask=BITFIELDS[4],),
    #endregion Channel

    #region Note Layer
    #endregion Note Layer
]
#endregion Spec


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
    spec: Spec
    section: SeqSection
    args: list[Arg] = field(default_factory=list)

    def get_arg(self, index: int) -> Arg | None:
        if 0 <= index < len(self.args):
            return self.args[index]
        return None

    @property
    def name(self) -> str:
        return self.spec.name

    @property
    def is_pointer(self) -> bool:
        return self.spec.is_pointer


@dataclass
class PointerMessage(Message):
    @property
    def pointer(self) -> TypedArg:
        raise NotImplementedError()


@dataclass
class CallMessage(PointerMessage):
    @property
    def pointer(self) -> TypedArg:
        return self.args[0]


@dataclass
class LoadChannelMessage(PointerMessage):
    @property
    def index(self) -> int:
        return self.args[0].value

    @property
    def pointer(self) -> TypedArg:
        return self.args[1]


MESSAGE_TYPES = {
    'call': CallMessage,
    'ldchan': LoadChannelMessage,
}


@dataclass
class Script:
    section: SeqSection
    start: int
    end: int = 0
    messages: list[Message] = field(default_factory=list)

    def find_all(self, predicate: Callable[[Message], bool]) -> list[Message]:
        return [
            msg
            for msg in self.messages
            if predicate(msg)
        ]

    def find_all_opcodes(self, opcode: int) -> list[Message]:
        return self.find_all(lambda msg: msg.opcode == opcode)

    def find_all_names(self, name: str) -> list[Message]:
        return self.find_all(lambda msg: msg.name == name)

    @property
    def size(self):
        return self.end - self.start

    @property
    def references(self):
        return self.find_all(lambda msg: msg.is_pointer == True)


class AudioSequence:
    def __init__(self, seq_path: Path, seq_version: SeqVersion):
        self.data = bytearray(seq_path.read_bytes())
        self.version = seq_version

        self.scripts: list[Script] = []
        self.script_map: dict[tuple[SeqSection, int], Script] = {}

    @property
    def header(self):
        return self.script_map[(SeqSection.HEADER, 0x0000)]

    @property
    def messages(self):
        for script in self.scripts:
            yield from script.messages

    def _get_msgs(self, sections: Collection[SeqSection], predicate: Callable[[Message], bool]) -> list[Message]:
        return [
            msg
            for msg in self.messages
            if msg.section in sections
            and predicate(msg)
        ]

    def get_msgs_by_opcode(self, opcode: int, sections: Collection[SeqSection] = ALL_SECTIONS) -> list[Message]:
        return self._get_msgs(sections, lambda msg: msg.opcode == opcode)

    def get_msgs_by_name(self, name: str, sections: Collection[SeqSection] = ALL_SECTIONS) -> list[Message]:
        return self._get_msgs(sections, lambda msg: msg.name == name)

    # def get_channel(self, index: int) -> Script | None:
    #     for msg in self.header.messages:
    #         if isinstance(msg, LoadChannelMessage) and msg.index == index:
    #             return self.script_map[(SeqSection.CHANNEL, msg.pointer.value)]

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

    def _parse_script(self, section: SeqSection, start: int, queue: list[tuple(SeqSection, int)] = None) -> Script:
        script = Script(section, start)
        pos = start

        while True:
            msg_offset = pos

            opcode = self.data[pos]
            pos += 1

            for spec in SPECS:
                if spec.matches(opcode, section, self.version):
                    break
            else:
                raise ValueError(f"Unknown opcode {opcode:#x} at {msg_offset:#06x}")

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

            msg_type = MESSAGE_TYPES.get(spec.name, Message)
            msg: Message = msg_type(
                offset=msg_offset,
                opcode=opcode,
                spec=spec,
                section=section,
                args=args,
            )

            script.messages.append(msg)

            match msg.name:
                case 'ldchan':
                    if queue is not None:
                        queue.append((SeqSection.CHANNEL, msg.pointer.value))

                case 'call':
                    if queue is not None:
                        queue.append((section, msg.pointer.value))

                case 'end':
                    script.end = pos
                    return script


    def parse_sequence(self) -> None:
        queue = [(SeqSection.HEADER, 0x0000)]
        seen = set()

        while queue:
            section, start = queue.pop()

            if (section, start) in seen:
                continue

            seen.add((section, start))

            script = self._parse_script(section, start, queue)
            # script = self._parse_script(SeqSection.HEADER, 0x0000)

            self.scripts.append(script)
            self.script_map[(section, start)] = script
            # self.script_map[(SeqSection.HEADER, 0x0000)] = script
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
    seq.parse_sequence()

    vol_msgs = seq.header.find_all_opcodes(0xDB)

    # cvol_msgs = seq.get_msgs_by_name('volexp', (SeqSection.CHANNEL,))
    # for msg in cvol_msgs:
    #     print(msg.get_arg(0).value)

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

