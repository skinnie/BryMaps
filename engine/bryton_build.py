"""Build a Bryton Aero 60 MAP .dat from a Planetiler (OpenMapTiles) .mbtiles."""
import argparse
import gzip
import math
import sqlite3
import struct
import zlib

from mapbox_vector_tile.Mapbox import vector_tile_pb2 as pb

EMPTY = 0xFFFFFFFF
GZIP_MTIME = 0x5B76B000  # 2018-08-17, same era as Bryton's own files

T_TRANS_Z9 = {'motorway', 'trunk', 'primary', 'secondary', 'rail'}
T_TRANS_Z12 = {'motorway', 'trunk', 'primary', 'secondary', 'tertiary', 'minor', 'service',
               'rail', 'ferry', 'raceway', 'transit', 'cable_car'}
T_TRANS_Z14 = {'path', 'track'}

# layer -> (allowed classes or None, kept keys, keys dropped when value is 0)
PROFILE = {
    ('b1', 9): {
        'transportation': (T_TRANS_Z9, ['class', 'subclass', 'ramp', 'layer'], {'ramp', 'layer'}),
        'water': ({'ocean', 'lake', 'river'}, ['class'], set()),
        'waterway': ({'river'}, ['class', 'name'], set()),
        'boundary': (None, ['admin_level', 'disputed', 'maritime'], set()),
    },
    ('b1', 12): {
        'transportation': (T_TRANS_Z12, ['class', 'subclass', 'ramp', 'oneway', 'brunnel', 'layer', 'service'], set()),
        'water': ({'ocean', 'lake', 'river'}, ['class'], set()),
        'waterway': ({'river', 'canal'}, ['class', 'name', 'brunnel'], set()),
        'boundary': (None, ['admin_level', 'disputed', 'maritime'], set()),
    },
    ('b2', None): {
        'place': ({'country', 'state', 'city', 'town', 'village', 'hamlet', 'suburb', 'island'},
                  ['name', 'rank', 'class', 'capital', 'iso_a2'], set()),
    },
    ('b3', 14): {
        'transportation': (T_TRANS_Z14, ['class', 'subclass', 'ramp', 'oneway', 'brunnel', 'layer', 'service', 'level', 'indoor'], set()),
    },
}
LAYER_ORDER = ['transportation', 'water', 'waterway', 'boundary', 'place']


def pyval(v):
    for f in ('string_value', 'int_value', 'sint_value', 'uint_value', 'bool_value', 'double_value', 'float_value'):
        if v.HasField(f):
            return getattr(v, f)
    return None


class Src:
    def __init__(self, path):
        self.db = sqlite3.connect(path)

    def raw(self, z, x, y):
        r = self.db.execute("select tile_data from tiles where zoom_level=? and tile_column=? and tile_row=?",
                            (z, x, y)).fetchone()
        if not r:
            return None
        d = r[0]
        return gzip.decompress(d) if d[:2] == b'\x1f\x8b' else d

    def tile(self, z, x, y):
        d = self.raw(z, x, y)
        if d is None:
            return None
        t = pb.tile()
        t.ParseFromString(d)
        return t

    def cells(self, z):
        return [(x, y) for x, y in self.db.execute(
            "select tile_column, tile_row from tiles where zoom_level=?", (z,))]


def decode_geom(g):
    parts, i, x, y, cur = [], 0, 0, 0, None
    while i < len(g):
        cmd, cnt = g[i] & 7, g[i] >> 3
        i += 1
        if cmd == 7:
            if cur is not None:
                cur['closed'] = True
            continue
        for _ in range(cnt):
            dx, dy = g[i], g[i + 1]
            i += 2
            x += (dx >> 1) ^ -(dx & 1)
            y += (dy >> 1) ^ -(dy & 1)
            if cmd == 1:
                cur = {'pts': [], 'closed': False}
                parts.append(cur)
            cur['pts'].append((x, y))
    return parts


def zz(n):
    return (n << 1) ^ (n >> 31)


def encode_geom(parts):
    out, cx, cy = [], 0, 0
    for p in parts:
        pts = p['pts']
        out.append(1 | (1 << 3))
        out += [zz(pts[0][0] - cx), zz(pts[0][1] - cy)]
        cx, cy = pts[0]
        if len(pts) > 1:
            out.append(2 | ((len(pts) - 1) << 3))
            for x, y in pts[1:]:
                out += [zz(x - cx), zz(y - cy)]
                cx, cy = x, y
        if p['closed']:
            out.append(7 | (1 << 3))
    return out


class LayerBuilder:
    def __init__(self, name):
        self.L = pb.tile.layer()
        self.L.name = name
        self.L.version = 1
        self.L.extent = 4096
        self.kidx, self.vidx = {}, {}

    def _key(self, k):
        if k not in self.kidx:
            self.kidx[k] = len(self.L.keys)
            self.L.keys.append(k)
        return self.kidx[k]

    def _val(self, v):
        key = (type(v).__name__, v)
        if key not in self.vidx:
            val = self.L.values.add()
            if isinstance(v, str):
                val.string_value = v
            elif isinstance(v, bool):
                val.int_value = int(v)
            elif isinstance(v, float):
                if v.is_integer():
                    val.int_value = int(v)
                else:
                    val.float_value = v
            else:
                val.int_value = int(v)
            self.vidx[key] = len(self.L.values) - 1
        return self.vidx[key]

    def add(self, gtype, geometry, props):
        f = self.L.features.add()
        f.type = gtype
        f.geometry.extend(geometry)
        for k, v in props:
            f.tags.extend([self._key(k), self._val(v)])


def filtered_props(L, ft, keys, drop_zero):
    d = {}
    for k in range(0, len(ft.tags), 2):
        d[L.keys[ft.tags[k]]] = pyval(L.values[ft.tags[k + 1]])
    out = []
    for key in keys:
        if key not in d or d[key] is None:
            continue
        v = d[key]
        if key in drop_zero and v == 0:
            continue
        out.append((key, v))
    return d.get('class'), out


def build_tile(sources, profile):
    """sources: list of (pb.tile, transform or None) ; transform=(dx, dy, scale) maps child coords."""
    builders = {}
    for t, tf in sources:
        for L in t.layers:
            if L.name not in profile:
                continue
            classes, keys, drop_zero = profile[L.name]
            for ft in L.features:
                cls, props = filtered_props(L, ft, keys, drop_zero)
                if classes is not None and cls not in classes:
                    continue
                if L.name == 'boundary' and dict(props).get('admin_level', 99) > 6:
                    continue
                geom = list(ft.geometry)
                if ft.type == 1:
                    # Bryton keeps each point only in its owning tile (no buffer copies)
                    pts = [pt for p in decode_geom(geom) for pt in p['pts']]
                    if not pts or not all(0 <= x < 4096 and 0 <= y < 4096 for x, y in pts):
                        continue
                if tf is not None:
                    dx, dy, s = tf
                    parts = []
                    for p in decode_geom(geom):
                        pts = []
                        for x, y in p['pts']:
                            q = (int(round((x + dx) / s)), int(round((y + dy) / s)))
                            if not pts or pts[-1] != q:
                                pts.append(q)
                        if ft.type == 2 and len(pts) < 2:
                            continue
                        if ft.type == 3 and len(pts) < 3:
                            continue
                        p['pts'] = pts
                        parts.append(p)
                    if not parts:
                        continue
                    geom = encode_geom(parts)
                if L.name not in builders:
                    builders[L.name] = LayerBuilder(L.name)
                builders[L.name].add(ft.type, geom, props)
    if not builders:
        return None
    out = pb.tile()
    for name in LAYER_ORDER:
        if name in builders:
            out.layers.append(builders[name].L)
    return out.SerializeToString()


def gz(raw):
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    body = c.compress(raw) + c.flush()
    hdr = b'\x1f\x8b\x08\x00' + struct.pack('<I', GZIP_MTIME) + b'\x02\xff'
    return hdr + body + struct.pack('<II', zlib.crc32(raw) & 0xFFFFFFFF, len(raw) & 0xFFFFFFFF)


def section_bytes(zoom, bbox, tiles):
    """tiles: dict (x,y)->gzip bytes. bbox=(xmin,xmax,ymin,ymax). Column-major, TMS y."""
    xmin, xmax, ymin, ymax = bbox
    w, h = xmax - xmin + 1, ymax - ymin + 1
    table = [EMPTY] * (w * h)
    data = bytearray()
    for x in range(xmin, xmax + 1):
        for y in range(ymin, ymax + 1):
            g = tiles.get((x, y))
            if g is None:
                continue
            table[(x - xmin) * h + (y - ymin)] = len(data)
            data += struct.pack('<I', len(g)) + g + b'\x00\x00'
    hdr = bytearray(100)
    hdr[0:6] = b'BRYTON'
    struct.pack_into('<HHIH', hdr, 6, 1, zoom, 1, 0)
    struct.pack_into('<IIII', hdr, 16, xmin, xmax, ymin, ymax)
    hdr[32], hdr[33] = 4, 4
    struct.pack_into('<I', hdr, 34, 100 + 4 * w * h)
    return bytes(hdr) + struct.pack(f'<{w * h}I', *table) + bytes(data)


def block_bytes(sections):
    """sections: dict zoom -> section bytes. Returns 80-byte block header + sections."""
    hdr = bytearray(80)
    body = bytearray()
    for z in sorted(sections):
        struct.pack_into('<I', hdr, 36 + 4 * (z - 9), 80 + len(body))
        body += sections[z]
    return bytes(hdr) + bytes(body)


def lonlat_to_tms(lon, lat, z):
    n = 2 ** z
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n)
    return x, n - 1 - y


def bbox_for(bounds, z):
    w, s, e, n = bounds
    x0, y0 = lonlat_to_tms(w, s, z)
    x1, y1 = lonlat_to_tms(e, n, z)
    return min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)


def in_bbox(xy, bb):
    return bb[0] <= xy[0] <= bb[1] and bb[2] <= xy[1] <= bb[3]


def build(src_path, out_dir, name, code, bounds, log=print, z12_mode='native'):
    src = Src(src_path)
    bb = {z: bbox_for(bounds, z) for z in (9, 10, 11, 12, 14)}

    def collect(z, profile, source_fn):
        tiles = {}
        for xy in src.cells(z):
            if not in_bbox(xy, bb[z]):
                continue
            raw = build_tile(source_fn(z, *xy), profile)
            if raw:
                tiles[xy] = gz(raw)
        log(f"  z{z}: {len(tiles)} tiles")
        return tiles

    def same(z, x, y):
        t = src.tile(z, x, y)
        return [(t, None)] if t else []

    ARTERIAL = {'motorway', 'trunk', 'primary', 'secondary', 'tertiary', 'rail',
                'ferry', 'raceway', 'transit', 'cable_car'}
    LOCAL = {'minor', 'service'}

    def z13_merged(z, x, y):
        # arterials + water/boundary from native z12; local street grid from the
        # 4 z13 children (already simplified for z13, ~1/4 the vertices of z14)
        out = []
        t = src.tile(12, x, y)
        if t:
            base = pb.tile()
            for L in t.layers:
                if L.name in ('water', 'boundary', 'waterway'):
                    base.layers.append(L)
                elif L.name == 'transportation':
                    keep = pb.tile.layer()
                    keep.CopyFrom(L)
                    del keep.features[:]
                    for ft in L.features:
                        cls = next((pyval(L.values[ft.tags[k + 1]]) for k in range(0, len(ft.tags), 2)
                                    if L.keys[ft.tags[k]] == 'class'), None)
                        if cls in ARTERIAL:
                            keep.features.append(ft)
                    if keep.features:
                        base.layers.append(keep)
            out.append((base, None))
        n13 = 2 ** 13
        for cx in range(2 * x, 2 * x + 2):
            for cy in range(2 * y, 2 * y + 2):
                c = src.tile(13, cx, cy)
                if not c:
                    continue
                sub = pb.tile()
                for L in c.layers:
                    if L.name != 'transportation':
                        continue
                    keep = pb.tile.layer()
                    keep.CopyFrom(L)
                    del keep.features[:]
                    for ft in L.features:
                        cls = next((pyval(L.values[ft.tags[k + 1]]) for k in range(0, len(ft.tags), 2)
                                    if L.keys[ft.tags[k]] == 'class'), None)
                        if cls in LOCAL:
                            keep.features.append(ft)
                    if keep.features:
                        sub.layers.append(keep)
                if sub.layers:
                    col = cx - 2 * x
                    row = (n13 - 1 - cy) - 2 * (2 ** 12 - 1 - y)
                    out.append((sub, (col * 4096, row * 4096, 2)))
        return out

    def z12_merged(z, x, y):
        # water/boundary from the z12 tile itself (polygons stay seamless),
        # roads/waterways from the 16 z14 children for full detail
        out = []
        t = src.tile(12, x, y)
        if t:
            keep = pb.tile()
            keep.layers.extend([L for L in t.layers if L.name in ('water', 'boundary')])
            out.append((keep, None))
        n14 = 2 ** 14
        for cx in range(4 * x, 4 * x + 4):
            for cy in range(4 * y, 4 * y + 4):
                c = src.tile(14, cx, cy)
                if not c:
                    continue
                sub = pb.tile()
                sub.layers.extend([L for L in c.layers if L.name in ('transportation', 'waterway')])
                col = cx - 4 * x
                row = (n14 - 1 - cy) - 4 * (2 ** 12 - 1 - y)  # XYZ row offset inside parent
                out.append((sub, (col * 4096, row * 4096, 4)))
        return out

    z12src = {'native': same, 'z13': z13_merged, 'z14': z12_merged}[z12_mode]
    log(f"block1 (base map, z12 mode={z12_mode})")
    b1 = {9: collect(9, PROFILE[('b1', 9)], same),
          12: collect(12, PROFILE[('b1', 12)], z12src)}
    log("block2 (place labels)")
    b2 = {z: collect(z, PROFILE[('b2', None)], same) for z in (9, 10, 11, 12)}
    log("block3 (paths/tracks)")
    b3 = {14: collect(14, PROFILE[('b3', 14)], same)}

    blocks = []
    for sec in (b1, b2, b3):
        blocks.append(block_bytes({z: section_bytes(z, bb[z], t) for z, t in sec.items()}))

    head = bytearray(50)
    head[0:6] = b'P' + code.encode() + b'00'
    o1 = 50
    o2 = o1 + len(blocks[0])
    o3 = o2 + len(blocks[1])
    struct.pack_into('<IIII', head, 6, 1, o1, o2, o3)
    x0, x1, y0, y1 = bb[9]
    fname = f"{x0}-{y0}-{x1}-{y1}-{name}.dat"
    path = f"{out_dir}/{fname}"
    with open(path, 'wb') as f:
        f.write(head)
        for b in blocks:
            f.write(b)
    return path


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('mbtiles')
    ap.add_argument('--out', default='.')
    ap.add_argument('--name', required=True)
    ap.add_argument('--code', required=True, help='3 chars after P, e.g. CTW')
    ap.add_argument('--bounds', required=True, help='w,s,e,n in degrees')
    ap.add_argument('--z12', default='native', choices=['native', 'z13', 'z14'])
    a = ap.parse_args()
    print(build(a.mbtiles, a.out, a.name, a.code, tuple(float(v) for v in a.bounds.split(',')), z12_mode=a.z12))
