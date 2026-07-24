# TODO:
# - Add support for modifying channel volume and expression.
#   The parsing is implemented, now just the functionality has
#   to actually be implemented.


from pathlib import Path
import sys
import tempfile
import zipfile

from seq import SeqVersion, SequenceParser


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


def modify_volume(seq_path: Path, seq_version: SeqVersion, new_volume: int):
    # seq = AudioSequence(seq_file, seq_version)
    seq = SequenceParser.from_file(seq_path, seq_version)

    vol_instructions = seq.header.find_all_opcodes(0xDB)

    for instruction in vol_instructions:
        operand = instruction.get_operand(0)
        if operand:
            operand.value = new_volume

    seq_path.write_bytes(bytes(seq.stream))
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
