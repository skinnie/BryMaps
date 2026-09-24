# BryMaps

Fresh OpenStreetMap maps for **Bryton Aero 60** and **Rider 450** GPS cycling computers.

Bryton removed the map-download function from their tools and the old links don't work. If you have one of these units, the on-device map is
frozen at whatever shipped in 2018 — no new roads, no new paths. 
BryMaps rebuilds the exact
on-device map format from current OpenStreetMap data, so you can put an up-to-date map on the
device yourself.

- **Pick a country or region** from the free [Geofabrik](https://download.geofabrik.de)
  extract list (updated daily).
- **Build** a Bryton-format `.dat` map from current OSM data.
- **Back up** the maps already on your device before changing anything.
- **Install** the new map straight to the connected device.

Windows and Linux desktop app.

> Not affiliated with or endorsed by Bryton. OpenStreetMap data © OpenStreetMap contributors,
> ODbL. Use at your own risk — always keep the backup BryMaps makes.
> Vibecoded with Claude, tested on Aero 60

## How it works

The Aero 60 / Rider 450 read a container format (`MAP/Preload/*.dat`, `MAP/Update/*.dat`) whose
tiles are standard [Mapbox Vector Tiles](https://github.com/mapbox/vector-tile-spec) in the
OpenMapTiles schema, gzipped and packed behind a small index. BryMaps:

1. downloads the OSM extract for the chosen region (Geofabrik),
2. renders current vector tiles with [Planetiler](https://github.com/onthegomap/planetiler),
3. packs them into the Bryton container (`engine/bryton_build.py`), matching the device's own
   layer set (transportation / water / waterway / boundary / place) and zoom layout.

The container format and the build pipeline were reverse-engineered by round-tripping the
device's own map files byte-for-byte; see [docs/FORMAT.md](docs/FORMAT.md).

## Install (from source)

Requires Python 3.10+ and Java 21+ (for Planetiler, downloaded automatically on first build).

```bash
git clone https://github.com/skinnie/BryMaps
cd BryMaps
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python brymaps/main.py
```

Prebuilt Windows/Linux bundles are attached to each
[release](https://github.com/skinnie/BryMaps/releases).

## Usage

1. Plug the Bryton in over USB (it appears as a `BRYTON` USB drive). BryMaps detects it.
2. **Back up device maps to disk** first — one click, keep it safe.
3. Search and select a region (pick the smallest that covers where you ride — smaller is faster
   to build and quicker to load on the device).
4. **Build this map.** Output goes to the device's `MAP/Update` folder by default, or a folder
   you choose.
5. **Install last build to device** (this also clears the device's render cache, which Bryton's
   own manual instructs after adding a map). Eject before unplugging.

To go back to the original map, restore the folder from your backup.

## Command line

The build engine runs standalone too:

```bash
.venv/bin/python engine/bryton_build.py region.mbtiles \
    --name nord-pas-de-calais --code CNP --bounds 1.28,49.97,4.27,51.28 --z12 native
```

## Credits

- Map data © OpenStreetMap contributors ([ODbL](https://www.openstreetmap.org/copyright))
- Region extracts by [Geofabrik](https://download.geofabrik.de)
- Vector tiles by [Planetiler](https://github.com/onthegomap/planetiler) /
  [OpenMapTiles](https://github.com/openmaptiles/openmaptiles) schema
- UI theme reused from the Sommet (ambit-app) desktop project

## License

MIT — see [LICENSE](LICENSE).
