"""BryMaps backend: device detection, map backup, and the OSM->.dat build pipeline.

Exposed to QML as a single `Backend` QObject. All long work runs on a worker thread and
reports progress via signals, so the UI never blocks.
"""
import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot, Property

def _res_base() -> Path:
    # bundled (PyInstaller) resources live under sys._MEIPASS; source layout is repo root
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


ENGINE = _res_base() / "engine"
DATA = _res_base() / "data"
sys.path.insert(0, str(ENGINE))
import bryton_build  # noqa: E402

GEOFABRIK_INDEX = "https://download.geofabrik.de/index-v1.json"
PLANETILER_JAR_URL = "https://github.com/onthegomap/planetiler/releases/latest/download/planetiler.jar"


def app_cache() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    p = Path(base) / "brymaps"
    p.mkdir(parents=True, exist_ok=True)
    return p


def find_java() -> str:
    for c in ("/usr/lib/jvm/java-21-openjdk-amd64/bin/java",
              "/usr/lib/jvm/java-21-openjdk/bin/java"):
        if Path(c).exists():
            return c
    return shutil.which("java") or "java"


def find_device() -> Path | None:
    """Locate a mounted Bryton (a filesystem with a MAP/ dir; label BRYTON on most)."""
    cands = []
    sys_ = platform.system()

    def looks_like(p: Path) -> bool:
        m = p / "MAP"
        return m.is_dir() and ((m / "Preload").is_dir() or (m / "Update").is_dir())

    if sys_ == "Linux":
        user = os.environ.get("USER", "")
        # only look at actual mount points, never recurse into them
        roots = [Path(f"/media/{user}"), Path("/media"), Path(f"/run/media/{user}"),
                 Path("/run/media"), Path("/mnt")]
        for b in roots:
            if not b.is_dir():
                continue
            for entry in b.iterdir():
                try:
                    if entry.is_dir() and looks_like(entry):
                        cands.append(entry)
                except OSError:
                    continue
    elif sys_ == "Darwin":
        for entry in Path("/Volumes").glob("*"):
            if (entry / "MAP").is_dir():
                cands.append(entry)
    elif sys_ == "Windows":
        import string
        for d in string.ascii_uppercase:
            root = Path(f"{d}:/")
            if (root / "MAP").is_dir():
                cands.append(root)
    return cands[0] if cands else None


def read_model(dev: Path | None) -> str:
    """Read the device model from System/device.txt or release.ini ([MODEL] Model=...)."""
    if not dev:
        return ""
    for rel in ("System/device.txt", "System/release.ini"):
        f = Path(dev) / rel
        try:
            for line in f.read_text(errors="ignore").splitlines():
                s = line.strip()
                if s.lower().startswith("model="):
                    val = s.split("=", 1)[1].strip()
                    if val:
                        return val if val.lower().startswith("bryton") else f"Bryton {val}"
        except OSError:
            continue
    return ""


class Backend(QObject):
    logLine = Signal(str)
    busyChanged = Signal()
    deviceChanged = Signal()
    progress = Signal(float)          # 0..1, -1 = indeterminate
    regionsLoaded = Signal("QVariantList")
    buildFinished = Signal(bool, str)  # ok, message

    def __init__(self):
        super().__init__()
        self._busy = False
        self._device = None
        self._model = ""
        self._regions = []
        threading.Thread(target=self._load_regions, daemon=True).start()
        self.refresh_device()

    # ---- properties ----
    def _get_busy(self):
        return self._busy
    busy = Property(bool, _get_busy, notify=busyChanged)

    def _get_device(self):
        return str(self._device) if self._device else ""
    devicePath = Property(str, _get_device, notify=deviceChanged)

    def _get_model(self):
        return self._model
    deviceModel = Property(str, _get_model, notify=deviceChanged)

    def _set_busy(self, v):
        if v != self._busy:
            self._busy = v
            self.busyChanged.emit()

    def _log(self, msg):
        self.logLine.emit(msg.rstrip())

    # ---- device ----
    @Slot()
    def refresh_device(self):
        self._device = find_device()
        self._model = read_model(self._device) if self._device else ""
        self.deviceChanged.emit()
        if self._device:
            self._log(f"Device found at {self._device}" + (f" — {self._model}" if self._model else ""))
        return self._get_device()

    @Slot(str)
    def backup_device(self, dest_dir):
        if self._busy:
            return
        threading.Thread(target=self._backup_worker, args=(dest_dir,), daemon=True).start()

    def _backup_worker(self, dest_dir):
        self._set_busy(True)
        self.progress.emit(-1)
        try:
            dev = self._device
            if not dev:
                raise RuntimeError("No device connected")
            dest = Path(dest_dir) / f"bryton-map-backup-{time.strftime('%Y%m%d-%H%M%S')}"
            dest.mkdir(parents=True, exist_ok=True)
            for sub in ("Preload", "Update"):
                src = Path(dev) / "MAP" / sub
                if src.is_dir():
                    self._log(f"Backing up MAP/{sub} ...")
                    shutil.copytree(src, dest / sub, dirs_exist_ok=True)
            self._log(f"Backup complete: {dest}")
            self.buildFinished.emit(True, f"Backup saved to {dest}")
        except Exception as e:
            self._log(f"Backup failed: {e}")
            self.buildFinished.emit(False, str(e))
        finally:
            self.progress.emit(0)
            self._set_busy(False)

    # ---- regions ----
    def _sizes(self):
        if getattr(self, "_size_map", None) is None:
            self._size_map = {}
            f = DATA / "geofabrik-sizes.json"
            try:
                self._size_map = json.loads(f.read_text())
            except Exception:
                pass
        return self._size_map

    def _parse_index(self, text):
        data = json.loads(text)
        sizes = self._sizes()
        regions = []
        parents = set()
        for feat in data["features"]:
            p = feat["properties"]
            pbf = (p.get("urls") or {}).get("pbf")
            if not pbf:
                continue
            par = p.get("parent") or ""
            parents.add(par)
            b = feat.get("geometry")
            regions.append({
                "id": p["id"], "name": p.get("name", p["id"]),
                "parent": par, "pbf": pbf,
                "bbox": _bbox_of(b) if b else None,
                "bytes": int(sizes.get(p["id"], 0)),
            })
        for r in regions:
            r["hasChildren"] = r["id"] in parents
        regions.sort(key=lambda r: (r["parent"] or "", r["name"] or ""))
        return regions

    def _load_regions(self):
        bundled = DATA / "geofabrik-index.json"
        cache = app_cache() / "geofabrik-index.json"

        # 1) show the full list immediately from whatever we already have (bundled or cache)
        for src in (cache, bundled):
            try:
                if src.exists():
                    regions = self._parse_index(src.read_text(encoding="utf-8"))
                    if len(regions) > 100:
                        self._regions = regions
                        self.regionsLoaded.emit(regions)
                        self._log(f"{len(regions)} regions available")
                        break
            except Exception:
                continue

        # 2) refresh from Geofabrik in the background; only replace if it parses fully
        if not cache.exists() or cache.stat().st_mtime < time.time() - 7 * 86400:
            try:
                self._log("Refreshing region list from Geofabrik ...")
                with urllib.request.urlopen(GEOFABRIK_INDEX, timeout=30) as r:
                    text = r.read().decode("utf-8")
                regions = self._parse_index(text)
                if len(regions) > 100:
                    cache.write_text(text, encoding="utf-8")
                    self._regions = regions
                    self.regionsLoaded.emit(regions)
                    self._log(f"{len(regions)} regions available (updated)")
            except Exception as e:
                self._log(f"Using bundled region list (online refresh failed: {e})")
        if not self._regions:
            self._log("No region list available — check your internet connection")

    @Slot(result="QVariantList")
    def regions(self):
        return self._regions

    def _region(self, rid):
        return next((r for r in self._regions if r["id"] == rid), None)

    # ---- build ----
    @Slot(str, str, str)
    def build_region(self, region_id, dest, code):
        if self._busy:
            return
        threading.Thread(target=self._build_worker,
                         args=(region_id, None, dest, code), daemon=True).start()

    @Slot(str, "QVariantList", str, str)
    def build_bbox(self, region_id, bounds, dest, code):
        if self._busy:
            return
        threading.Thread(target=self._build_worker,
                         args=(region_id, [float(x) for x in bounds], dest, code),
                         daemon=True).start()

    def _planetiler_jar(self):
        jar = app_cache() / "planetiler.jar"
        if not jar.exists():
            self._log("Downloading Planetiler (one-time, ~90 MB) ...")
            urllib.request.urlretrieve(PLANETILER_JAR_URL, jar)
        return jar

    def _build_worker(self, region_id, bounds, dest, code):
        self._set_busy(True)
        self.progress.emit(-1)
        try:
            region = self._region(region_id)
            if not region:
                raise RuntimeError("Unknown region")
            name = region["id"].split("/")[-1]
            work = app_cache() / "build" / name
            work.mkdir(parents=True, exist_ok=True)
            pbf = work / f"{name}.osm.pbf"
            if not pbf.exists() or pbf.stat().st_mtime < time.time() - 14 * 86400:
                self._log(f"Downloading OSM data for {region['name']} ...")
                urllib.request.urlretrieve(region["pbf"], pbf)
            mbtiles = work / f"{name}.mbtiles"
            jar = self._planetiler_jar()
            # shared base-data dir so the ~1 GB of Planetiler sources (water polygons,
            # natural earth, lake centerlines) download ONCE and are reused across builds
            shared = app_cache() / "planetiler"
            (shared / "data").mkdir(parents=True, exist_ok=True)
            cmd = [find_java(), "-Xmx4g", "-jar", str(jar),
                   f"--osm-path={pbf}", f"--output={mbtiles}", "--download", "--force"]
            if bounds:
                cmd.append("--bounds={},{},{},{}".format(*bounds))
            self._log("Generating vector tiles with Planetiler "
                      "(first run downloads ~1 GB of base data) ...")
            self._run(cmd, cwd=shared)
            self._log("Packing Bryton .dat ...")
            b = bounds or region["bbox"]
            path = bryton_build.build(str(mbtiles), dest, name, code or "CXX",
                                      tuple(b), log=self._log)
            self._log(f"Built {path}")
            self.buildFinished.emit(True, path)
        except Exception as e:
            self._log(f"Build failed: {e}")
            self.buildFinished.emit(False, str(e))
        finally:
            self.progress.emit(0)
            self._set_busy(False)

    @Slot(str, str)
    def install_to_device(self, dat_path, clear_cache):
        try:
            dev = self._device
            if not dev:
                raise RuntimeError("No device connected")
            up = Path(dev) / "MAP" / "Update"
            up.mkdir(exist_ok=True)
            shutil.copy2(dat_path, up / Path(dat_path).name)
            if clear_cache == "true":
                data = Path(dev) / "MAP" / "Data"
                for f in data.rglob("*"):
                    if f.is_file():
                        f.unlink()
            self._log(f"Installed {Path(dat_path).name} to device")
            self.buildFinished.emit(True, "Installed to device — eject before unplugging")
        except Exception as e:
            self.buildFinished.emit(False, str(e))

    def _run(self, cmd, cwd):
        p = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True, bufsize=1)
        for line in p.stdout:
            s = line.rstrip()
            if any(k in s for k in ("INF", "ERROR", "Exception", "%")) and "argument:" not in s:
                self._log(s[-140:])
        if p.wait() != 0:
            raise RuntimeError("Planetiler failed")


def _bbox_of(geom):
    xs, ys = [], []

    def walk(c):
        if isinstance(c, (int, float)):
            return
        if c and isinstance(c[0], (int, float)):
            xs.append(c[0]); ys.append(c[1]); return
        for x in c:
            walk(x)
    walk(geom.get("coordinates", []))
    if not xs:
        return None
    return [min(xs), min(ys), max(xs), max(ys)]
