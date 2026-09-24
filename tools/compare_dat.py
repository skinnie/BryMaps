"""Compare two Bryton .dat files section by section; render sample tiles side by side."""
import collections
import gzip
import math
import sys

from PIL import Image, ImageDraw
from mapbox_vector_tile.Mapbox import vector_tile_pb2 as pb

import bryton_dat as B
from bryton_build import decode_geom, pyval

NAMES = {0: 'b1', 1: 'b2', 2: 'b3'}
COLORS = {'motorway': (200, 0, 0), 'trunk': (220, 80, 0), 'primary': (230, 140, 0), 'secondary': (180, 170, 0),
          'tertiary': (120, 120, 120), 'minor': (150, 150, 150), 'service': (190, 190, 190), 'rail': (60, 60, 60),
          'path': (0, 140, 0), 'track': (140, 90, 30)}


def load(path):
    buf = open(path, 'rb').read()
    magic, blocks = B.parse(buf)
    secs = {}
    for bi, blk in enumerate(blocks):
        for z, s in blk.sections.items():
            tiles = {}
            for i, v in enumerate(s.table):
                if v == B.EMPTY:
                    continue
                tiles[(s.xmin + i // s.height, s.ymin + i % s.height)] = B.record(buf, s, i)[2]
            secs[(NAMES[bi], z)] = (s, tiles)
    return magic, secs


def parse(g):
    t = pb.tile()
    t.ParseFromString(gzip.decompress(g))
    return t


def stats(tiles):
    c = collections.Counter()
    raw = 0
    for g in tiles.values():
        t = parse(g)
        raw += len(gzip.decompress(g))
        for L in t.layers:
            for ft in L.features:
                cls = None
                for k in range(0, len(ft.tags), 2):
                    if L.keys[ft.tags[k]] == 'class':
                        cls = pyval(L.values[ft.tags[k + 1]])
                c[(L.name, cls)] += 1
    return c, raw


def lines(t, classes=('motorway', 'trunk', 'primary')):
    pts = []
    for L in t.layers:
        if L.name != 'transportation':
            continue
        for ft in L.features:
            cls = next((pyval(L.values[ft.tags[k + 1]]) for k in range(0, len(ft.tags), 2)
                        if L.keys[ft.tags[k]] == 'class'), None)
            if cls in classes:
                for p in decode_geom(list(ft.geometry)):
                    pts += p['pts']
    return pts


def match(a, b):
    pa, pb_ = lines(a), lines(b)
    if not pa or not pb_:
        return None
    pa = pa[::max(1, len(pa) // 200)]
    d = sorted(min(math.hypot(x - u, y - v) for u, v in pb_) for x, y in pa)
    return d[len(d) // 2]


def render(t, size=512):
    im = Image.new('RGB', (size, size), (250, 250, 245))
    dr = ImageDraw.Draw(im)
    s = size / 4096
    for L in t.layers:
        for ft in L.features:
            cls = next((pyval(L.values[ft.tags[k + 1]]) for k in range(0, len(ft.tags), 2)
                        if L.keys[ft.tags[k]] == 'class'), None)
            for p in decode_geom(list(ft.geometry)):
                xy = [(x * s, y * s) for x, y in p['pts']]
                if L.name == 'water' and len(xy) > 2:
                    dr.polygon(xy, fill=(170, 200, 240))
                elif L.name == 'place':
                    x, y = xy[0]
                    dr.ellipse([x - 2, y - 2, x + 2, y + 2], fill=(0, 0, 0))
                elif len(xy) > 1:
                    col = (80, 130, 220) if L.name == 'waterway' else (160, 0, 160) if L.name == 'boundary' \
                        else COLORS.get(cls, (100, 100, 100))
                    dr.line(xy, fill=col, width=1)
    return im


def main(theirs, ours, outprefix):
    _, A = load(theirs)
    _, O = load(ours)
    for key in sorted(set(A) | set(O)):
        sa, ta = A.get(key, (None, {}))
        so, to = O.get(key, (None, {}))
        ca, ra = stats(ta)
        co, ro = stats(to)
        print(f"\n=== {key[0]} z{key[1]}: theirs {len(ta)} tiles ({ra // 1024} KB raw) | ours {len(to)} tiles ({ro // 1024} KB raw)"
              f" | shared cells {len(set(ta) & set(to))}")
        for k in sorted(set(ca) | set(co), key=lambda k: -(ca[k] + co[k]))[:18]:
            print(f"    {k[0]:15s} {str(k[1]):12s} theirs={ca[k]:8d} ours={co[k]:8d}")
        if key[0] == 'b1':
            shared = sorted(set(ta) & set(to))
            scores = [m for m in (match(parse(ta[c]), parse(to[c])) for c in shared[::max(1, len(shared) // 40)]) if m is not None]
            if scores:
                scores.sort()
                print(f"    major-road geometry match (median dist, /4096): {scores[len(scores) // 2]:.1f} over {len(scores)} cells")
            # render the densest shared cell side by side
            if shared:
                c = max(shared, key=lambda c: len(ta[c]))
                im = Image.new('RGB', (1024, 512))
                im.paste(render(parse(ta[c])), (0, 0))
                im.paste(render(parse(to[c])), (512, 0))
                fn = f"{outprefix}_{key[0]}_z{key[1]}_{c[0]}_{c[1]}.png"
                im.save(fn)
                print(f"    rendered {fn} (left=theirs 2018, right=ours)")


if __name__ == '__main__':
    main(*sys.argv[1:4])
