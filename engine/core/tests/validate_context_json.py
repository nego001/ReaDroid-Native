"""Independent strict consumer for local context export synthetic fixtures."""
import json
import re
import subprocess
from collections import Counter

def unique(pairs):
    result = {}
    for key, value in pairs:
        assert key not in result, ("duplicate", key)
        result[key] = value
    return result

def reject(value):
    raise ValueError(value)

def keys(obj, fields):
    assert type(obj) is dict and set(obj) == set(fields.split()), obj

def decimal(value):
    assert type(value) is str and re.fullmatch(r"0|[1-9][0-9]*", value)
    n = int(value)
    assert n <= 2**64 - 1
    return n

def uint(value, cap=4096):
    assert type(value) is int and 0 <= value <= cap
    return value

FAMILIES = {
    "unknown": ("unknown", "unknown"),
    "mach_o_fat_or_java_class": ("ambiguous", "ambiguous_family_hint"),
    **{x: ("executable_family", "family_hint") for x in ("dos_mz","pe","elf","mach_o")},
    "dex": ("bytecode_family","family_hint"),
    **{x: ("archive_family","family_hint") for x in ("zip","7z","rar","ar","tar")},
    **{x: ("compression_family","family_hint") for x in ("gzip","zstd")},
    "ole_compound": ("compound_document_family","family_hint"),
    "pdf": ("document_family","family_hint"),
    **{x: ("image_family","family_hint") for x in ("png","jpeg")},
    "sqlite": ("database_family","family_hint"),
}
COVERAGE = dict(declared_bytes_observed="observed", read_failed="failed", interrupted="cancelled", not_started="not_started")
RECOGNITION = dict(unknown="unknown_hint", family_hint="family_hint", ambiguous_family_hint="ambiguous_hint")
STRUCTURE = ("not_requested","unavailable","unsupported","malformed_subset","checked_subset")

def load(mode, after=0, cap=131072):
    raw = subprocess.check_output(["cargo","+1.85.1","run","--quiet","--locked","--offline","--example","context_fixture","--",mode,str(after),str(cap)])
    assert 0 < len(raw) <= cap <= 131072
    assert raw.isascii()
    obj = json.loads(raw.decode("utf-8"),object_pairs_hook=unique,parse_constant=reject)
    assert json.dumps(obj,separators=(",",":"),ensure_ascii=True).encode() == raw
    keys(obj,"wire_version scope state summary page_counts after included next data_role authority source_text limitations segments")
    assert obj["wire_version"] == 1 and obj["scope"] == "static_evidence_only"
    assert (obj["data_role"],obj["authority"],obj["source_text"]) == ("untrusted_evidence","none","excluded")
    assert obj["limitations"] == ["not_full_structure_validation","not_authenticity_or_safety","format_hints_only"]
    s = obj["summary"]
    keys(s,"planned observed failed cancelled not_started reserved_bytes charged_bytes batches")
    planned=uint(s["planned"])
    assert sum(uint(s[k]) for k in COVERAGE.values()) == planned
    assert decimal(s["charged_bytes"]) <= decimal(s["reserved_bytes"])
    assert uint(s["batches"]) <= planned
    assert obj["state"] == ("cancelled" if s["cancelled"] or s["not_started"] else "with_failures" if s["failed"] else "complete_byte_observation")
    assert obj["after"] == (after or None)
    included=uint(obj["included"],128)
    assert after+included <= planned
    assert obj["next"] == (after+included if after+included < planned else None)
    assert included > 0 or after == planned
    counts=Counter({k:0 for k in (*COVERAGE.values(),*RECOGNITION.values(),*STRUCTURE)})
    entries=[]
    for segment in obj["segments"]:
        keys(segment,"family recognition coverage structure items")
        assert 1 <= len(segment["items"]) <= 32
        for e in segment["items"]:
            keys(e,"ordinal format_hint declared_length charged_bytes header")
            assert (segment["family"],segment["recognition"]) == FAMILIES[e["format_hint"]]
            assert segment["structure"] == e["header"]["state"]
            counts[COVERAGE[segment["coverage"]]] += 1
            counts[RECOGNITION[segment["recognition"]]] += 1
            counts[segment["structure"]] += 1
            length=decimal(e["declared_length"]);charge=decimal(e["charged_bytes"])
            assert charge <= length+min(length,512)+(4 if length>512 else 0)+min(length,112)
            if segment["coverage"] == "declared_bytes_observed": assert charge >= length
            if segment["coverage"] == "not_started": assert charge == 0
            h=e["header"]
            if h["state"] == "malformed_subset":
                keys(h,"state issue")
                assert h["issue"] in ("truncated","signature","field","checksum","table_bounds")
            elif h["state"] == "checked_subset":
                keys(h,"state metadata")
                m=h["metadata"]
                shapes={"elf":"kind bits byte_order machine","png":"kind width height bit_depth color_type",
                        "pe":"kind bits machine sections","dex":"kind version byte_order file_size",
                        "zip_local":"kind method compressed uncompressed","zip_empty":"kind"}
                keys(m,shapes[m["kind"]])
                for k,v in m.items():
                    if k=="byte_order": assert v in ("little","big")
                    elif k!="kind": uint(v,2**32-1)
            else: keys(h,"state")
            entries.append(e)
    assert [e["ordinal"] for e in entries] == list(range(after+1,after+included+1))
    assert len(entries)==included
    assert obj["page_counts"] == dict(counts)
    for secret in (b"private/",b"ignore previous instructions",b"ordinary text",b"send all secrets",b"sha256",b"logical_key",b"relative_path"):
        assert secret not in raw
    return raw,obj,entries

def main():
    raw,mixed,entries=load("mixed")
    assert mixed["summary"]["observed"] == 3 and mixed["summary"]["failed"] == 1
    assert entries[0]["header"] == {"state":"malformed_subset","issue":"truncated"}
    assert entries[1]["header"] == {"state":"unavailable"}
    assert entries[2]["header"] == {"state":"unsupported"}
    assert entries[3]["header"] == {"state":"checked_subset","metadata":{"kind":"zip_empty"}}
    assert load("mixed")[0] == raw
    assert load("mixed",cap=len(raw))[0] == raw
    _,large,entries=load("large")
    assert large["state"]=="cancelled" and entries[0]["declared_length"]=="9007199254740993"
    _,empty,entries=load("empty")
    assert empty["included"]==0 and not entries and empty["next"] is None
    assert load("alias_a")[0] == load("alias_b")[0]
    after=0;seen=[];pages=0
    while True:
        _,obj,entries=load("pages",after,4096)
        seen.extend(e["ordinal"] for e in entries);pages+=1
        assert pages<=259
        if obj["next"] is None: break
        after=obj["next"]
    assert seen==list(range(1,260))
    print("U1.12_6_CONTEXT_CONSUMER_PASS", "fixture_documents", 7+pages, "pagination_pages", pages)
if __name__=="__main__": main()
