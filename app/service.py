"""Schedule service: the cracked .tdb timetables joined with the live feed.

This is the layer the web UI talks to. Everything here is derived from the
verified format (see TDB_FORMAT.md): container -> lines -> patterns -> trips,
with the 21-date validity bitmap, plus an overlay that attaches live
`transpositions` to the matching scheduled trip (the live `tripId` starts with
the timetable run id, and both sides use the same platform-specific stop ids).
"""

from __future__ import annotations

import asyncio
import datetime as dt
import os
import re
import threading
import urllib.parse
from typing import Any, Iterable

from . import tdb
from .upstream import Upstream

DEFAULT_FILES = ("syd-trains", "syd-ferries", "syd-lightrail")
SERVICE_DAY_START = 180                      # 03:00, like the app
NETWORKS = {
    "CR": {"label": "火车", "name": "Sydney Trains"},
    "SM": {"label": "地铁", "name": "Sydney Metro"},
    "LR": {"label": "轻轨", "name": "Light Rail"},
    "SF": {"label": "渡轮", "name": "Sydney Ferries"},
}
FAMILY_PREFIX = {"CR": "CR", "SM": "SM", "SF": "SF", "CCC": "SF", "CRF": "SF",
                 "MFF": "SF", "LR": "LR", "SLR": "LR", "PLR": "LR", "NT": "LR"}


def family_of(line_id: str) -> str:
    return FAMILY_PREFIX.get((line_id or "").split("_")[0], "CR")


def hhmm(minutes: int) -> str:
    m = int(minutes) % 1440
    return f"{m // 60:02d}:{m % 60:02d}"


def sydney_now() -> dt.datetime:
    try:
        from zoneinfo import ZoneInfo

        return dt.datetime.now(ZoneInfo("Australia/Sydney"))
    except Exception:
        return dt.datetime.now()


def service_minutes(now: dt.datetime | None = None) -> int:
    """Minutes since the start of the service day (03:00 counts as 0)."""
    now = now or sydney_now()
    m = now.hour * 60 + now.minute
    return m + 1440 if m < SERVICE_DAY_START else m


def unserviced(minutes: int) -> int:
    """Normalise after-midnight wall-clock minutes onto the service day."""
    return minutes + 1440 if minutes < SERVICE_DAY_START else minutes


class LoadedTimetable:
    def __init__(self, name: str, path: str, db: tdb.Database):
        self.name = name
        self.path = path
        self.db = db
        self.stop_index: dict[str, dict[str, Any]] = {}
        self.stop_ids: dict[str, int] = {}
        self.pattern_sets: list[list[frozenset]] = []
        self.station_lines: dict[str, dict[str, dict]] = {}
        for i, stop in enumerate(db.stops):
            st = self.stop_index.setdefault(
                stop["station"],
                {"platforms": set(), "indices": [], "lat": stop["lat"],
                 "lon": stop["lon"], "ids": set()})
            st["platforms"].add(stop["platform"])
            st["indices"].append(i)
            if stop["stop_id"]:
                st["ids"].add(stop["stop_id"])
                self.stop_ids.setdefault(stop["stop_id"], i)
        self._build_pattern_sets()
        self._build_station_lines()

    def _build_pattern_sets(self) -> None:
        self.pattern_sets = [
            [frozenset(si for si, _ in pat["stops"]) for pat in group]
            for group in self.db.groups]

    def _build_station_lines(self) -> None:
        """station -> {line id: line info + how many patterns call there}.

        One pass over the pattern map (thousands of entries), not over trips.
        """
        for table_index, group in enumerate(self.db.groups):
            line = self.db.lines[table_index // 2]
            seen: set[tuple[str, str]] = set()
            for pat in group:
                for stop_index, _ in pat["stops"]:
                    station = self.db.stops[stop_index]["station"]
                    key = (station, line["id"])
                    if key in seen:
                        continue
                    seen.add(key)
                    entry = self.station_lines.setdefault(station, {}).setdefault(
                        line["id"], {
                            "id": line["id"], "code": line["code"],
                            "name": line["name"], "dir": line["dir"],
                            "network": family_of(line["id"]), "patterns": 0})
                    entry["patterns"] += 1

    def lines_for_station(self, station: str) -> list[dict]:
        return sorted(self.station_lines.get(station, {}).values(),
                      key=lambda l: (-l["patterns"], l["code"]))


class ScheduleService:
    def __init__(self, upstream: Upstream, cache_dir: str,
                 region: str = "syd", files: Iterable[str] = DEFAULT_FILES):
        self.upstream = upstream
        self.cache_dir = cache_dir
        self.region = region
        self.requested = list(files)
        self.loaded: dict[str, LoadedTimetable] = {}
        self._lock = threading.Lock()
        self._meta: dict[str, dict] = {}
        os.makedirs(cache_dir, exist_ok=True)

    # -- loading -----------------------------------------------------------
    def _path(self, name: str) -> str:
        safe = re.sub(r"[^A-Za-z0-9_-]", "", name)
        return os.path.join(self.cache_dir, safe + ".tdb")

    async def available(self) -> dict[str, dict]:
        """Catalogue from the API, merged with what is already on disk."""
        try:
            cat = await self.upstream.timetables(self.region)
        except Exception:
            cat = {}
        for fn in os.listdir(self.cache_dir):
            if fn.endswith(".tdb"):
                cat.setdefault(fn[:-4], {"name": fn[:-4], "desc": "",
                                         "size": os.path.getsize(
                                             os.path.join(self.cache_dir, fn))})
        return cat

    async def ensure(self, names: Iterable[str] | None = None) -> None:
        """Load (downloading once if needed). Parsing happens off the event loop."""
        want = list(names or self.requested)
        for name in want:
            if name in self.loaded:
                continue
            path = self._path(name)
            if not os.path.exists(path):
                cat = await self.available()
                info = cat.get(name) or {}
                url = info.get("url") or f"https://static.tripview.com.au/{name}.tdb"
                blob = await self.upstream.download(url)
                tmp = path + ".tmp"
                with open(tmp, "wb") as fh:
                    fh.write(blob)
                os.replace(tmp, path)
            db = await asyncio.to_thread(tdb.Database, path)
            with self._lock:
                self.loaded[name] = await asyncio.to_thread(
                    LoadedTimetable, name, path, db)
        self.requested = sorted(set(self.requested) | set(want))

    def meta(self) -> list[dict]:
        out = []
        for name in self.requested:
            item = self.loaded.get(name)
            if item:
                out.append({
                    "name": name, "loaded": True,
                    "title": item.db.name,
                    "dates": [d.isoformat() for d in item.db.dates],
                    "lines": len(item.db.lines), "stops": len(item.db.stops),
                    "trips": sum(len(t) for t in item.db.trips)})
            else:
                out.append({"name": name, "loaded": False})
        return out

    def validity_dates(self) -> list[str]:
        """Dates every loaded timetable covers (the tool's shared window)."""
        windows = [[d.isoformat() for d in item.db.dates]
                   for item in self.loaded.values()]
        if not windows:
            return []
        shared = set(windows[0])
        for w in windows[1:]:
            shared &= set(w)
        return sorted(shared) if shared else sorted(windows[0])

    # -- lookups -----------------------------------------------------------
    def day_bit(self, db: tdb.Database, day: str | None) -> int:
        today = sydney_now().date()
        if not day or day == "today":
            want = today if today in db.dates else db.dates[0]
        elif day.isdigit():
            return int(day)
        else:
            want = dt.date.fromisoformat(day)
        if want not in db.dates:
            raise ValueError(f"{want} outside {db.dates[0]}..{db.dates[-1]}")
        return db.dates.index(want)

    def stations(self) -> dict[str, dict]:
        """Merged station index across every loaded timetable."""
        key = tuple(sorted(self.loaded))
        cached = getattr(self, "_stations_cache", None)
        if cached and cached[0] == key:
            return cached[1]
        out: dict[str, dict] = {}
        for item in self.loaded.values():
            for name, info in item.stop_index.items():
                rec = out.setdefault(name, {
                    "name": name, "platforms": set(), "ids": set(),
                    "lat": info["lat"], "lon": info["lon"],
                    "timetables": set(), "lines": {},
                    "patterns": {}})
                rec["platforms"] |= info["platforms"]
                rec["ids"] |= info["ids"]
                rec["timetables"].add(item.name)
                for line in item.station_lines.get(name, {}).values():
                    rec["lines"].setdefault(line["id"], line)
                    rec["patterns"][line["id"]] = (
                        rec["patterns"].get(line["id"], 0) + line["patterns"])
        for rec in out.values():
            rec["platforms"] = sorted(rec["platforms"],
                                      key=lambda p: (not p.isdigit(), p))
            rec["lines"] = sorted(
                rec["lines"].values(),
                key=lambda l: (-rec["patterns"].get(l["id"], 0), l["code"]))
        self._stations_cache = (key, out)
        return out

    def search(self, query: str, limit: int = 12) -> dict:
        q = (query or "").strip().lower()
        stations = self.stations()
        if q:
            starts = [n for n in stations if n.lower().startswith(q)]
            contains = [n for n in stations
                        if q in n.lower() and n not in starts]
            names = (starts + contains)[:limit]
        else:
            names = []
        lines: list[dict] = []
        if q:
            for item in self.loaded.values():
                for line in item.db.lines:
                    hay = f"{line['code']} {line['name']} {line['id']}".lower()
                    if q in hay:
                        lines.append({"id": line["id"], "code": line["code"],
                                      "name": line["name"],
                                      "network": family_of(line["id"]),
                                      "timetable": item.name})
            lines.sort(key=lambda l: (0 if l["code"].lower() == q else 1,
                                      l["code"]))
            lines = lines[:limit]
        return {
            "query": query,
            "stations": [{
                "name": n, "platforms": stations[n]["platforms"],
                "lines": [l["code"] for l in stations[n]["lines"][:6]],
                "timetables": sorted(stations[n]["timetables"]),
                "lat": stations[n]["lat"], "lon": stations[n]["lon"],
            } for n in names],
            "lines": lines,
        }

    # hubs people actually start from; anything else is ranked by coverage
    HUB_ORDER = ("Central", "Town Hall", "Wynyard", "Circular Quay", "Redfern",
                 "Strathfield", "Parramatta", "Chatswood", "Bondi Junction",
                 "North Sydney", "Hornsby", "Sydenham", "Epping", "Blacktown",
                 "Liverpool", "Manly", "Barangaroo", "Hurstville", "Penrith")

    def popular_stations(self, limit: int = 12) -> list[dict]:
        """Quick-access chips: main hubs first, then the best covered stations."""
        stations = self.stations()
        def codes(rec: dict) -> list[str]:
            out: list[str] = []
            for line in rec["lines"]:
                if line["code"] not in out:
                    out.append(line["code"])
            return out[:4]
        hub = [{"name": n, "platforms": len(stations[n]["platforms"]),
                "lines": codes(stations[n])}
               for n in self.HUB_ORDER if n in stations]
        rest = sorted(
            (s for s in stations.values() if s["name"] not in self.HUB_ORDER),
            key=lambda s: (-len(s["lines"]), -len(s["platforms"]), s["name"]))
        combined = hub + [{"name": s["name"], "platforms": len(s["platforms"]),
                           "lines": codes(s)} for s in rest]
        return combined[:limit]

    def _station_stops(self, name: str) -> tuple[str, list[tuple[str, int]]]:
        """Resolve a station name (exact, else unique case-insensitive)."""
        stations = self.stations()
        if name in stations:
            key = name
        else:
            low = (name or "").lower()
            hits = [n for n in stations if n.lower() == low]
            if not hits:
                hits = [n for n in stations if low in n.lower()]
            if not hits:
                raise KeyError(name)
            key = hits[0]
        out: list[tuple[str, int]] = []
        for item in self.loaded.values():
            info = item.stop_index.get(key)
            if info:
                out.extend((item.name, i) for i in info["indices"])
        return key, out

    def departures(self, station: str, day: str | None = None,
                   from_min: int | None = None, limit: int = 60,
                   network: str | None = None) -> dict:
        """Scheduled calls at a station, merged across every loaded timetable."""
        key, stops = self._station_stops(station)
        rows: list[dict] = []
        total = 0
        for item in self.loaded.values():
            db = item.db
            try:
                bit = self.day_bit(db, day)
            except ValueError:
                continue                 # this timetable is not published for that date
            indices = item.stop_index.get(key, {}).get("indices") or []
            if not indices:
                continue
            wanted = set(indices)
            for table_index, table in enumerate(db.trips):
                line = db.lines[table_index // 2]
                sets = item.pattern_sets[table_index]
                serving = {i for i, s in enumerate(sets) if s & wanted}
                if not serving:
                    continue
                for trip in table:
                    if not db.runs_on(trip, bit):
                        continue
                    if trip["pattern"] not in serving:
                        continue
                    pattern_stops = db.groups[table_index][trip["pattern"]]["stops"]
                    origin = db.stops[pattern_stops[0][0]]["station"]
                    destination = db.stops[pattern_stops[-1][0]]["station"]
                    for offset, stop_index, flags in db.stop_times(table_index, trip):
                        if stop_index not in wanted:
                            continue
                        stop = db.stops[stop_index]
                        minutes = trip["depart"] + offset // 60
                        total += 1
                        if from_min is not None and minutes < from_min:
                            continue
                        rows.append({
                            "time": minutes,
                            "clock": hhmm(minutes),
                            "depart": trip["depart"],
                            "depart_clock": hhmm(trip["depart"]),
                            "line": line["code"], "line_name": line["name"],
                            "line_id": line["id"], "network": family_of(line["id"]),
                            "direction": table_index % 2,
                            "headsign": line["dir"][table_index % 2],
                            "platform": stop["platform"],
                            "stop_id": stop["stop_id"],
                            "trip": trip.get("id", ""),
                            "service": trip.get("service", ""),
                            "flags": flags,
                            "timetable": item.name,
                            "origin": origin, "destination": destination,
                            "stops": len(pattern_stops),
                        })
        if network:
            rows = [r for r in rows if r["network"] == network]
        rows.sort(key=lambda r: (r["time"], r["line"]))
        return {"station": key, "day": day, "count": total,
                "returned": len(rows), "rows": rows[:limit],
                "platforms": sorted({r["platform"] for r in rows if r["platform"]}),
                "truncated": len(rows) > limit}

    def line_catalogue(self, day: str | None = None) -> list[dict]:
        out: list[dict] = []
        for item in self.loaded.values():
            try:
                bit = self.day_bit(item.db, day)
            except ValueError:
                continue
            for i, line in enumerate(item.db.lines):
                counts = [sum(1 for t in item.db.trips[i * 2 + d]
                              if item.db.runs_on(t, bit)) for d in (0, 1)]
                if not any(counts):
                    continue
                hours: dict[int, int] = {}
                first = last = None
                for d in (0, 1):
                    for trip in item.db.trips[i * 2 + d]:
                        if not item.db.runs_on(trip, bit):
                            continue
                        dep = trip["depart"]
                        first = dep if first is None else min(first, dep)
                        last = dep if last is None else max(last, dep)
                        hours[dep // 60] = hours.get(dep // 60, 0) + 1
                out.append({"id": line["id"], "code": line["code"],
                            "name": line["name"], "dir": line["dir"],
                            "network": family_of(line["id"]),
                            "trips": counts, "timetable": item.name,
                            "first": hhmm(first) if first is not None else None,
                            "last": hhmm(last) if last is not None else None,
                            "peak": max(hours.values()) if hours else 0})
        out.sort(key=lambda l: (l["code"], l["id"]))
        return out

    def next_departures(self, stations: list[str], day: str | None = None,
                        from_min: int | None = None,
                        per_station: int = 3) -> dict[str, list[dict]]:
        """Next calls at several stations in one pass (for the home cards)."""
        out: dict[str, list[dict]] = {name: [] for name in stations}
        for item in self.loaded.values():
            db = item.db
            try:
                bit = self.day_bit(db, day)
            except ValueError:
                continue
            local = {}
            for name in stations:
                info = item.stop_index.get(name)
                if info:
                    for index in info["indices"]:
                        local[index] = name
            if not local:
                continue
            keys = set(local)
            for table_index, table in enumerate(db.trips):
                line = db.lines[table_index // 2]
                sets = item.pattern_sets[table_index]
                serving = {i for i, s in enumerate(sets) if s & keys}
                if not serving:
                    continue
                for trip in table:
                    if not db.runs_on(trip, bit) or trip["pattern"] not in serving:
                        continue
                    pattern_stops = db.groups[table_index][trip["pattern"]]["stops"]
                    destination = db.stops[pattern_stops[-1][0]]["station"]
                    for offset, stop_index, _ in db.stop_times(table_index, trip):
                        name = local.get(stop_index)
                        if name is None:
                            continue
                        minutes = trip["depart"] + offset // 60
                        if from_min is not None and minutes < from_min:
                            continue
                        out[name].append({
                            "time": minutes, "clock": hhmm(minutes),
                            "line": line["code"], "line_id": line["id"],
                            "network": family_of(line["id"]),
                            "destination": destination,
                            "headsign": line["dir"][table_index % 2],
                            "trip": trip.get("id", ""),
                            "service": trip.get("service", ""),
                            "platform": db.stops[stop_index]["platform"],
                            "stop_id": db.stops[stop_index]["stop_id"],
                            "depart": trip["depart"],
                        })
        for name, rows in out.items():
            rows.sort(key=lambda r: (r["time"], r["line"]))
            out[name] = rows[:per_station]
        return out

    def stats(self, day: str | None = None) -> dict:
        """Day profile for the home page: trips per hour and per network."""
        key = (tuple(sorted(self.loaded)), day)
        if getattr(self, "_stats_cache", None) and self._stats_cache[0] == key:
            return self._stats_cache[1]
        hours = [{"hour": h, "total": 0, **{k: 0 for k in NETWORKS}}
                 for h in range(24)]
        line_trips: dict[str, int] = {}
        line_family: dict[str, str] = {}
        stations: dict[str, set] = {k: set() for k in NETWORKS}
        total = 0
        for item in self.loaded.values():
            db = item.db
            try:
                bit = self.day_bit(db, day)
            except ValueError:
                continue
            for table_index, table in enumerate(db.trips):
                fam = family_of(db.lines[table_index // 2]["id"])
                line_id = db.lines[table_index // 2]["id"]
                line_family[line_id] = fam
                for trip in table:
                    if not db.runs_on(trip, bit):
                        continue
                    bucket = hours[min(23, trip["depart"] // 60)]
                    bucket[fam] += 1
                    bucket["total"] += 1
                    line_trips[line_id] = line_trips.get(line_id, 0) + 1
                    total += 1
            for table_index, group in enumerate(db.groups):
                fam = family_of(db.lines[table_index // 2]["id"])
                for pat in group:
                    for stop_index, _ in pat["stops"]:
                        stations[fam].add(db.stops[stop_index]["station"])
        networks = []
        for fam in NETWORKS:
            trips = sum(n for lid, n in line_trips.items()
                        if line_family.get(lid) == fam)
            if not trips:
                continue
            networks.append({
                "network": fam,
                "lines": sum(1 for lid, n in line_trips.items()
                             if line_family.get(lid) == fam and n > 0),
                "stations": len(stations[fam]), "trips": trips,
                "share": round(trips / total, 4) if total else 0})
        out = {"day": day, "hours": hours, "networks": networks,
               "total": total, "peak": max((h["total"] for h in hours), default=0)}
        self._stats_cache = (key, out)
        return out

    def line_trips(self, line_id: str, day: str | None = None,
                   direction: int | None = None, limit: int = 400,
                   include_stops: bool = True) -> dict:
        for item in self.loaded.values():
            if not any(line["id"] == line_id for line in item.db.lines):
                continue
            db = item.db
            index = db.line_by_id(line_id)
            line = db.lines[index]
            bit = self.day_bit(db, day)
            tables = []
            for d in ((direction,) if direction in (0, 1) else (0, 1)):
                table_index = db.table(index, d)
                trips = []
                for trip in db.trips[table_index]:
                    if not db.runs_on(trip, bit):
                        continue
                    stops = db.stop_times(table_index, trip) if include_stops else []
                    entry = {
                        "depart": trip["depart"], "clock": hhmm(trip["depart"]),
                        "trip": trip.get("id", ""),
                        "service": trip.get("service", ""),
                        "headsign": line["dir"][d],
                        "patterns": len(db.groups[table_index]),
                        "stop_count": len(db.groups[table_index][trip["pattern"]]["stops"]),
                    }
                    if include_stops:
                        entry["stops"] = [{
                            "time": trip["depart"] + off // 60,
                            "clock": hhmm(trip["depart"] + off // 60),
                            "station": db.stops[si]["station"],
                            "platform": db.stops[si]["platform"],
                            "stop_id": db.stops[si]["stop_id"],
                        } for off, si, _ in stops]
                    else:
                        entry["origin"] = db.stops[stops[0][1]]["station"] if stops else (
                            db.stops[db.groups[table_index][trip["pattern"]]["stops"][0][0]]["station"])
                        entry["destination"] = db.stops[
                            db.groups[table_index][trip["pattern"]]["stops"][-1][0]]["station"]
                    trips.append(entry)
                trips.sort(key=lambda t: t["depart"])
                tables.append({"direction": d, "headsign": line["dir"][d],
                               "count": len(trips), "trips": trips[:limit]})
            return {"line": {"id": line["id"], "code": line["code"],
                             "name": line["name"], "dir": line["dir"],
                             "network": family_of(line["id"])},
                    "timetable": item.name,
                    "dates": [x.isoformat() for x in db.dates],
                    "day": db.dates[bit].isoformat(), "tables": tables}
        raise KeyError(line_id)

    # -- live overlay ------------------------------------------------------
    async def realtime_index(self) -> tuple[dict, dict]:
        """{(run id, stop id): minutes} plus the raw payload."""
        raw = await self.upstream.realtime(region=self.region)
        index: dict[tuple[str, str], int] = {}
        for t in raw.get("transpositions", []):
            run = str(t.get("tripId", "")).split(".")[0]
            parts = str(t.get("stops", "")).split(",")
            # times arrive in service-day order; only map those that move forward
            prev = None
            for i in range(0, len(parts) - 2, 3):
                try:
                    h, m = parts[i].split(":")
                    minutes = int(h) * 60 + int(m)
                except ValueError:
                    continue
                if prev is not None and minutes < prev - 720:
                    minutes += 1440
                prev = minutes
                index[(run, parts[i + 1])] = minutes
        return index, raw

    def apply_realtime(self, rows: list[dict], index: dict) -> list[dict]:
        """Attach live times/platforms to scheduled rows."""
        live_runs: set[str] = set()
        for row in rows:
            run = row.get("trip") or ""
            if not run:
                continue
            key = (run, row.get("stop_id") or "")
            minutes = index.get(key)
            if minutes is None:
                # the stop id may be missing a platform variant; try the run only
                candidates = [v for (r, _), v in index.items() if r == run]
                if candidates:
                    near = min(candidates, key=lambda v: abs(v - row["time"]))
                    minutes = near if abs(near - row["time"]) <= 30 else None
            if minutes is None:
                continue
            live_runs.add(run)
            row["realtime"] = True
            row["live"] = minutes
            row["live_clock"] = hhmm(minutes)
            row["delay"] = minutes - row["time"]
        for row in rows:
            if row.get("trip") in live_runs and not row.get("realtime"):
                row["trip_realtime"] = True
        rows.sort(key=lambda r: ((r.get("live") or r["time"]), r["line"]))
        return rows

    def stop_id_map(self) -> dict[str, tuple[str, str]]:
        """stop id -> (station, platform) across every loaded timetable."""
        if getattr(self, "_stop_map", None) is None:
            out: dict[str, tuple[str, str]] = {}
            for item in self.loaded.values():
                for stop in item.db.stops:
                    if stop["stop_id"]:
                        out.setdefault(stop["stop_id"],
                                       (stop["station"], stop["platform"]))
            self._stop_map = out
        return self._stop_map

    async def live_stations(self, limit: int = 12) -> list[dict]:
        """Stations touched by the trips that are being corrected right now."""
        index, raw = await self.realtime_index()
        mapping = self.stop_id_map()
        trips_per_station: dict[str, set[str]] = {}
        lines_per_station: dict[str, set[str]] = {}
        for t in raw.get("transpositions", []):
            run = str(t.get("tripId", ""))
            line = str(t.get("route", "")).rsplit("_", 1)[0]
            parts = str(t.get("stops", "")).split(",")
            for i in range(0, len(parts) - 2, 3):
                hit = mapping.get(parts[i + 1])
                if not hit:
                    continue
                trips_per_station.setdefault(hit[0], set()).add(run)
                lines_per_station.setdefault(hit[0], set()).add(line)
        out = [{"station": name, "trips": len(runs),
                "lines": sorted(lines_per_station.get(name, set()))}
               for name, runs in trips_per_station.items()]
        out.sort(key=lambda r: (-r["trips"], r["station"]))
        return out[:limit]

    async def alerts(self) -> list[dict]:
        text = await self.upstream.svinfo(self.region)
        out: list[dict] = []
        for block in re.split(r"\n\s*\n", text):
            if not block.strip():
                continue
            rec: dict[str, str] = {}
            key = None
            for line in block.split("\n"):
                i = line.find("=")
                if i > 0 and re.fullmatch(r"[A-Za-z_]+", line[:i]):
                    key = line[:i]
                    rec[key] = line[i + 1:]
                elif key:
                    rec[key] += "\n" + line
            if not (rec.get("title") or rec.get("body")):
                continue
            lines = [x.strip() for x in rec.get("lines", "").split(",") if x.strip()]
            families = sorted({family_of(x) for x in lines})
            if not families:
                tt = rec.get("timetable", "")
                if re.search(r"ferr", tt):
                    families = ["SF"]
                elif re.search(r"light|tram", tt):
                    families = ["LR"]
                elif re.search(r"train", tt):
                    families = ["CR"]
            out.append({
                "title": rec.get("title", ""), "body": rec.get("body", "").strip(),
                "type": rec.get("type", "alert"), "lines": lines,
                "families": families,
                "start": rec.get("start"), "end": rec.get("end"),
                "ongoing": rec.get("ongoing") == "true",
            })
        rank = {"interrupt": 0, "trackwork": 1, "alert": 2, "news": 3}
        out.sort(key=lambda a: (rank.get(a["type"], 9),
                                0 if a["lines"] else 1,
                                -(int(a["start"] or 0))))
        return out
