"""Build the history timeline: python -m timeline.build --model data/model --out site (docs/timeline.md)"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import duckdb

from model.report import ATTRIBUTION
from model.rules import GAP_HOURS, RETIME_WINDOW_HOURS

from . import pages

STATIC = Path(__file__).parent / "static"
MARKER = ".timeline-site"
# The board keeps a past flight at least this long and lists a flight this far ahead (CLAUDE.md, measured).
BOARD_KEEPS = timedelta(hours=22)
BOARD_AHEAD = timedelta(hours=72)
OBS_COLUMNS = ("flight_id", "snap_rn", "observed_at", "prev_observed_at", "change_kind", "changed_fields",
               "sched_local", "est_local", "status", "status_he", "terminal", "counters", "zone",
               "airline_name", "airport_name", "city_en", "city_he", "country_en", "country_he")


def _rows(con, sql: str) -> list[dict]:
    cur = con.execute(sql)
    names = [d[0] for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def _utc(day: date) -> datetime:
    """Midnight starting a local Israel date, as naive UTC like the model's times."""
    return datetime.combine(day, time(), tzinfo=pages.ISRAEL).astimezone(timezone.utc).replace(tzinfo=None)


def load(model_dir: Path) -> tuple[list[dict], list[dict], list[dict]]:
    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC'")
    src = {t: str(model_dir / f"{t}.parquet").replace("'", "''") for t in ("flights", "observations", "snapshots")}
    flights = _rows(con, f"SELECT * FROM '{src['flights']}' ORDER BY sched_local_final, direction, airline, flight_no, flight_id")
    obs = _rows(con, f"SELECT {', '.join(OBS_COLUMNS)} FROM '{src['observations']}' ORDER BY flight_id, snap_rn")
    snaps = _rows(con, f"""SELECT fetched_at, lag(fetched_at) OVER (ORDER BY snap_rn) AS prev, gap_before_s
                           FROM '{src['snapshots']}' ORDER BY snap_rn""")
    return flights, obs, snaps


def render(flights: list[dict], obs: list[dict], snaps: list[dict]) -> dict[str, str]:
    """Every page of the site, by path. Pure: the same rows give the same text."""
    undated = [f"{f['airline']} {f['flight_no']}" for f in flights if f["sched_local_final"] is None]
    if undated:
        raise ValueError(f"{len(undated)} flights have no final scheduled time ({undated[:10]}); "
                         "every flight must land on a day page")
    first_check, last_check = snaps[0]["fetched_at"], snaps[-1]["fetched_at"]
    gaps = [(s["prev"], s["fetched_at"]) for s in snaps if (s["gap_before_s"] or 0) > GAP_HOURS * 3600]
    obs_by_flight: dict[str, list[dict]] = {}
    for o in obs:
        obs_by_flight.setdefault(o["flight_id"], []).append(o)
    by_group: dict[str, list[dict]] = {}
    for f in flights:
        by_group.setdefault(f["codeshare_group_id"], []).append(f)
    by_day: dict[date, list[dict]] = {}
    for f in flights:
        by_day.setdefault(f["sched_local_final"].date(), []).append(f)

    files, days = {}, []
    for day in sorted(by_day):
        start, end = _utc(day), _utc(day + timedelta(days=1))
        partial = first_check > start + BOARD_KEEPS or last_check < end - BOARD_AHEAD
        window = (start - BOARD_AHEAD, end + BOARD_KEEPS)
        day_gaps = [(a, b) for a, b in gaps if a < window[1] and b > window[0]]
        anchors = [pages.anchor(f["airline"], f["flight_no"], f["direction"], f["sched_local_first"], f["airport"])
                   for f in by_day[day]]
        if len(set(anchors)) != len(anchors):
            raise ValueError(f"two flights on {day} share an anchor: {sorted(a for a in anchors if anchors.count(a) > 1)}")
        files[f"day/{day:%Y-%m-%d}.html"] = pages.day_page(day, by_day[day], obs_by_flight, by_group, day_gaps, partial,
                                                           last_check, ATTRIBUTION, GAP_HOURS)
        dep = sum(f["direction"] == "D" for f in by_day[day])
        days.append({"day": day, "dep": dep, "arr": len(by_day[day]) - dep, "partial": partial})
    files["index.html"] = pages.index_page(days, gaps, first_check, last_check, ATTRIBUTION)
    files["methodology.html"] = pages.methodology_page(ATTRIBUTION, GAP_HOURS, RETIME_WINDOW_HOURS)
    for name in ("search.js", "style.css"):
        files[name] = (STATIC / name).read_text(encoding="utf-8")
    return files


def _siblings(out_dir: Path) -> tuple[Path, Path]:
    return out_dir.with_name(out_dir.name + ".building"), out_dir.with_name(out_dir.name + ".old")


def refuse_foreign(out_dir: Path) -> None:
    """A folder this generator did not make (no marker) is never replaced or deleted: `--out data` must not
    delete the archive copy, and neither may a stray `<out>.building` or `<out>.old` that someone else owns."""
    for folder in (out_dir, *_siblings(out_dir)):
        if folder.exists() and not (folder / MARKER).exists():
            raise SystemExit(f"{folder} exists and was not made by timeline.build (no {MARKER}); refusing to replace it")


def write_site(files: dict[str, str], out_dir: Path) -> None:
    """Build beside out_dir, then swap: the old site moves aside before the new one moves in, so a crash
    leaves either the old site or the new one in place (plus a marked leftover the next build clears)."""
    refuse_foreign(out_dir)
    tmp, old = _siblings(out_dir)
    for leftover in (tmp, old):
        if leftover.exists():
            shutil.rmtree(leftover)
    tmp.mkdir(parents=True)
    (tmp / MARKER).write_text("Made by timeline.build; replaced whole on every build.\n", encoding="utf-8")
    for rel, text in files.items():
        path = tmp / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    if out_dir.exists():
        out_dir.rename(old)
    tmp.rename(out_dir)
    if old.exists():
        shutil.rmtree(old)


def build(model_dir: Path, out_dir: Path) -> dict[str, int]:
    refuse_foreign(out_dir)  # before doing any work
    flights, obs, snaps = load(model_dir)
    files = render(flights, obs, snaps)
    write_site(files, out_dir)
    return {"days": sum(p.startswith("day/") for p in files), "flights": len(flights)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=Path("data/model"))
    parser.add_argument("--out", type=Path, default=Path("site"))
    args = parser.parse_args(argv)
    if not (args.model / "flights.parquet").exists():
        print(f"no model under {args.model}; run model.build first", file=sys.stderr)
        return 2
    counts = build(args.model, args.out)
    print(f"{counts['days']} day pages, {counts['flights']} flight numbers -> {args.out}/index.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
