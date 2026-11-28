-- Prototype schema contract; not yet a production Rust persistence adapter.
-- Each caller connection must enable foreign_keys and verify user_version.
PRAGMA foreign_keys = ON;
BEGIN IMMEDIATE;
CREATE TABLE analysis_run (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL CHECK(kind IN ('discovery','analysis')),
    path_policy TEXT NOT NULL CHECK(path_policy IN ('omitted','logical_opt_in')),
    planned INTEGER NOT NULL CHECK(planned BETWEEN 0 AND 100000),
    omissions INTEGER NOT NULL CHECK(omissions BETWEEN 0 AND 100000),
    sealed INTEGER NOT NULL DEFAULT 0 CHECK(sealed IN (0,1)),
    CHECK(kind='discovery' OR (omissions=0 AND planned<=4096))
) STRICT;
CREATE TABLE source_entry (
    run_id INTEGER NOT NULL REFERENCES analysis_run(id),
    ordinal INTEGER NOT NULL CHECK(ordinal BETWEEN 1 AND 100000),
    logical_key BLOB CHECK(logical_key IS NULL OR length(logical_key) BETWEEN 1 AND 40000),
    declared_length BLOB NOT NULL CHECK(length(declared_length)=8),
    format_hint TEXT NOT NULL CHECK(length(format_hint) BETWEEN 1 AND 64),
    status TEXT NOT NULL CHECK(status IN ('unexamined','observed','failed','cancelled','not_started')),
    sha256 BLOB CHECK(sha256 IS NULL OR length(sha256)=32),
    charged_bytes BLOB CHECK(charged_bytes IS NULL OR length(charged_bytes)=8),
    PRIMARY KEY(run_id,ordinal),
    UNIQUE(run_id,logical_key),
    CHECK((status='observed' AND sha256 IS NOT NULL) OR (status!='observed' AND sha256 IS NULL)),
    CHECK((status='unexamined' AND charged_bytes IS NULL) OR (status!='unexamined' AND charged_bytes IS NOT NULL)),
    CHECK(status!='not_started' OR charged_bytes=X'0000000000000000')
) STRICT;
CREATE TRIGGER run_insert_guard BEFORE INSERT ON analysis_run
WHEN NEW.sealed!=0 BEGIN SELECT RAISE(ABORT,'run must begin unsealed'); END;
CREATE TRIGGER source_insert_guard BEFORE INSERT ON source_entry
BEGIN
    SELECT CASE WHEN NOT EXISTS(
        SELECT 1 FROM analysis_run r WHERE r.id=NEW.run_id AND r.sealed=0
        AND NEW.ordinal<=r.planned
        AND ((r.path_policy='omitted' AND NEW.logical_key IS NULL) OR
             (r.path_policy='logical_opt_in' AND NEW.logical_key IS NOT NULL))
        AND ((r.kind='discovery' AND NEW.status='unexamined' AND NEW.format_hint='unknown')
             OR (r.kind='analysis' AND NEW.status!='unexamined'))
    ) THEN RAISE(ABORT,'entry inconsistent with run') END;
END;
CREATE TRIGGER source_no_update BEFORE UPDATE ON source_entry
BEGIN SELECT RAISE(ABORT,'entries immutable'); END;
CREATE TRIGGER source_no_delete BEFORE DELETE ON source_entry
BEGIN SELECT RAISE(ABORT,'entries immutable'); END;
CREATE TRIGGER run_update_guard BEFORE UPDATE ON analysis_run
BEGIN
    SELECT CASE WHEN OLD.sealed!=0 OR NEW.sealed!=1 OR NEW.id!=OLD.id
        OR NEW.kind!=OLD.kind OR NEW.path_policy!=OLD.path_policy
        OR NEW.planned!=OLD.planned OR NEW.omissions!=OLD.omissions
        OR (SELECT count(*) FROM source_entry WHERE run_id=OLD.id)!=OLD.planned
        THEN RAISE(ABORT,'invalid seal') END;
END;
CREATE TRIGGER run_no_delete BEFORE DELETE ON analysis_run
BEGIN SELECT RAISE(ABORT,'runs immutable'); END;
CREATE VIEW sealed_run_summary AS
SELECT r.id,r.kind,r.planned,r.omissions,r.path_policy,
    count(e.ordinal) AS entries,
    sum(CASE WHEN e.status='observed' THEN 1 ELSE 0 END) AS observed,
    sum(CASE WHEN e.status='failed' THEN 1 ELSE 0 END) AS failed,
    sum(CASE WHEN e.status='cancelled' THEN 1 ELSE 0 END) AS cancelled,
    sum(CASE WHEN e.status='not_started' THEN 1 ELSE 0 END) AS not_started,
    CASE WHEN r.kind='discovery' THEN
        CASE WHEN r.omissions>0 THEN 'discovery_with_omissions' ELSE 'discovery_no_reported_omissions' END
    WHEN sum(CASE WHEN e.status IN ('cancelled','not_started') THEN 1 ELSE 0 END)>0 THEN 'cancelled'
    WHEN sum(CASE WHEN e.status='failed' THEN 1 ELSE 0 END)>0 THEN 'with_failures'
    ELSE 'complete_byte_observation' END AS state
FROM analysis_run r LEFT JOIN source_entry e ON e.run_id=r.id
WHERE r.sealed=1 GROUP BY r.id;
PRAGMA user_version=1;
COMMIT;
