from dataclasses import dataclass, field
from datetime import timedelta
from typing import Callable, Collection, Iterable

from .byte_stream import ByteStream
from .constants import DEFAULT_TEMPO, TATUMS_PER_BEAT
from .enums import SeqSection, SeqVersion, ALL_SECTIONS
from .instructions import Instruction


@dataclass(eq=False)
class Script:
    section: SeqSection
    start: int
    end: int = 0
    instructions: list[Instruction] = field(default_factory=list)

    def find_all(self, predicate: Callable[[Instruction], bool]) -> list[Instruction]:
        return [
            instruction
            for instruction in self.instructions
            if predicate(instruction)
        ]

    def find_all_opcodes(self, opcode: int) -> list[Instruction]:
        return self.find_all(lambda instruction: instruction.opcode == opcode)

    def find_all_names(self, name: str) -> list[Instruction]:
        return self.find_all(lambda instruction: instruction.name == name)

    @property
    def size(self):
        return self.end - self.start

    @property
    def references(self):
        return self.find_all(lambda instruction: instruction.is_pointer == True)

    @property
    def calls(self):
        return self.find_all(lambda instruction: instruction.name == 'call')

    def __iter__(self):
        return iter(self.instructions)


@dataclass
class Channel:
    index: int
    scripts: list[Script] = field(default_factory=list)
    subscripts: set[Script] = field(default_factory=set)

    def find_all_opcodes(self, opcode: int) -> list[Instruction]:
        return [
            instruction
            for script in self.all_scripts
            for instruction in script.find_all_opcodes(opcode)
        ]

    def find_all_names(self, name: str) -> list[Instruction]:
        return [
            instruction
            for script in self.all_scripts
            for instruction in script.find_all_names(name)
        ]

    @property
    def all_scripts(self) -> set[Script]:
        return set(self.scripts) | self.subscripts


@dataclass
class AudioSequence:
    stream: ByteStream
    version: SeqVersion
    scripts: list[Script]
    script_map: dict[tuple[SeqSection, int], Script]
    channels: dict[int, Channel]

    def _get_script(self, section: SeqSection, address: int):
        key = (section, address)
        if key not in self.script_map:
            raise ValueError(f"No script found for {section=} at {address=}")
        return self.script_map[key]

    @property
    def header(self):
        return self._get_script(SeqSection.HEADER, 0x0000)

    @property
    def instructions(self) -> Iterable[Instruction]:
        for script in self.scripts:
            yield from script.instructions

    def get_channel(self, index: int) -> Channel | None:
        return self.channels.get(index)

    def get_duration(self) -> timedelta:
        tempo_instructions = sorted(
            self.get_instructions_by_name('tempo', (SeqSection.HEADER,)),
            key=lambda instruction: instruction.address,
        )

        delay_instructions = sorted(
            self.get_instructions_by_name('delay', (SeqSection.HEADER,)),
            key=lambda instruction: instruction.address,
        )

        current_tempo = DEFAULT_TEMPO
        tempo_index = 0
        duration = timedelta()

        for delay in delay_instructions:
            while (
                tempo_index < len(tempo_instructions)
                and tempo_instructions[tempo_index].address < delay.address
            ):
                current_tempo = tempo_instructions[tempo_index].get_operand(0).value
                tempo_index += 1

            if current_tempo == 0:
                continue

            ticks = delay.get_operand(0).value
            duration += timedelta(
                minutes=ticks / (TATUMS_PER_BEAT * current_tempo)
            )

        return duration

    def _get_instructions(self, sections: Collection[SeqSection], predicate: Callable[[Instruction], bool]) -> list[Instruction]:
        return [
            instruction
            for instruction in self.instructions
            if instruction.section in sections
            and predicate(instruction)
        ]

    def get_instructions_by_opcode(self, opcode: int, sections: Collection[SeqSection] = ALL_SECTIONS) -> list[Instruction]:
        return self._get_instructions(sections, lambda instruction: instruction.opcode == opcode)

    def get_instructions_by_name(self, name: str, sections: Collection[SeqSection] = ALL_SECTIONS) -> list[Instruction]:
        return self._get_instructions(sections, lambda instruction: instruction.name == name)
