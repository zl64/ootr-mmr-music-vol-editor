from dataclasses import dataclass, field
from pathlib import Path

from .byte_stream import ByteStream
from .enums import SeqSection, SeqVersion
from .sequence import Script
from .specification import SPECS
from .instructions import Instruction, INSTRUCTION_TYPES, Operand
from .sequence import AudioSequence, Script, Channel


@dataclass
class ParserState:
    scripts: list[Script] = field(default_factory=list)
    script_map: dict[tuple[SeqSection, int], Script] = field(default_factory=dict)
    channel_roots: dict[int, list[int]] = field(default_factory=dict)
    channels: dict[int, Channel] = field(default_factory=dict)


class SequenceParser:
    def __init__(self, stream: ByteStream, version: SeqVersion) -> None:
        self.stream: ByteStream = stream
        self.version: SeqVersion = version
        self.state: ParserState = ParserState()

    @classmethod
    def from_file(cls, file_path: Path, version: SeqVersion) -> AudioSequence:
        parser = cls(ByteStream(file_path.read_bytes()), version)
        return parser.parse()

    def parse(self) -> AudioSequence:
        self._parse_sequence()
        self._build_channels()

        result = AudioSequence(
            stream=self.stream,
            version=self.version,
            scripts=self.state.scripts,
            script_map=self.state.script_map,
            channels=self.state.channels,
        )

        self.state = ParserState()
        return result

    def _get_script(self, section: SeqSection, address: int):
        key = (section, address)
        if key not in self.state.script_map:
            raise ValueError(f"No script found for {section=} at {address=}")
        return self.state.script_map[key]

    def _parse_sequence(self) -> None:
        queue = [(SeqSection.HEADER, 0x0000)]
        seen = set()

        while queue:
            section, start = queue.pop()
            key = (section, start)

            if key in seen:
                continue

            seen.add(key)

            script = self._parse_script(section, start, queue)

            self.state.scripts.append(script)
            self.state.script_map[key] = script

    def _parse_script(self, section: SeqSection, start: int, queue: list[tuple(SeqSection, int)] = None) -> Script:
        self.stream.seek(start)

        script = Script(section, start)

        while True:
            instruction_address = self.stream.tell()
            opcode = self.stream.read_byte()

            for spec in SPECS:
                if spec.matches(opcode, section, self.version):
                    break
            else:
                raise ValueError(f"Unknown opcode {opcode:#x} at {instruction_address:#06x}")

            operands = []

            if spec.bitmask:
                operands.append(
                    Operand(
                        stream=self.stream,
                        address=instruction_address,
                        mask=spec.bitmask.operand_mask,
                    )
                )

            for data_type in spec.operands:
                operand_address = self.stream.tell()

                operands.append(
                    Operand(
                        stream=self.stream,
                        address=operand_address,
                        data_type=data_type,
                    )
                )

                self.stream.skip(self.stream.sizeof(data_type))

            instruction: Instruction = INSTRUCTION_TYPES.get(spec.name, Instruction)(
                stream=self.stream,
                address=instruction_address,
                opcode=opcode,
                name=spec.name,
                section=section,
                operands=operands,
                is_pointer=spec.is_pointer,
            )

            script.instructions.append(instruction)

            match instruction.name:
                case 'ldchan':
                    ch_idx = instruction.operands[0].value
                    ch_ptr = instruction.operands[1].value

                    # TODO: Figure out if this condition is needed later
                    if section == SeqSection.HEADER:
                        self.state.channel_roots.setdefault(ch_idx, []).append(ch_ptr)

                    if queue is not None:
                        queue.append((SeqSection.CHANNEL, ch_ptr))

                case 'call':
                    ptr = instruction.operands[0].value

                    if queue is not None:
                        queue.append((section, ptr))

                case 'end':
                    script.end = self.stream.tell()
                    return script

    # TODO: Clean this shit up...
    def _build_channels(self) -> None:
        for index, pointers in self.state.channel_roots.items():
            channel = Channel(index)

            for ptr in pointers:
                script = self._get_script(SeqSection.CHANNEL, ptr)

                channel.scripts.append(script)
                self._collect_subscripts(script, channel.subscripts)

            self.state.channels[index] = channel

    def _collect_subscripts(self, script: Script, result: set[Script]):
        for call in script.calls:
            subscript = self._get_script(script.section, call.get_operand(0).value)

            if subscript in result:
                continue

            result.add(subscript)
            self._collect_subscripts(subscript, result)
