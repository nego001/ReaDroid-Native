"""Independent strict JSON consumer for synthetic Rust report fixtures only."""
import hashlib
import json
import subprocess


def unique_object(pairs):
    obj = {}
    for key, value in pairs:
        assert key not in obj, f"duplicate JSON key: {key}"
        obj[key] = value
    return obj


def reject_constant(value):
    raise ValueError(f"non-JSON constant: {value}")


def decimal(value):
    assert isinstance(value, str) and value.isascii() and value.isdecimal()
    n = int(value)
    assert str(n) == value and 0 <= n <= 2**64 - 1
    return n


def load(mode):
    raw = subprocess.check_output([
        "cargo", "+1.85.1", "run", "--quiet", "--locked", "--offline",
        "--example", "report_fixture", "--", mode,
    ])
    assert 0 < len(raw) <= 16 * 1024 * 1024
    obj = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object,
                     parse_constant=reject_constant)
    assert obj["schema_version"] == 1
    assert obj["scope"] == "caller_supplied_sources"
    assert "signature_hint_not_structural_validation" in obj["limitations"]
    summary, entries = obj["summary"], obj["entries"]
    assert summary["planned"] == len(entries)
    assert [e["id"] for e in entries] == list(range(1, len(entries) + 1))
    counts = {status: 0 for status in ("observed", "failed", "cancelled", "not_started")}
    charged = reserved = 0
    for entry in entries:
        status = entry["status"]
        counts[status] += 1
        length = decimal(entry["declared_length"])
        amount = decimal(entry["charged_bytes"])
        maximum = length + min(length, 512) + (4 if length > 512 else 0)
        assert amount <= maximum
        charged += amount
        reserved += maximum
        if status == "observed":
            assert len(entry["sha256"]) == 64
            assert all(c in "0123456789abcdef" for c in entry["sha256"])
            assert entry["error_kind"] is None
        else:
            assert entry["sha256"] is None
        if obj["path_policy"] == "omitted":
            assert not {"root", "relative_path", "members"} & entry.keys()
    assert all(summary[k] == v for k, v in counts.items())
    assert decimal(summary["charged_bytes"]) == charged
    assert decimal(summary["reserved_bytes"]) == reserved
    print(f"JSON consumer PASS: {mode}", flush=True)
    return obj, raw


def main():
    omitted, raw = load("mixed_omit")
    included, _ = load("mixed_include")
    assert b"private" not in raw and b"nested" not in raw
    assert omitted["path_policy"] == "omitted"
    assert included["path_policy"] == "logical_opt_in"
    assert omitted["state"] == included["state"] == "with_failures"
    assert omitted["summary"] == included["summary"]
    assert omitted["summary"]["observed"] == 2
    assert omitted["summary"]["failed"] == 1
    entries = included["entries"]
    assert entries[0]["relative_path"] == 'a-private-"á.zip'
    assert entries[0]["members"] == ["nested/配置.json"]
    assert decimal(entries[0]["root"]) == 9_007_199_254_740_993
    assert entries[0]["sha256"] == hashlib.sha256(b"abc").hexdigest()
    assert entries[1]["sha256"] == hashlib.sha256(b"").hexdigest()
    assert entries[2]["error_kind"] == "UnexpectedEof"
    assert [{k: v for k, v in e.items() if k not in {"root", "relative_path", "members"}}
            for e in entries] == omitted["entries"]
    assert load("mixed_omit")[1] == raw
    cancelled, _ = load("cancelled")
    assert cancelled["state"] == "cancelled"
    assert cancelled["summary"]["not_started"] == 1
    assert cancelled["summary"]["charged_bytes"] == "0"
    assert decimal(cancelled["entries"][0]["declared_length"]) == 9_007_199_254_740_993
    empty, _ = load("empty")
    assert empty["state"] == "complete_byte_observation"
    assert empty["entries"] == [] and empty["summary"]["batches"] == 0
    print("U1.7_JSON_INDEPENDENT_CONSUMER_PASS", flush=True)


if __name__ == "__main__":
    main()
