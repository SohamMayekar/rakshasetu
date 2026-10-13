# MH · Mumbai floods (the live pack)

**Demo neighbourhood: Kurla West, Mumbai Suburban, by the Mithi river.** The Mithi floods the low-lying settlements
along its banks in Kurla in a heavy monsoon; the team and the judges know these streets.

## The demo spot (measured on the extract, 12 Oct 2026)
- **Kurla West** is a mapped suburb (OSM). Mumbai maps most neighbourhoods as two halves, so callers who just say
  "Kurla" match a **derived** place joining Kurla East and Kurla West (`osm_type: derived` in `places.csv`; built by
  `join_halves()` in `scripts/import_osm.py`; 15 such places, never shown as OSM features).
- **"shankar mandir (kranti nagar central railway colony)"** (OSM node 2930720778) is **117 m** from a mapped
  bridge on Railway Colony Road and about 1 km from the Kurla West point. Unlike Thawe, a Mumbai neighbourhood has
  several temples within 1 km, so the caller naming the temple ("Shankar mandir") is what makes the circle tight.

## Contents
- `incident.yaml`: the incident and its two districts, **Mumbai Suburban** (the live desk) and **Mumbai City**;
  centroids from the OSM boundaries ("Mumbai Suburban District", "Mumbai City District", given as `osm:`).
- `teams.yaml`: 16 teams (NDRF, SDRF, the fire brigade as "Fire & Rescue", police, Aapda Mitra, a Koli fishermen's
  boat), one radio-only NDRF boat for the demo, one out of service.
- `cases.yaml`: **generated** by `scripts/gen_seed_cases.py --pack MH` (deterministic): 48 synthetic reports at real
  OSM places (Kurla, Kalina, Saki Naka, Jarimari, Chembur, Ghatkopar, Vikhroli, Govandi, Mankhurd, Andheri East,
  Malad West, Bandra East, Dharavi, Sion Koliwada, Wadala, Parel): water in ground floors, people stuck in
  buildings, chawls and stalled buses, landslides on the Vikhroli, Ghatkopar and Chembur hillsides; plus a
  place-only Low case and a no-location case.
- `gazetteer/`: the OSM extract for the two districts (+2 km): 936 places, 4,399 bridge points (flyovers and foot
  over-bridges included), 163 stations, 1,508 hospitals, 763 schools and campuses (colleges and universities),
  453 temples, 170 mosques, 109 churches, 349 markets and big retail (supermarkets, department stores, wholesale,
  malls — a named "DMart in Powai" pins), 115 police stations; district boundaries.
  Built by `python scripts/import_osm.py --pack MH --pbf <extract>`; the ladder reads only these committed rows.

**Source and licence:** OpenStreetMap data © OpenStreetMap contributors, available under the Open Database License
(ODbL). Extract: `https://download.openstreetmap.fr/extracts/asia/india/maharashtra.osm.pbf`
(md5 `dfd802f82a50345d1ab2a80807348cda`, downloaded 13 Oct 2026).

**Synthetic:** every person, name and phone number here is invented and never dialled. Places are real.
