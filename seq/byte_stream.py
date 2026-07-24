import struct

from .constants import ReadableBuffer, WriteableBuffer
from .enums import DataType, Endian


class ByteStream:
    def __init__(self, data: ReadableBuffer, endian: Endian = Endian.BIG) -> None:
        self.data: WriteableBuffer = bytearray(data)
        self.cursor: int = 0
        self.endian: Endian = endian

    def seek(self, position: int = 0) -> None:
        self.cursor = position

    def tell(self) -> int:
        return self.cursor

    def skip(self, rel_position: int = 0) -> None:
        self.cursor += rel_position

    def read_byte(self) -> int:
        value = self.data[self.cursor]
        self.cursor += 1
        return value

    def read(self, data_type: DataType) -> tuple[int, int]:
        value, size = self._decode_at(data_type, self.cursor)
        self.cursor += size
        return value, size

    def read_at(self, data_type: DataType, address: int) -> tuple[int, int]:
        return self._decode_at(data_type, address)

    def _decode_at(self, data_type: DataType, address: int) -> tuple[int, int]:
        if data_type is DataType.COMPRESSED_U16:
            return self._decode_compressed_u16(address)

        value = struct.unpack_from(self.endian.value + data_type.fmt, self.data, address)[0]
        return value, data_type.size

    def _decode_compressed_u16(self, address: int) -> tuple[int, int]:
        # Source: https://github.com/zeldaret/mm/blob/a6850d214927aafa2635177510a5029ab7e989ea/src/audio/lib/seqplayer.c#L539-L547
        first_byte = self.data[address]

        if first_byte & 0x80:
            value = (first_byte << 8) & 0x7F00
            value = self.data[address + 1] | value
            return value, 2

        return first_byte, 1

    def write(self, data_type: DataType, value: int) -> int:
        size = self._encode_at(data_type, self.cursor, value)
        self.cursor += size
        return size

    def write_at(self, data_type: DataType, address: int, value: int) -> int:
        return self._encode_at(data_type, address, value)

    def _encode_at(self, data_type: DataType, address: int, value: int) -> int:
        if data_type is DataType.COMPRESSED_U16:
            return self._encode_compressed_u16(address, value)

        struct.pack_into(self.endian.value + data_type.fmt, self.data, address, value)
        return data_type.size

    def _encode_compressed_u16(self, address: int, value: int):
        if value < 0:
            raise ValueError(value)

        if value < 0x80:
            self.data[address] = value
            return 1

        if value <= 0x7FFF:
            self.data[address] = ((value >> 8) & 0x7F) | 0x80
            self.data[address + 1] = value & 0xFF
            return 2

        raise ValueError(value)

    def sizeof(self, data_type: DataType) -> int:
        if data_type is DataType.COMPRESSED_U16:
            return 2 if self.data[self.cursor] & 0x80 else 1
        return data_type.size

    def sizeof_at(self, data_type: DataType, address: int) -> int:
        if data_type is DataType.COMPRESSED_U16:
            return 2 if self.data[address] & 0x80 else 1
        return data_type.size

    def __bytes__(self) -> bytes:
        return bytes(self.data)

    def __getitem__(self, index: int | slice) -> int | bytearray:
        return self.data[index]

    def __setitem__(self, index: int, value: int) -> None:
        self.data[index] = value

    def __len__(self) -> int:
        return len(self.data)
