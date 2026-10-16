"""FastAPI application: the TripLens HTTP API plus the query UI.

    GET /                     the single-page query tool
    GET /api/meta             readiness, timetable validity windows, Sydney time
    GET /api/search?q=        station / line typeahead
    GET /api/popular          quick-access stations
    GET /api/station?name=    station detail (platforms, lines, coordinates)
    GET /api/departures?...   merged departure board (scheduled + live overlay)
    GET /api/lines?day=       line catalogue with per-day trip counts
    GET /api/line?line=&...   one line's trips with per-stop times
    GET /api/trip?...         one trip's stop list (with live times)
    GET /api/alerts           service notices from /svinfo
    GET /api/timetables       available .tdb files (optionally load one)
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .service import (DEFAULT_FILES, NETWORKS, ScheduleService, family_of,
                      hhmm, service_minutes, sydney_now)
from .upstream import Upstream

REGION = os.environ.get("TRIPLENS_REGION", "syd")
ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = Path(__file__).resolve().parent / "static"
CACHE_DIR = Path(os.environ.get("TRIPLENS_CACHE", ROOT / ".tdb-cache"))

upstream = Upstream(region=REGION)
service = ScheduleService(upstream, str(CACHE_DIR), region=REGION,
                          files=DEFAULT_FILES)
state = {"ready": False, "error": None, "loaded_at": None}


async def load_timetables() -> None:
    try:
        await service.ensure(DEFAULT_FILES)
        state["ready"] = True
        state["error"] = None
    except Exception as exc:                     # keep serving what is cached
        state["error"] = f"{type(exc).__name__}: {exc}"


@asynccontextmanager
async def lifespan(_: FastAPI):
    asyncio.create_task(load_timetables())
    yield
    await upstream.aclose()


app = FastAPI(title="TripLens", version=__version__,
              description="Sydney transit query tool over TripView .tdb timetables",
              lifespan=lifespan)


def require_ready() -> None:
    if not service.loaded:
        raise HTTPException(503, state["error"] or "timetables are still loading")


def now_payload() -> dict:
    now = sydney_now()
    return {"iso": now.isoformat(timespec="seconds"),
            "clock": now.strftime("%H:%M:%S"),
            "date": now.date().isoformat(),
            "service_minutes": service_minutes(now)}


# -- meta ------------------------------------------------------------------
@app.get("/api/meta")
async def meta() -> dict:
    timetables = service.meta()
    dates = service.validity_dates()
    stations = service.stations() if service.loaded else {}
    lines = {l["id"] for item in service.loaded.values() for l in item.db.lines}
    return {
        "project": "TripLens", "version": __version__, "region": REGION,
        "ready": bool(service.loaded), "error": state["error"],
        "now": now_payload(), "dates": dates,
        "networks": NETWORKS,
        "timetables": timetables,
        "counts": {"stations": len(stations), "lines": len(lines)},
    }


@app.get("/api/timetables")
async def timetables(load: str | None = None) -> dict:
    if load:
        try:
            await service.ensure([load])
        except Exception as exc:
            raise HTTPException(400, f"{type(exc).__name__}: {exc}")
    return {"loaded": service.meta(), "available": await service.available()}


# -- search ----------------------------------------------------------------
@app.get("/api/search")
async def search(q: str = "", limit: int = Query(12, ge=1, le=50)) -> dict:
    require_ready()
    return service.search(q, limit)


@app.get("/api/popular")
async def popular(limit: int = Query(12, ge=1, le=40), next: int = 0,
                  day: str | None = None) -> dict:
    """Hub stations, optionally each with its next few departures."""
    require_ready()
    stations = service.popular_stations(limit)
    if next:
        try:
            boards = service.next_departures(
                [s["name"] for s in stations], day,
                from_min=service_minutes() - 1, per_station=next)
        except Exception:
            boards = {}
        for s in stations:
            s["next"] = boards.get(s["name"], [])
    return {"stations": stations, "day": day}


@app.get("/api/live/stations")
async def live_stations(limit: int = Query(12, ge=1, le=40)) -> dict:
    """Stations whose trips are being corrected in the current live feed."""
    require_ready()
    try:
        return {"stations": await service.live_stations(limit), **now_payload()}
    except Exception as exc:
        raise HTTPException(502, f"{type(exc).__name__}: {exc}")


@app.get("/api/station")
async def station(name: str) -> dict:
    require_ready()
    stations = service.stations()
    key = name if name in stations else next(
        (n for n in stations if n.lower() == name.lower()), None)
    if key is None:
        hits = [n for n in stations if name.lower() in n.lower()]
        if not hits:
            raise HTTPException(404, f"no station matching {name!r}")
        key = hits[0]
    rec = stations[key]
    return {
        "name": key, "platforms": rec["platforms"], "lat": rec["lat"],
        "lon": rec["lon"], "timetables": sorted(rec["timetables"]),
        "lines": rec["lines"],
        "stop_ids": sorted(rec["ids"])[:60],
    }


# -- departures ------------------------------------------------------------
@app.get("/api/departures")
async def departures(
    station: str,
    day: str | None = None,
    limit: int = Query(50, ge=1, le=400),
    network: str | None = None,
    live: int = 1,
    include_past: int = 0,
) -> dict:
    require_ready()
    today = now_payload()["date"]
    is_today = day in (None, "today", today)
    from_min = None
    if is_today and not include_past:
        from_min = max(0, service_minutes() - 1)
    try:
        data = service.departures(station, day, from_min=from_min,
                                  limit=400 if live else limit, network=network)
    except KeyError:
        raise HTTPException(404, f"no station matching {station!r}")
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    data["day"] = today if is_today else (day or today)
    if live:
        try:
            index, raw = await service.realtime_index()
            data["rows"] = service.apply_realtime(data["rows"], index)
            data["realtime"] = {
                "pollInterval": raw.get("pollInterval", 30),
                "trackerPollInterval": raw.get("trackerPollInterval", 10),
                "transpositions": len(raw.get("transpositions") or []),
            }
        except Exception as exc:
            data["realtime"] = {"error": f"{type(exc).__name__}: {exc}"}
    else:
        data["realtime"] = None
    data["rows"] = data["rows"][:limit]
    data["truncated"] = data["returned"] > len(data["rows"])
    return data


# -- lines -----------------------------------------------------------------
@app.get("/api/lines")
async def lines(day: str | None = None,
                network: str | None = None) -> dict:
    require_ready()
    cat = service.line_catalogue(day)
    if network:
        cat = [l for l in cat if l["network"] == network]
    return {"lines": cat, "count": len(cat)}


@app.get("/api/stats")
async def stats(day: str | None = None) -> dict:
    """Per-hour / per-network profile of a day, for the home page charts."""
    require_ready()
    data = service.stats(day)
    data["now"] = now_payload()
    try:
        index, raw = await service.realtime_index()
        data["live"] = {"transpositions": len(raw.get("transpositions") or []),
                        "lines": sorted({str(t.get("route", "")).rsplit("_", 1)[0]
                                         for t in raw.get("transpositions", [])})[:12]}
    except Exception:
        data["live"] = None
    return data


@app.get("/api/line")
async def line(line: str, day: str | None = None, direction: int | None = None,
               limit: int = Query(300, ge=1, le=1000), stops: int = 0) -> dict:
    require_ready()
    try:
        return service.line_trips(line, day, direction, limit,
                                  include_stops=bool(stops))
    except KeyError:
        raise HTTPException(404, f"unknown line {line!r}")
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/trip")
async def trip(line: str, depart: int, trip: str | None = None,
               day: str | None = None, live: int = 1) -> dict:
    """The full stop list of one trip, with live times where available."""
    require_ready()
    try:
        data = service.line_trips(line, day, limit=1000)
    except KeyError:
        raise HTTPException(404, f"unknown line {line!r}")
    for table in data["tables"]:
        for candidate in table["trips"]:
            if candidate["depart"] != depart:
                continue
            if trip and candidate["trip"] != trip:
                continue
            if live:
                try:
                    index, _ = await service.realtime_index()
                    for stop in candidate["stops"]:
                        minutes = index.get((candidate["trip"], stop["stop_id"]))
                        if minutes is not None:
                            stop["live"] = minutes
                            stop["live_clock"] = hhmm(minutes)
                            stop["delay"] = minutes - stop["time"]
                except Exception:
                    pass
            return {"line": data["line"], "day": data["day"],
                    "direction": table["direction"],
                    "headsign": table["headsign"], **candidate}
    # a station board row carries the time at that station, not the origin
    # departure of the trip, so fall back to the nearest trip on the line
    best = None
    for table in data["tables"]:
        for candidate in table["trips"]:
            if trip and candidate["trip"] != trip:
                continue
            gap = abs(candidate["depart"] - depart)
            if best is None or gap < best[0]:
                best = (gap, table, candidate)
    if best and best[0] <= 180:
        _, table, candidate = best
        return {"line": data["line"], "day": data["day"],
                "direction": table["direction"],
                "headsign": table["headsign"], **candidate}
    raise HTTPException(404, "trip not found")


# -- alerts ----------------------------------------------------------------
@app.get("/api/alerts")
async def alerts(network: str | None = None, q: str | None = None) -> dict:
    require_ready()
    try:
        items = await service.alerts()
    except Exception as exc:
        raise HTTPException(502, f"{type(exc).__name__}: {exc}")
    if network:
        items = [a for a in items if network in a["families"]]
    if q:
        needle = q.lower()
        items = [a for a in items
                 if needle in (a["title"] + a["body"]).lower()
                 or any(needle in l.lower() for l in a["lines"])]
    return {"alerts": items, "count": len(items),
            "by_network": {k: sum(1 for a in items if k in a["families"])
                           for k in NETWORKS}}


@app.get("/api/raw/realtime")
async def raw_realtime(routes: str | None = None, types: str = "dtva") -> dict:
    try:
        return await upstream.realtime(routes=routes, types=types)
    except Exception as exc:
        raise HTTPException(502, f"{type(exc).__name__}: {exc}")


# -- static ----------------------------------------------------------------
@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8090, reload=False)
