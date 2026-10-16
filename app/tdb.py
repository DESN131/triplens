#!/usr/bin/env python3
"""TripView timetable (.tdb) reader - format recovered from libtv.so.

Container (libtv.so FUN_0017823c "read header" / FUN_00178488 "read index" /
FUN_00178790 "read + inflate one section"):

    0      "TDB" 0x0f
    4      u32be build timestamp
    8      u16be section count N
    10     N x 9 bytes: u8 tag, u32be raw_size, u32be stored_size
    10+9N  data area: each section's stored_size bytes in record order, a zlib
           stream inflating to raw_size bytes (libz 1.2.8, inflate())
    EOF    4 trailing bytes

Sections are looked up by tag (FUN_00177b74 hashes the tag byte, FUN_00177fdc
resolves it). The Database loader FUN_001ae79c reads:

    tag  1  properties: u8 count, then (u8 kind, u16be len, value) entries;
            kind 1 = name, 3 = numeric, 4/5 = flags           FUN_001b216c
    tag 15  operators: u16be count, then per operator
            (u16be len id, then (u8 kind, u16be len, string) entries)
                                                              FUN_001b7a98
    tag  3  locations: u16be count, then per stop (u16be len
            "Name:platform#stopId", u16be len alias, f32be lat, f32be lon)
                                                              FUN_001b4c44
    tag  2  lines: u16be count, then per line 5 length-prefixed strings
            (internal id, display name, public code, dir1, dir2) + u32be,
            then count single bytes                           FUN_001bfb9c
    tag 12  special dates                                      FUN_001c2798
    tag 13  pattern map: u16be group count; per group u16be pattern count;
            per pattern (u16be tripCount, u16be stopCount,
            u16be stopIndex[stopCount], u8 flags[stopCount])
                                            FUN_001be960/beaf8/bec1c
    tag  4  one trip table per (line, direction) in line order (dir0, dir1):
            u16be tripCount, then per trip
              u8    low nibble -> field0, high nibble -> field6
              u16be departure minutes since midnight
              u8    -> field7
              u16be patternIndex + 1     (index into this table's group)
              u32be -> field12
              u16be legs + 1             (legs = pattern stops - 1)
              legs x u8 minutes per leg
            then a chain of blocks, each u8 tag + one payload per trip:
              0x10 u16be len + string -> trip id (run number)
              0x11 u8                 -> byte8
              0x12 u16be len + string -> service id (operator.pattern)
              0x13 u8                 -> field0 |= value << 4
                                     FUN_001c010c / FUN_001c1684

Stop times of a trip: t[0] = departure, t[i] = t[i-1] + legs[i-1] minutes
(FUN_001c1684). FUN_001ae79c clears bit0 of the first and bit1 of the last stop
of each pattern, so (flags & 3) marks a stop as actually served.

Sections present in some timetables whose readers are identified but whose
layout is not decoded here: tag 9 per-stop departure index (FUN_001a8c88),
tag 14 (FUN_00199434), tag 16 (FUN_001c1cdc), tag 17 (FUN_001a88a0),
tag 18 "TMAP" blob, tag 5.

Usage:
    python tdb.py FILE.tdb                     inventory
    python tdb.py FILE.tdb --lines             line/direction table
    python tdb.py FILE.tdb --services CR_ESI   trips of a line with stop times
    python tdb.py FILE.tdb --station 200060    scheduled calls at a stop
    python tdb.py FILE.tdb --stops stops.json  rebuild the stop id -> label map
"""

import argparse
import json
import os
import struct
import sys
import zlib

MAGIC = b"TDB"
FORMAT_VERSION = 0x0F


class Section:
    __slots__ = ("index", "tag", "raw_size", "stored_size", "offset", "data")

    def __init__(self, index, tag, raw_size, stored_size, offset, data):
        self.index = index
        self.tag = tag
        self.raw_size = raw_size
        self.stored_size = stored_size
        self.offset = offset
        self.data = data

    def __repr__(self):
        return f"<section {self.index} tag={self.tag} raw={self.raw_size}>"


class Tdb:
    """Container only: header, index, inflated sections."""

    def __init__(self, path):
        self.path = path
        raw = open(path, "rb").read()
        if raw[:3] != MAGIC:
            raise ValueError(f"{path}: bad signature {raw[:3]!r}")
        self.version = raw[3]
        if self.version != FORMAT_VERSION:
            raise ValueError(f"{path}: unsupported version 0x{self.version:02x}")
        self.timestamp = struct.unpack_from(">I", raw, 4)[0]
        self.count = struct.unpack_from(">H", raw, 8)[0]
        self.sections = []
        off = 10 + 9 * self.count
        for k in range(self.count):
            p = 10 + 9 * k
            tag = raw[p]
            raw_size = int.from_bytes(raw[p + 1:p + 5], "big")
            stored = int.from_bytes(raw[p + 5:p + 9], "big")
            blob = zlib.decompress(raw[off:off + stored])
            if len(blob) != raw_size:
                raise ValueError(
                    f"{path}: section {k} inflated to {len(blob)} != {raw_size}")
            self.sections.append(Section(k, tag, raw_size, stored, off, blob))
            off += stored
        self.data_end = off
        self.trailer = raw[off:]

    def by_tag(self, tag):
        return [s for s in self.sections if s.tag == tag]

    def one(self, tag):
        got = self.by_tag(tag)
        if len(got) != 1:
            raise ValueError(f"tag {tag}: expected 1 section, found {len(got)}")
        return got[0]


class Reader:
    """The big-endian byte cursor the native code uses."""

    def __init__(self, data, pos=0):
        self.d = data
        self.p = pos

    def u8(self):
        v = self.d[self.p]
        self.p += 1
        return v

    def u16(self):
        v = struct.unpack_from(">H", self.d, self.p)[0]
        self.p += 2
        return v

    def u32(self):
        v = struct.unpack_from(">I", self.d, self.p)[0]
        self.p += 4
        return v

    def f32(self):
        v = struct.unpack_from(">f", self.d, self.p)[0]
        self.p += 4
        return v

    def string(self):
        ln = self.u16()
        v = self.d[self.p:self.p + ln].decode("latin-1")
        self.p += ln
        return v

    def rest(self):
        return len(self.d) - self.p


def parse_properties(blob):
    """tag 1: u8 count, then (u8 kind, u16be len, string) entries."""
    r = Reader(blob)
    props = []
    for _ in range(r.u8()):
        kind = r.u8()
        props.append((kind, r.string()))
    return props


def parse_operators(blob):
    """tag 15: u16be count, then per operator id + tagged properties."""
    r = Reader(blob)
    out = []
    for _ in range(r.u16()):
        op_id = r.string()
        props = []
        while r.p < len(blob) and blob[r.p] != 0:
            kind = r.u8()
            props.append((kind, r.string()))
        r.p += 1
        out.append({"id": op_id, "props": props})
    return out


def parse_stops(blob):
    """tag 3: u16be count, then (name, alias, lat, lon) per stop."""
    r = Reader(blob)
    out = []
    for _ in range(r.u16()):
        name = r.string()
        alias = r.string()
        lat, lon = r.f32(), r.f32()
        station, _, stop_id = name.partition("#")
        base, _, platform = station.partition(":")
        out.append({"name": name, "station": base, "platform": platform,
                    "stop_id": stop_id, "alias": alias, "lat": lat, "lon": lon})
    return out


def parse_lines(blob):
    """tag 2: u16be count, per line 5 strings + u32be, then count bytes."""
    r = Reader(blob)
    n = r.u16()
    out = []
    for _ in range(n):
        values = [r.string() for _ in range(5)]
        out.append({"id": values[0], "name": values[1], "code": values[2],
                    "dir": values[3:5], "num": r.u32()})
    for i in range(n):
        out[i]["byte"] = blob[r.p + i]
    return out


def parse_pattern_map(blob):
    """tag 13: [group][pattern] with per-stop (stop index, flags)."""
    r = Reader(blob)
    groups = []
    for _ in range(r.u16()):
        pats = []
        for _ in range(r.u16()):
            trip_count = r.u16()
            n = r.u16()
            idx = [r.u16() for _ in range(n)]
            flags = [r.u8() for _ in range(n)]
            pats.append({"trips": trip_count, "flags": flags,
                         "stops": list(zip(idx, flags))})
        groups.append(pats)
    return groups


DATE_EPOCH_JDN = 2440588      # 1970-01-01


def _day_number(blob, pos):
    """FUN_001c2798: 4 packed bytes -> Julian day number."""
    a = struct.unpack_from(">H", blob, pos)[0]
    c = blob[pos + 2]
    d = blob[pos + 3]
    yy = a - (1 if c < 3 else 0)
    k = -3 if c >= 3 else 9
    return (d + ((yy // 100) * 0x23AB1 >> 2) + ((k + c) * 0x99 + 2) // 5
            + ((yy % 100) * 0x5B5 >> 2) + 0x1A431F)


def parse_dates(blob):
    """tag 12: u8 count, then count x 4-byte day numbers (the validity window).

    Trip records carry a bitmask (field12) of the dates they run on, so bit i
    refers to entry i of this list.
    """
    import datetime
    n = blob[0]
    out = []
    for i in range(n):
        jdn = _day_number(blob, 1 + 4 * i)
        out.append(datetime.date(1970, 1, 1) + datetime.timedelta(
            days=jdn - DATE_EPOCH_JDN))
    return out


def parse_trips(blob):
    """tag 4: see module docstring."""
    r = Reader(blob)
    trips = []
    for _ in range(r.u16()):
        b0 = r.u8()
        trips.append({
            "field0": b0 & 0x0F,
            "depart": r.u16(),
            "field6": b0 >> 4,
            "field7": r.u8(),
            "pattern": r.u16() - 1,
            "field12": r.u32(),
            "legs": [r.u8() for _ in range(r.u16() - 1)],
        })
    while r.p < len(blob):
        block = r.u8()
        if block in (0x10, 0x12):
            key = "id" if block == 0x10 else "service"
            for t in trips:
                t[key] = r.string()
        elif block == 0x11:
            for t in trips:
                t["byte8"] = r.u8()
        elif block == 0x13:
            for t in trips:
                t["field0"] |= r.u8() << 4
        else:
            raise ValueError(f"unknown trip block 0x{block:02x} at {r.p - 1}")
    return trips


class Database:
    """Everything the app's Tdb::Database exposes, decoded."""

    def __init__(self, path):
        self.tdb = Tdb(path)
        self.properties = parse_properties(self.tdb.one(1).data)
        self.operators = parse_operators(self.tdb.one(15).data)
        self.stops = parse_stops(self.tdb.one(3).data)
        self.lines = parse_lines(self.tdb.one(2).data)
        self.dates = parse_dates(self.tdb.one(12).data)
        self.groups = parse_pattern_map(self.tdb.one(13).data)
        self.trip_sections = self.tdb.by_tag(4)
        self.trips = [parse_trips(s.data) for s in self.trip_sections]
        if len(self.groups) != len(self.trips):
            raise ValueError(
                f"{path}: {len(self.groups)} pattern groups for "
                f"{len(self.trips)} trip tables")

    @property
    def name(self):
        for kind, value in self.properties:
            if kind == 1:
                return value
        return ""

    def table(self, line_index, direction):
        """Trip-table index for a line and direction (0/1)."""
        return line_index * 2 + direction

    def line_by_id(self, line_id):
        for i, line in enumerate(self.lines):
            if line["id"] == line_id:
                return i
        raise KeyError(line_id)

    def day_bit(self, day):
        """Bit index in trip field12 for a date (int index or datetime.date)."""
        if isinstance(day, int):
            return day
        return self.dates.index(day)

    @staticmethod
    def runs_on(trip, day_bit):
        return day_bit is None or (trip["field12"] >> day_bit) & 1

    def stop_label(self, index):
        s = self.stops[index]
        if not s["platform"]:
            return s["station"]
        if s["platform"].isdigit():
            return f"{s['station']} P{s['platform']}"
        return f"{s['station']} ({s['platform']})"

    def stop_times(self, table_index, trip):
        """[(seconds after departure, stop index, flags), ...] for one trip."""
        pattern = self.groups[table_index][trip["pattern"]]
        out = []
        t = 0
        for i, (stop_index, flags) in enumerate(pattern["stops"]):
            out.append((t, stop_index, flags))
            if i < len(trip["legs"]):
                t += trip["legs"][i] * 60
        return out

    def departures(self, stop_index, day_bit=None, from_seconds=None,
                   to_seconds=None):
        """Every scheduled call at one stop, across all lines."""
        out = []
        for table_index, table in enumerate(self.trips):
            line = self.lines[table_index // 2]
            direction = table_index % 2
            for trip in table:
                if not self.runs_on(trip, day_bit):
                    continue
                for t, si, flags in self.stop_times(table_index, trip):
                    if si != stop_index:
                        continue
                    seconds = trip["depart"] * 60 + t
                    if from_seconds is not None and seconds < from_seconds:
                        continue
                    if to_seconds is not None and seconds > to_seconds:
                        continue
                    out.append({
                        "seconds": seconds,
                        "line": line["code"],
                        "line_name": line["name"],
                        "line_id": line["id"],
                        "direction": direction,
                        "headsign": line["dir"][direction],
                        "platform": self.stops[si]["platform"],
                        "trip": trip.get("id", ""),
                        "service": trip.get("service", ""),
                    })
        out.sort(key=lambda d: (d["seconds"], d["line"]))
        return out


def hhmm(seconds):
    seconds %= 86400
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}"


def cmd_inventory(db):
    t = db.tdb
    from collections import Counter
    print(f"{t.path}: TDB v{t.version} built={t.timestamp} records={t.count} "
          f"trailer={t.trailer.hex()}")
    print(f"  name: {db.name!r}")
    print(f"  operators: {', '.join(o['id'] for o in db.operators[:8])}")
    print(f"  tags: {dict(sorted(Counter(s.tag for s in t.sections).items()))}")
    bad = sum(1 for k, tbl in enumerate(db.trips) for trip in tbl
              if not 0 <= trip["pattern"] < len(db.groups[k]) or
              len(trip["legs"]) != len(db.groups[k][trip["pattern"]]["stops"]) - 1)
    print(f"  stops {len(db.stops)}  lines {len(db.lines)}  trip tables "
          f"{len(db.trips)}  patterns {sum(len(g) for g in db.groups)}  "
          f"trips {sum(len(x) for x in db.trips)}  "
          f"pattern/leg inconsistencies {bad}")
    if db.dates:
        print(f"  validity {db.dates[0]} .. {db.dates[-1]} "
              f"({len(db.dates)} dates, one bit each in trip field12)")


def cmd_lines(db):
    for i, line in enumerate(db.lines):
        print(f"{i:3d} {line['id']:14s} {line['code']:6s} {line['name']:42s} "
              f"trips {len(db.trips[i * 2]):4d}/{len(db.trips[i * 2 + 1]):4d}  "
              f"num=0x{line['num']:08x} byte={line['byte']}")
        for d in (0, 1):
            print(f"        dir{d}: {line['dir'][d][:100]}")


def cmd_services(db, selector, day_bit):
    index = int(selector) if selector.isdigit() else db.line_by_id(selector)
    for direction in (0, 1):
        table_index = db.table(index, direction)
        line = db.lines[index]
        print(f"\n=== {line['id']} {line['name']} dir{direction}: "
              f"{line['dir'][direction]}")
        trips = [t for t in db.trips[table_index] if db.runs_on(t, day_bit)]
        print(f"  {len(trips)} trips"
              + (f" on {db.dates[day_bit]}" if day_bit is not None else ""))
        for n, trip in enumerate(trips):
            print(f"  trip {n:4d} depart {hhmm(trip['depart'] * 60)} "
                  f"pattern {trip['pattern']:3d} id={trip.get('id', ''):>10s} "
                  f"service={trip.get('service', '')}")
            for seconds, si, flags in db.stop_times(table_index, trip):
                print(f"       {hhmm(trip['depart'] * 60 + seconds)}  "
                      f"{db.stop_label(si):34s} flags=0x{flags:02x}")


def cmd_station(db, wanted, day_bit):
    """Every platform entry of a station is a separate stop index, so group them."""
    by_name = {}
    for i, s in enumerate(db.stops):
        by_name.setdefault(s["station"], []).append(i)
    if wanted in by_name:
        stations = [wanted]
    else:
        stations = sorted(n for n in by_name if wanted.lower() in n.lower())
    if not stations:
        sys.exit(f"no stop matching {wanted!r}")
    for name in stations[:6]:
        indices = by_name[name]
        calls = []
        for index in indices:
            calls.extend(db.departures(index, day_bit=day_bit))
        calls.sort(key=lambda d: (d["seconds"], d["line"]))
        stop = db.stops[indices[0]]
        print(f"\n=== {name} ({len(indices)} platform entries, "
              f"{stop['lat']:.4f},{stop['lon']:.4f}) - {len(calls)} calls"
              + (f" on {db.dates[day_bit]}" if day_bit is not None
                 else " (every date in the window)"))
        for d in calls[:20]:
            print(f"    {hhmm(d['seconds'])}  {d['line']:6s} "
                  f"{d['headsign'][:38]:40s} P{d['platform']:3s} {d['trip']}")


def cmd_stops_json(db, path):
    table = {}
    for i, s in enumerate(db.stops):
        if not s["stop_id"]:
            continue
        label = db.stop_label(i)
        if s["stop_id"] not in table or len(label) > len(table[s["stop_id"]]):
            table[s["stop_id"]] = label
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(table, fh, ensure_ascii=False, sort_keys=True)
    print(f"wrote {len(table)} stops -> {path}")


def cmd_json(db, path, day_bit):
    """Export a machine-readable schedule (optionally one date only)."""
    out = {
        "file": os.path.basename(db.tdb.path),
        "name": db.name,
        "built": db.tdb.timestamp,
        "dates": [d.isoformat() for d in db.dates],
        "day": db.dates[day_bit].isoformat() if day_bit is not None else None,
        "lines": [{"index": i, "id": l["id"], "code": l["code"],
                   "name": l["name"], "dir": l["dir"]}
                  for i, l in enumerate(db.lines)],
        "tables": [],
    }
    for table_index, table in enumerate(db.trips):
        trips = []
        for trip in table:
            if not db.runs_on(trip, day_bit):
                continue
            trips.append({
                "depart": hhmm(trip["depart"] * 60),
                "depart_min": trip["depart"],
                "pattern": trip["pattern"],
                "id": trip.get("id", ""),
                "service": trip.get("service", ""),
                "stops": [
                    {"time": hhmm(trip["depart"] * 60 + seconds),
                     "offset": seconds // 60,
                     "stop": si,
                     "station": db.stops[si]["station"],
                     "platform": db.stops[si]["platform"],
                     "stop_id": db.stops[si]["stop_id"],
                     "flags": flags}
                    for seconds, si, flags in db.stop_times(table_index, trip)
                ],
            })
        out["tables"].append({
            "table": table_index,
            "line": table_index // 2,
            "direction": table_index % 2,
            "trips": trips,
        })
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False)
    print(f"wrote {sum(len(t['trips']) for t in out['tables'])} trips -> {path}")


def main():
    ap = argparse.ArgumentParser(
        description="TripView .tdb timetable reader")
    ap.add_argument("path")
    ap.add_argument("--lines", action="store_true", help="print the line table")
    ap.add_argument("--day", metavar="DATE|BIT|today",
                    help="restrict to one date of the validity window")
    ap.add_argument("--services", metavar="LINE_ID|INDEX",
                    help="print a line's trips with per-stop times")
    ap.add_argument("--station", metavar="STOP_ID|TEXT",
                    help="print scheduled calls at a stop")
    ap.add_argument("--stops", metavar="OUT.JSON",
                    help="write the stop id -> label map")
    ap.add_argument("--json", metavar="OUT.JSON",
                    help="export the schedule (with --day for one date)")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    db = Database(args.path)
    cmd_inventory(db)
    day_bit = None
    if args.day:
        import datetime
        if args.day.isdigit():
            day_bit = int(args.day)
        else:
            day = datetime.date.today() if args.day == "today" else \
                datetime.date.fromisoformat(args.day)
            if day not in db.dates:
                sys.exit(f"{day} outside {db.dates[0]}..{db.dates[-1]}")
            day_bit = db.dates.index(day)
    if args.lines:
        cmd_lines(db)
    if args.services:
        cmd_services(db, args.services, day_bit)
    if args.station:
        cmd_station(db, args.station, day_bit)
    if args.stops:
        cmd_stops_json(db, args.stops)
    if args.json:
        cmd_json(db, args.json, day_bit)


if __name__ == "__main__":
    main()
