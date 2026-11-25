"""SQLite schema contract using only synthetic fixtures; no production adapter."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

SCHEMA = (Path(__file__).resolve().parents[1] / "schema" / "index_v1.sql").read_text(encoding="utf-8")

def u64(n):
    return n.to_bytes(8, "big")

def connect(path):
    c = sqlite3.connect(path)
    c.execute("PRAGMA foreign_keys=ON")
    return c

def init(c):
    c.executescript(SCHEMA)

def run(c, planned=1, kind="analysis", policy="omitted", omissions=0):
    return c.execute("INSERT INTO analysis_run(kind,path_policy,planned,omissions) VALUES(?,?,?,?)",
                     (kind,policy,planned,omissions)).lastrowid

def entry(c, rid, ordinal=1, status="observed", key=None, length=2**64-1, digest=b"x"*32):
    charged = None if status=="unexamined" else u64(0 if status=="not_started" else 8)
    c.execute("INSERT INTO source_entry VALUES(?,?,?,?,?,?,?,?)",
              (rid,ordinal,key,u64(length),"unknown",status,digest,charged))

def seal(c,rid):
    c.execute("UPDATE analysis_run SET sealed=1 WHERE id=?",(rid,))

class Contract(unittest.TestCase):
    def setUp(self):
        self.c=connect(":memory:")
        init(self.c)
    def tearDown(self):
        self.c.close()
    def test_incomplete_not_visible_and_cannot_seal(self):
        rid=run(self.c,2)
        entry(self.c,rid)
        self.assertEqual(self.c.execute("SELECT count(*) FROM sealed_run_summary").fetchone()[0],0)
        with self.assertRaises(sqlite3.IntegrityError): seal(self.c,rid)
        entry(self.c,rid,2,status="failed",digest=None)
        seal(self.c,rid)
        self.assertEqual(self.c.execute("SELECT state,observed,failed FROM sealed_run_summary").fetchone(),("with_failures",1,1))
    def test_cancelled_and_discovery_not_complete_observation(self):
        rid=run(self.c)
        entry(self.c,rid,status="not_started",digest=None);seal(self.c,rid)
        did=run(self.c,kind="discovery",omissions=3)
        entry(self.c,did,status="unexamined",digest=None);seal(self.c,did)
        self.assertEqual(self.c.execute("SELECT state FROM sealed_run_summary ORDER BY id").fetchall(),
                         [("cancelled",),("discovery_with_omissions",)])
    def test_hash_invariants(self):
        rid=run(self.c)
        for status,digest in [("observed",None),("failed",b"x"*32),("observed",b"x")]:
            with self.assertRaises(sqlite3.IntegrityError): entry(self.c,rid,status=status,digest=digest)
    def test_privacy_and_duplicates(self):
        rid=run(self.c,2)
        with self.assertRaises(sqlite3.IntegrityError): entry(self.c,rid,key=b"private")
        rid=run(self.c,2,policy="logical_opt_in")
        with self.assertRaises(sqlite3.IntegrityError): entry(self.c,rid)
        entry(self.c,rid,key=b"key")
        with self.assertRaises(sqlite3.IntegrityError): entry(self.c,rid,2,key=b"key")
        with self.assertRaises(sqlite3.IntegrityError): entry(self.c,rid,3,key=b"other")
    def test_sealed_immutable(self):
        rid=run(self.c);entry(self.c,rid);seal(self.c,rid)
        for sql in ["UPDATE source_entry SET status='failed'", "DELETE FROM source_entry",
                    "UPDATE analysis_run SET sealed=0","DELETE FROM analysis_run"]:
            with self.assertRaises(sqlite3.IntegrityError): self.c.execute(sql)
        with self.assertRaises(sqlite3.IntegrityError): entry(self.c,rid)
    def test_empty_run(self):
        rid=run(self.c,0);seal(self.c,rid)
        self.assertEqual(self.c.execute("SELECT entries,observed,state FROM sealed_run_summary").fetchone(),(0,0,"complete_byte_observation"))
    def test_persistence_and_rollback(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"synthetic.sqlite"
            c=connect(path);init(c)
            with c:
                rid=run(c);entry(c,rid);seal(c,rid)
            try:
                with c:
                    bad=run(c,2);entry(c,bad);seal(c,bad)
            except sqlite3.IntegrityError: pass
            else: self.fail("incomplete transaction committed")
            c.close()
            c=connect(path)
            self.assertEqual(c.execute("PRAGMA user_version").fetchone()[0],1)
            self.assertEqual(c.execute("SELECT count(*) FROM analysis_run").fetchone()[0],1)
            self.assertEqual(c.execute("SELECT declared_length FROM source_entry").fetchone()[0],u64(2**64-1))
            self.assertEqual(c.execute("PRAGMA integrity_check").fetchone()[0],"ok")
            self.assertEqual(c.execute("PRAGMA foreign_key_check").fetchall(),[])
            c.close()

if __name__=="__main__":
    unittest.main()
