"""Reader for Bryton Aero 60 / Rider 450 MAP .dat containers (magic 'P?xx00')."""
import struct
from dataclasses import dataclass, field

EMPTY = 0xFFFFFFFF


@dataclass
class Section:
    offset: int
    zoom: int
    xmin: int
    xmax: int
    ymin: int
    ymax: int
    data_offset: int
    raw_header: bytes
    table: list = field(repr=False, default_factory=list)

    @property
    def width(self):
        return self.xmax - self.xmin + 1

    @property
    def height(self):
        return self.ymax - self.ymin + 1

    @property
    def data_base(self):
        return self.offset + self.data_offset


@dataclass
class Block:
    offset: int
    raw_header: bytes
    section_offsets: dict  # zoom -> relative offset
    sections: dict = field(default_factory=dict)


def parse_section(buf, off):
    assert buf[off:off + 6] == b'BRYTON', f"no BRYTON at {off}"
    ver, zoom = struct.unpack_from('<HH', buf, off + 6)
    xmin, xmax, ymin, ymax = struct.unpack_from('<IIII', buf, off + 16)
    data_offset = struct.unpack_from('<I', buf, off + 34)[0]
    s = Section(off, zoom, xmin, xmax, ymin, ymax, data_offset, bytes(buf[off:off + 100]))
    n = s.width * s.height
    assert data_offset == 100 + 4 * n, (data_offset, n)
    s.table = list(struct.unpack_from(f'<{n}I', buf, off + 100))
    return s


def parse(buf):
    magic = bytes(buf[:6])
    ver, b1, b2, b3 = struct.unpack_from('<IIII', buf, 6)
    blocks = []
    for boff in (b1, b2, b3):
        slots = struct.unpack_from('<11I', buf, boff + 36)
        so = {9 + i: v for i, v in enumerate(slots) if v}
        blk = Block(boff, bytes(buf[boff:boff + 80]), so)
        for z, rel in so.items():
            sec = parse_section(buf, boff + rel)
            assert sec.zoom == z
            blk.sections[z] = sec
        blocks.append(blk)
    return magic, blocks


def cell_index(sec, x, y):
    # column-major, TMS y; verified against Planetiler geometry for Lille z12
    return (x - sec.xmin) * sec.height + (y - sec.ymin)


def record(buf, sec, i):
    v = sec.table[i]
    if v == EMPTY:
        return None
    p = sec.data_base + v
    ln = struct.unpack_from('<I', buf, p)[0]
    return p, ln, bytes(buf[p + 4:p + 4 + ln])
