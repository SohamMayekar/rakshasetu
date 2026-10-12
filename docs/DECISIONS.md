# Decisions

*One paragraph per real decision, with the alternative we rejected. Newest last.*


### D2 · Base images from public.ecr.aws
Docker Hub returns 429 to anonymous pulls in the build sandbox (and venue NAT can trigger the same limit). The Dockerfiles use `public.ecr.aws/docker/library/{python,node,caddy}`, which mirror the official images for free with no account. PostGIS comes from `postgis/postgis` (not mirrored there). **Rejected:** Docker Hub defaults (rate-limited) and a paid registry (zero budget).
