"""Independent final schema v4 conflict/immutability tests."""
import sqlite3
from pathlib import Path
import unittest

SCHEMA = (Path(__file__).resolve().parents[1]/"schema"/"index_v4.sql").read_text(encoding="utf-8")

class FinalSchema(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:")
        self.db.executescript(SCHEMA)
        self.db.execute("PRAGMA recursive_triggers=OFF")
    def tearDown(self):
        self.db.close()
    def reject(self,sql):
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute(sql)
    def test_version_and_identity(self):
        self.assertEqual(self.db.execute("PRAGMA user_version").fetchone(),(4,))
        self.assertEqual(self.db.execute("PRAGMA application_id").fetchone(),(1313098072,))
        self.assertEqual(self.db.execute("PRAGMA integrity_check").fetchone(),("ok",))
    def test_run_replacement_and_nonpositive_id(self):
        self.db.execute("INSERT INTO analysis_run(id,kind,path_policy,planned,omissions) VALUES(1,'discovery','omitted',0,0)")
        self.db.execute("INSERT INTO discovery_detail VALUES(1,0,0,0,0,0,0,0)")
        self.db.execute("UPDATE analysis_run SET sealed=1 WHERE id=1")
        self.reject("INSERT OR REPLACE INTO analysis_run(id,kind,path_policy,planned,omissions) VALUES(1,'analysis','omitted',0,0)")
        self.reject("INSERT INTO analysis_run(id,kind,path_policy,planned,omissions) VALUES(0,'analysis','omitted',0,0)")
        self.assertEqual(self.db.execute("SELECT kind,sealed FROM analysis_run").fetchall(),[("discovery",1)])
    def test_source_conflicts_and_detail_replacement(self):
        self.db.execute("INSERT INTO analysis_run VALUES(1,'discovery','logical_opt_in',2,0,0)")
        self.db.execute("INSERT INTO source_entry VALUES(1,1,X'01',X'0000000000000001','unknown','unexamined',NULL,NULL)")
        self.db.execute("INSERT INTO discovery_detail VALUES(1,2,2,0,0,0,0,0)")
        self.reject("INSERT OR REPLACE INTO source_entry VALUES(1,1,X'02',X'0000000000000002','unknown','unexamined',NULL,NULL)")
        self.reject("INSERT OR REPLACE INTO source_entry VALUES(1,2,X'01',X'0000000000000002','unknown','unexamined',NULL,NULL)")
        self.reject("INSERT OR REPLACE INTO discovery_detail VALUES(1,3,2,1,0,0,0,0)")
        self.assertEqual(self.db.execute("SELECT ordinal,hex(logical_key) FROM source_entry").fetchall(),[(1,"01")])
        self.reject("UPDATE analysis_run SET sealed=1 WHERE id=1")
    def test_report_replacement_before_seal(self):
        self.db.execute("INSERT INTO analysis_run VALUES(1,'analysis','omitted',0,0,0)")
        doc='{"schema_version":1,"path_policy":"omitted","summary":{"planned":0},"entries":[]}'
        self.db.execute("INSERT INTO report_document VALUES(1,1,?)",(doc,))
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT OR REPLACE INTO report_document VALUES(1,1,?)",(doc+" ",))
        self.db.execute("UPDATE analysis_run SET sealed=1 WHERE id=1")
        self.assertEqual(self.db.execute("SELECT payload FROM report_document").fetchone(),(doc,))
    def test_unsigned_charge_and_hint_constraints(self):
        self.db.execute("INSERT INTO analysis_run VALUES(1,'analysis','omitted',1,0,0)")
        self.reject("INSERT INTO source_entry VALUES(1,1,NULL,X'0000000000000001','invented','failed',NULL,X'0000000000000000')")
        self.reject("INSERT INTO source_entry VALUES(1,1,NULL,X'0000000000000001','png','not_started',NULL,X'0000000000000000')")
        self.reject("INSERT INTO source_entry VALUES(1,1,NULL,X'8000000000000000','unknown','observed',zeroblob(32),X'7FFFFFFFFFFFFFFF')")
        self.db.execute("INSERT INTO source_entry VALUES(1,1,NULL,X'8000000000000000','unknown','observed',zeroblob(32),X'FFFFFFFFFFFFFFFF')")
        self.assertEqual(self.db.execute("SELECT count(*) FROM source_entry").fetchone(),(1,))
if __name__=="__main__":
    unittest.main()
