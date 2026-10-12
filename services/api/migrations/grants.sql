-- Re-applied after every migration run (idempotent). Rule R9: the app role owns nothing,
-- and has INSERT + SELECT only on `events`, so the application cannot edit history.
GRANT USAGE ON SCHEMA public TO rakshasetu_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO rakshasetu_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO rakshasetu_app;
REVOKE UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON events FROM rakshasetu_app;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON schema_migrations FROM rakshasetu_app;
