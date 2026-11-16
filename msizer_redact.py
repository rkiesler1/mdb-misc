#!/usr/bin/env python3
"""Redact database, collection, index, and index field names from an msizer JSON file.

Usage: python3 msizer_redact.py <input.json> > redacted.json
"""
import json
import sys

REDACTED = "[REDACTED]"


def make_mapper():
    """Maintain consistent mappings so the same name always maps to the same placeholder."""
    maps = {"db": {}, "coll": {}, "index": {}, "field": {}}
    counts = {"db": 0, "coll": 0, "index": 0, "field": 0}

    def redact(kind, name):
        m = maps[kind]
        if name not in m:
            counts[kind] += 1
            m[name] = f"{kind.upper()}_{counts[kind]}_{REDACTED}"
        return m[name]

    return redact


def redact_index_key(key, redact):
    """Redact field names in an index key definition, preserving sort directions."""
    if not isinstance(key, dict):
        return key
    out = {}
    for field, direction in key.items():
        # keep special nested forms like $** wildcard / metadata fields readable
        if field.startswith("$"):
            out[field] = direction
        else:
            out[redact("field", field)] = direction
    return out


def redact_index_stat(stat, redact):
    out = {}
    for k, v in stat.items():
        if k == "name":
            out[k] = redact("index", v)
        elif k in ("key", "keyPattern"):
            out[k] = redact_index_key(v, redact)
        elif k == "weights":
            out[k] = {redact("field", f): w for f, w in v.items()} if isinstance(v, dict) else v
        elif k in ("partialFilterExpression", "wildcardProjection"):
            out[k] = v  # keep as-is; expressions would need a full parser
        else:
            out[k] = v
    return out


def redact_collection(coll, redact):
    out = {}
    for k, v in coll.items():
        if k == "name":
            out[k] = redact("coll", v)
        elif k == "indexes" and isinstance(v, dict):
            idx = dict(v)
            if isinstance(v.get("indexSizes"), dict):
                idx["indexSizes"] = {redact("index", i): s for i, s in v["indexSizes"].items()}
            if isinstance(v.get("stats"), list):
                idx["stats"] = [redact_index_stat(s, redact) for s in v["stats"]]
            out[k] = idx
        else:
            out[k] = v
    return out


def redact_database(db, redact):
    out = {}
    for k, v in db.items():
        if k == "db":
            out[k] = redact("db", v)
        elif k == "collectionstats" and isinstance(v, list):
            out[k] = [redact_collection(c, redact) for c in v]
        else:
            out[k] = v
    return out


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <msizer.json>", file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1], "r") as f:
        data = json.load(f)

    redact = make_mapper()

    if isinstance(data.get("databaseStats"), list):
        data["databaseStats"] = [redact_database(db, redact) for db in data["databaseStats"]]

    json.dump(data, sys.stdout, indent=1)
    print()


if __name__ == "__main__":
    main()
