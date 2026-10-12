# jobs · the Postgres job queue

- **What it does:** work that must survive a crash (processing a report, import batches, LLM back-fill) is a row in `jobs`, enqueued **in the same transaction** that created the work. The worker (`app/worker.py`, 4 threads) claims rows with `SELECT … FOR UPDATE SKIP LOCKED`, so two threads never take the same job.
- **Key table:** `jobs` (kind, lane, lane_rank, payload, dedupe_key, run_at, attempts, locked_by/at, done_at, dead_at, error).
- **The tricky rule:** a job whose worker died stays locked; after 60 s (`scheduler.job_reclaim_after`) any worker may claim it again. That makes delivery *at-least-once*, so every handler checks state first and is safe to run twice. Lanes set the claim order: live voice > WhatsApp/partner > import > surge > back-fill.
- **Failure:** an exception releases the job with exponential back-off (2, 4, 8 … ≤ 60 s); after `max_attempts` it is marked dead and shows up in the integrity check.
- **How to show it:** `SELECT kind, lane, attempts, locked_by, done_at FROM jobs ORDER BY id DESC LIMIT 5;` during a surge, then `docker compose kill worker` and restart it: nothing is lost.
