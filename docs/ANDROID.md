# Android — status and plan

The desktop app (Windows/Linux) is the working target today. Android is planned but not yet
built. This note records the intended approach so it isn't re-derived later.

## Why it's not trivial

The Aero 60 / Rider 450 mount as **USB mass storage**. On Android that means the app needs
USB-OTG plus access to a FAT-formatted USB volume (SAF `ACTION_OPEN_DOCUMENT_TREE`, or raw
access via the USB host API). Reading/writing the device's `MAP/` folder over SAF is doable
but fiddlier than the desktop's plain filesystem path.

The build pipeline also uses **Planetiler (Java)**, which is heavy for a phone. The realistic
Android design offloads the tile build:

- **Option A (recommended):** phone app is a *thin client* — it lists Geofabrik regions, lets
  you pick one, and downloads a **prebuilt `.dat`** from a small server (or a GitHub release
  of common regions), then writes it to the device over USB-OTG/SAF. No Planetiler on-device.
- **Option B:** full on-device build with a cloud build step; phone only does region select +
  USB write.

## UI reuse

The ambit-app (Sommet) Android client is React Native. A BryMaps Android client would reuse its
theme tokens (`android/src/theme/v3.ts`) and screen scaffolding, mirroring this desktop app's
three actions: **region list → build/fetch → backup + install over USB**.

## Milestone checklist

- [ ] SAF/USB-OTG read + write of a Bryton `MAP/` volume
- [ ] Region list (same Geofabrik index as desktop)
- [ ] Fetch prebuilt `.dat` (Option A) and write to `MAP/Update`, clear `MAP/Data`
- [ ] Backup `MAP/Preload` + `MAP/Update` to phone storage
