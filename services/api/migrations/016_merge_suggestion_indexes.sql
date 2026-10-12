-- 016 · open suggestions by case, from either side: the queue's "Review match →" per row, the drawer's matches
-- and every merge decision look them up this way. Without these, a surge (7,000 suggestions × 2,800 open
-- cases) made GET /v1/queue take 3.4 s in the database.
CREATE INDEX merge_suggestions_case_idx ON merge_suggestions (case_id) WHERE status = 'open';
CREATE INDEX merge_suggestions_candidate_idx ON merge_suggestions (candidate_case_id) WHERE status = 'open';
