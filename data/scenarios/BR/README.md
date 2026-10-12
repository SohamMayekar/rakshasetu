# BR · Bihar floods (the live pack)

**Demo village: Thawe, Gopalganj district, Bihar.** Chosen at H0–H1 from real OpenStreetMap data (PRD §21 #6).

**The demo line** (Hindi; the judge may change the number of people):
> थावे गाँव में, दुर्गा मंदिर के पीछे, पुल के पास, छत पे 6 लोग फँसे हैं। पानी घुस गया है, एक बुज़ुर्ग हैं, दवाई चाहिए।
> *Thawe gaon mein, Durga mandir ke peeche, pul ke paas, chhat pe 6 log fase hain. Paani ghus gaya hai, ek buzurg hain, dawai chahiye.*
> ("In Thawe village, behind the Durga temple, near the bridge, 6 people are stuck on the roof. Water has come in, there's an elderly person, we need medicine.")

## Why Thawe and not a Muzaffarpur village (measured on the extract, 12 Oct 2026)

The PRD assumed a Muzaffarpur village whose temple and bridge are both mapped within 500 m. The data doesn't have one:
- Muzaffarpur district (inside its OSM boundary): **26 village points, 1 town, 31 places of worship**.
- No mapped village there has a place of worship within 2 km that is also within 500 m of a mapped bridge. The closest village case is Sirsian: Ramjanki Mandir is 648 m from the village point, but its nearest bridge is 1,186 m away.
- **Thawe (Gopalganj)**: the village point is **42 m** from "Thawe durga mata mandir" (OSM node 13686519640); the nearest bridge node is **112 m** from the temple (an unclassified road bridge); **no other place of worship within 1 km**, so the temple–bridge pair is unique.

Gopalganj sits on the Gandak in the North Bihar flood belt. The incident keeps **Muzaffarpur as a second district** (with its own teams and duty officer), which also shows district scoping. *The humans can swap the demo village: rerun the search in `scripts/import_osm.py` (m22) and edit this file and the pitch line.*

## Contents
- `incident.yaml`: the incident and its two districts (district centroids from the OSM boundaries).
- `teams.yaml`: 9 teams with capabilities, `has_app`, positions near real places and position ages; one radio-only SDRF boat, one out of service.
- `cases.yaml`: **generated** by `scripts/gen_seed_cases.py` (deterministic): 48 synthetic household reports at real OSM village points, in Hinglish, English and Devanagari, plus a village-only Low case and a no-location case. Each text has its `truth` next to it.
- `gazetteer/`: the OSM extract for Gopalganj and Muzaffarpur (+2 km): 72 named places, 22 temples, 2,800 bridge
  points (long bridges sampled every 150 m), schools, hospitals, stations, water towers; district boundaries.
  Built by `scripts/import_osm.py --pbf <extract>`; the ladder reads only these committed rows.

**Source and licence:** OpenStreetMap data © OpenStreetMap contributors, available under the Open Database License (ODbL). Extract: `https://download.openstreetmap.fr/extracts/asia/india/bihar.osm.pbf` (md5 `b0fb84e0ee39d8befa7f7d0985500ef1`, state timestamp 2026-10-12T16:25:00Z). The Overpass API was unreachable from the build sandbox (see `docs/STATUS.md`, BLOCKED).

**Synthetic:** every person, name and phone number here is invented and never dialled. Places are real.
