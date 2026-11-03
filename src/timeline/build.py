"""Build the site: python -m timeline.build --model data/model --out site (docs/site-redesign.md, "How it is built")"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import duckdb

from model.report import ATTRIBUTION
from model.rules import GAP_HOURS

from . import flights, views, words

STATIC = Path(__file__).parent / "static"
MARKER = ".timeline-site"
# The board keeps a past flight at least this long and lists a flight this far ahead (measured on 61 boards, 12 to 27 October 2026).
BOARD_KEEPS = timedelta(hours=22)
BOARD_AHEAD = timedelta(hours=72)
CHART_DAYS = 14  # past days (today included) with flights on the front page's chart; every later day is added
OBS_COLUMNS = ("flight_id", "snap_rn", "observed_at", "prev_observed_at", "change_kind", "changed_fields",
               "sched_local", "est_local", "status", "status_he", "terminal", "counters", "zone",
               "airline_name", "airport_name", "city_en", "city_he", "country_en", "country_he")


def _rows(con, sql: str) -> list[dict]:
    cur = con.execute(sql)
    names = [d[0] for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def _utc(day: date) -> datetime:
    """Midnight starting a local Israel date, as naive UTC like the model's times."""
    return datetime.combine(day, time(), tzinfo=words.ISRAEL).astimezone(timezone.utc).replace(tzinfo=None)


def load(model_dir: Path) -> tuple[list[dict], list[dict], list[dict]]:
    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC'")
    src = {t: str(model_dir / f"{t}.parquet").replace("'", "''") for t in ("flights", "observations", "snapshots")}
    table = _rows(con, f"SELECT * FROM '{src['flights']}' ORDER BY sched_local_final, direction, airline, flight_no, flight_id")
    obs = _rows(con, f"SELECT {', '.join(OBS_COLUMNS)} FROM '{src['observations']}' ORDER BY flight_id, snap_rn")
    snaps = _rows(con, f"""SELECT fetched_at, confirmed_until, lag(confirmed_until) OVER (ORDER BY snap_rn) AS prev, gap_before_s
                           FROM '{src['snapshots']}' ORDER BY snap_rn""")
    return table, obs, snaps


def _partial_days(days: set[date], first_check: datetime, last_check: datetime) -> set[date]:
    """Days the records may not hold whole: they began after the board stopped listing the day's earliest
    flights, or ended before it listed the day's latest."""
    out = set()
    for day in days:
        start, end = _utc(day), _utc(day + timedelta(days=1))
        partial = first_check > start + BOARD_KEEPS or last_check < end - BOARD_AHEAD
        if partial:
            out.add(day)
    return out


def render(table: list[dict], obs: list[dict], snaps: list[dict]) -> dict[str, str]:
    """Every page of the site, by path, from the model's flights table, observations and snapshots as `load`
    returns them. Pure: the same rows give the same text."""
    undated = [f"{f['airline']} {f['flight_no']}" for f in table if f["sched_local_final"] is None]
    if undated:
        raise ValueError(f"{len(undated)} flights have no final scheduled time ({undated[:10]}); "
                         "every flight must land on a day page")
    first_check, last_check = snaps[0]["fetched_at"], snaps[-1]["confirmed_until"]  # the last sighting of the board
    gaps = [(s["prev"], s["fetched_at"]) for s in snaps if (s["gap_before_s"] or 0) > GAP_HOURS * 3600]
    rows = flights.make_rows(table, obs, last_check, GAP_HOURS)
    flights.check_unique(rows)
    flights_ = flights.group_flights(rows)
    infos = flights.day_infos(flights_, last_check, _partial_days({r.day for r in rows}, first_check, last_check))
    shown = [i for i in infos if i.state != "ahead"][-CHART_DAYS:]
    chart_days = shown + [i for i in infos if i.state == "ahead"]
    censored = {f["flight_id"]: f["cancel_lead_censored"] for f in table}
    cancelled, known = flights.headline_counts(flights_, last_check)

    files = {"index.html": views.front_page(cancelled, known, flights.featured(rows, censored),
                                            flights.recent_cancellations(flights_), chart_days, infos,
                                            flights.search_entries(rows), last_check)}
    files["how-it-works.html"] = views.how_it_works_page(ATTRIBUTION, gaps)
    files["cancellations.html"] = views.cancellations_page(flights_)
    by_day: dict[date, list[tuple[flights.Row, ...]]] = {}
    for fl in flights_:
        by_day.setdefault(fl[0].day, []).append(fl)
    for info in infos:
        files[f"day/{info.day:%Y-%m-%d}.html"] = views.day_page(info, by_day[info.day])
    by_page: dict[str, list[flights.Row]] = {}
    for r in rows:
        by_page.setdefault(r.page, []).append(r)
    partners = flights.partners(rows)
    since = words.il_time(first_check).date()  # the Israel date of the first record
    for page, page_rows in sorted(by_page.items()):
        files[page] = views.flight_page(page_rows, partners, since)
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
    """Build beside out_dir, then swap: the old site moves aside, then the new one moves in. A crash leaves the
    old site, the new one, or (only between the two renames) neither; every leftover carries the marker, and
    the next build clears it."""
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
    table, obs, snaps = load(model_dir)
    files = render(table, obs, snaps)
    write_site(files, out_dir)
    return {"days": sum(p.startswith("day/") for p in files), "flight_pages": sum(p.startswith("flight/") for p in files),
            "flights": len(table)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=Path("data/model"))
    parser.add_argument("--out", type=Path, default=Path("site"))
    args = parser.parse_args(argv)
    if not (args.model / "flights.parquet").exists():
        print(f"no model under {args.model}; run model.build first", file=sys.stderr)
        return 2
    counts = build(args.model, args.out)
    print(f"{counts['days']} day pages, {counts['flight_pages']} flight pages, {counts['flights']} flight numbers "
          f"-> {args.out}/index.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
