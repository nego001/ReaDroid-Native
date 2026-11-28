-- Fresh schema v4; no in-place migration from previous versions.
-- Each caller connection must enable foreign_keys and verify user_version.
PRAGMA foreign_keys = ON;
PRAGMA recursive_triggers = ON;
BEGIN IMMEDIATE;
CREATE TABLE analysis_run (
    id INTEGER PRIMARY KEY CHECK(id>0),
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
    format_hint TEXT NOT NULL CHECK(format_hint IN ('unknown','zip','dos_mz','pe','elf','mach_o','mach_o_fat_or_java_class','dex','gzip','zstd','7z','rar','ole_compound','ar','tar','pdf','png','jpeg','sqlite')),
    status TEXT NOT NULL CHECK(status IN ('unexamined','observed','failed','cancelled','not_started')),
    sha256 BLOB CHECK(sha256 IS NULL OR length(sha256)=32),
    charged_bytes BLOB CHECK(charged_bytes IS NULL OR length(charged_bytes)=8),
    PRIMARY KEY(run_id,ordinal),
    UNIQUE(run_id,logical_key),
    CHECK((status='observed' AND sha256 IS NOT NULL) OR (status!='observed' AND sha256 IS NULL)),
    CHECK((status='unexamined' AND charged_bytes IS NULL) OR (status!='unexamined' AND charged_bytes IS NOT NULL)),
    CHECK(status!='not_started' OR (charged_bytes=X'0000000000000000' AND format_hint='unknown')),
    CHECK(status!='observed' OR charged_bytes>=declared_length)
) STRICT, WITHOUT ROWID;
CREATE TABLE discovery_detail (
    run_id INTEGER PRIMARY KEY REFERENCES analysis_run(id),
    visited INTEGER NOT NULL CHECK(visited BETWEEN 0 AND 100000),
    files INTEGER NOT NULL CHECK(files BETWEEN 0 AND 100000),
    directories INTEGER NOT NULL CHECK(directories BETWEEN 0 AND 100000),
    links INTEGER NOT NULL CHECK(links BETWEEN 0 AND 100000),
    special INTEGER NOT NULL CHECK(special BETWEEN 0 AND 100000),
    invalid_names INTEGER NOT NULL CHECK(invalid_names BETWEEN 0 AND 100000),
    depth_skipped INTEGER NOT NULL CHECK(depth_skipped BETWEEN 0 AND directories),
    CHECK(visited=files+directories+links+special+invalid_names)
) STRICT;
CREATE TRIGGER discovery_insert_guard BEFORE INSERT ON discovery_detail
BEGIN
    SELECT CASE WHEN EXISTS(SELECT 1 FROM discovery_detail WHERE run_id=NEW.run_id) THEN RAISE(ABORT,'duplicate discovery detail') END;
    SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM analysis_run r WHERE r.id=NEW.run_id
        AND r.kind='discovery' AND r.sealed=0 AND r.planned=NEW.files
        AND r.omissions=NEW.links+NEW.special+NEW.invalid_names+NEW.depth_skipped)
        THEN RAISE(ABORT,'invalid discovery detail') END;
END;
CREATE TRIGGER discovery_no_update BEFORE UPDATE ON discovery_detail
BEGIN SELECT RAISE(ABORT,'discovery detail immutable'); END;
CREATE TRIGGER discovery_no_delete BEFORE DELETE ON discovery_detail
BEGIN SELECT RAISE(ABORT,'discovery detail immutable'); END;
CREATE TABLE report_document (
    run_id INTEGER PRIMARY KEY REFERENCES analysis_run(id),
    schema_version INTEGER NOT NULL CHECK(schema_version IN (1,2)),
    payload TEXT NOT NULL CHECK(length(CAST(payload AS BLOB)) BETWEEN 1 AND 16777216)
) STRICT;
CREATE TRIGGER document_insert_guard BEFORE INSERT ON report_document
BEGIN
    SELECT CASE WHEN EXISTS(SELECT 1 FROM report_document WHERE run_id=NEW.run_id) THEN RAISE(ABORT,'duplicate report document') END;
    SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM analysis_run r WHERE r.id=NEW.run_id
        AND r.kind='analysis' AND r.sealed=0) THEN RAISE(ABORT,'invalid report run') END;
    SELECT CASE WHEN json_valid(NEW.payload)!=1 THEN RAISE(ABORT,'invalid report JSON') END;
    SELECT CASE WHEN json_extract(NEW.payload,'$.schema_version') IS NOT NEW.schema_version
        OR json_extract(NEW.payload,'$.path_policy') IS NOT (SELECT path_policy FROM analysis_run WHERE id=NEW.run_id)
        OR json_extract(NEW.payload,'$.summary.planned') IS NOT (SELECT planned FROM analysis_run WHERE id=NEW.run_id)
        OR json_type(NEW.payload,'$.entries') IS NOT 'array'
        OR json_array_length(NEW.payload,'$.entries') IS NOT (SELECT planned FROM analysis_run WHERE id=NEW.run_id)
        THEN RAISE(ABORT,'report metadata mismatch') END;
END;
CREATE TRIGGER document_no_update BEFORE UPDATE ON report_document
BEGIN SELECT RAISE(ABORT,'documents immutable'); END;
CREATE TRIGGER document_no_delete BEFORE DELETE ON report_document
BEGIN SELECT RAISE(ABORT,'documents immutable'); END;
CREATE TRIGGER run_insert_guard BEFORE INSERT ON analysis_run
BEGIN
    SELECT CASE WHEN NEW.sealed!=0 THEN RAISE(ABORT,'run must begin unsealed') END;
    SELECT CASE WHEN EXISTS(SELECT 1 FROM analysis_run WHERE id=NEW.id) THEN RAISE(ABORT,'duplicate run') END;
END;
CREATE TRIGGER source_insert_guard BEFORE INSERT ON source_entry
BEGIN
    SELECT CASE WHEN EXISTS(SELECT 1 FROM source_entry WHERE run_id=NEW.run_id AND (ordinal=NEW.ordinal OR logical_key=NEW.logical_key)) THEN RAISE(ABORT,'duplicate source') END;
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
        OR (OLD.kind='analysis' AND NOT EXISTS(SELECT 1 FROM report_document WHERE run_id=OLD.id))
        OR (OLD.kind='discovery' AND NOT EXISTS(SELECT 1 FROM discovery_detail WHERE run_id=OLD.id))
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
PRAGMA application_id=1313098072;
PRAGMA user_version=4;
COMMIT;
