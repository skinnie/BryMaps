# Bryton Aero 60 / Rider 450 map container format

Reverse-engineered by round-tripping the device's own map files: BryMaps can unpack every
`.dat` on a device and repack it **byte-for-byte identically** (verified on the factory
Taiwan, New Zealand and South Africa maps), which is the proof the format below is correct.

## File layout

Maps live in `MAP/Preload/` and `MAP/Update/`, named `{xmin}-{ymin}-{xmax}-{ymax}-{name}.dat`
where the four numbers are the **zoom-9 tile bounding box** (Web Mercator, TMS Y).

```
offset 0   6   "P" + <2-char region code> + "00"     e.g. "PCTW00" (Taiwan)
       6   u32  version (1)
      10   u32  offset of block 1  (base map)
      14   u32  offset of block 2  (place labels)
      18   u32  offset of block 3  (paths / tracks)
```

Each **block** is an 80-byte header; at `+36` an array of `u32` zoom slots, one per zoom level
starting at z9 (`slot[z-9]`), giving the byte offset (relative to the block) of that zoom's
**section**, or 0 if absent.

- block 1: z9 (major roads) + z12 (all roads) — the base map
- block 2: z9–z12 — `place` labels
- block 3: z14 — `path` / `track`

## Section

```
offset 0    6   "BRYTON"
       6    u16 version (1)
       8    u16 zoom
      10    u32 1
      14    u16 0
      16    u32 xmin, xmax, ymin, ymax   (tile bbox at this zoom)
      32    u8  4, u8 4
      34    u32 dataOffset = 100 + 4*cellCount
     100    u32[cellCount] index table   (see below)
  dataOffset  packed tile records
```

`cellCount = (xmax-xmin+1) * (ymax-ymin+1)`. The index table is **column-major**, TMS Y:

```
index = (x - xmin) * height + (y - ymin)
```

Value `0xFFFFFFFF` means empty cell. Otherwise it is the byte offset (relative to
`dataOffset`) of that tile's record:

```
u32 length
<gzip stream>          gzip: mtime = 0x5B76B000, XFL=02, OS=0xFF
u8 0, u8 0             two-byte trailer
```

## Tile payload

Each gzip stream decompresses to a **Mapbox Vector Tile v1**, extent 4096, in the
**OpenMapTiles** schema. The device uses only these layers/properties:

| layer | keys | notes |
|---|---|---|
| `transportation` | `class, subclass, ramp, oneway, brunnel, layer, service, level, indoor` | classes vary by zoom |
| `water` | `class` | ocean / lake / river polygons |
| `waterway` | `class, name, brunnel` | rivers / canals |
| `boundary` | `admin_level, disputed, maritime` | admin_level ≤ 6 |
| `place` | `name, rank, class, capital, iso_a2` | block 2 only |

Integer properties are encoded as protobuf `int_value` (not `sint_value` — this matters; the
device's own tiles use `int_value`).

`engine/bryton_build.py` produces exactly this from a Planetiler OpenMapTiles `.mbtiles`.

### z12 base-map density (`--z12` mode)

- `native` (default): use Planetiler's native z12 tiles. Lightest, renders fastest; town
  residential streets appear when you zoom to z14.
- `z13`: merge the 4 z13 children for local streets — restores the medium-zoom street grid at
  ~1.3× the device's own vertex count.
- `z14`: merge all 16 z14 children at full detail — most detailed but 2–3× the vertices, slow
  to render. Not recommended.
