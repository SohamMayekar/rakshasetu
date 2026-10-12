-- 011 · find a report's events by the report (its "received" event is written before its case exists).
CREATE INDEX events_entity_idx ON events (entity_type, entity_id);
