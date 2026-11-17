"""The spoken names of airlines: the name a traveller says aloud ("Lufthansa", not "LUFTHANSA"), kept by hand,
and the list of airlines that still need one (docs/will-it-fly-plan.md, Question 5, answered 2026-11-17: every
airline some flight is grouped under, and every airline with 100 or more counted flights).

This module only holds and lists the names. A page that says one passes it through `views.d()`.

    PYTHONPATH=src python -m timeline.names --model data/model-<date>
"""
import argparse
import sys
from pathlib import Path

from . import blend, counting
from .load import load

FLOOR = 100  # counted flights that make an airline needed even when no flight is grouped under it

# The owner approves this list (the plan's Question 5); the three are the ones the approved lines use.
# The name a traveller says aloud, by airline code. LH, LO and LY are the approved lines' own; the rest are the main
# session's draft of 2026-11-17 from `python -m timeline.names` on the 2026-11-17 model, for the owner's approval at the
# hand check. Marked "check": the airport's own name is odd or unknown to the drafter.
SPOKEN_NAMES: dict[str, str] = {
    "3E": "Electra Airways", "3F": "FlyOne Armenia", "4L": "One Click",  # check
    "4V": "Sky Up Nistru",  # check
    "5F": "FlyOne", "6H": "Israir", "A3": "Aegean", "A4": "Azimuth", "AF": "Air France", "AM": "Aeromexico",
    "AR": "Aerolineas Argentinas", "ASY": "Royal Australian Air Force",  # check: the airport spells it AUSTALIAN
    "AZ": "ITA Airways", "B2": "Belavia", "BA": "British Airways", "BT": "airBaltic", "BZ": "Bluebird Airways",
    "C6": "Centrum Air", "CY": "Cyprus Airways", "DE": "Condor", "DL": "Delta", "E2": "Air Haifa",
    "EAF": "Electra Airways", "ENT": "Enter Air", "ET": "Ethiopian Airlines", "EW": "Eurowings", "EY": "Etihad",
    "FB": "Bulgaria Air", "GQ": "Sky Express", "H4": "HiSky Europe", "H7": "HiSky", "HH": "Qanot Sharq",
    "HM": "Air Seychelles", "HY": "Uzbekistan Airways", "I2": "Iberia Express", "IB": "Iberia", "IZ": "Arkia",
    "J2": "Azerbaijan Airlines", "KL": "KLM", "LH": "Lufthansa", "LO": "LOT", "LX": "Swiss", "LY": "El Al",
    "NO": "Neos", "OS": "Austrian Airlines", "QS": "Smartwings", "RO": "TAROM", "SK": "SAS",
    "SN": "Brussels Airlines", "TO": "Transavia", "TP": "TAP Air Portugal", "U8": "TUS Airways", "UA": "United",
    "UN": "Transaero",  # check: the name of an airline the drafter believes stopped flying (unverified)
    "UX": "Air Europa", "VS": "Virgin Atlantic", "W4": "Wizz Air Malta", "W6": "Wizz Air", "W9": "Wizz Air UK",
    "WZ": "Red Wings",
}


def spoken(code: str) -> str | None:
    """The name a traveller says for airline `code`, or None when none is kept."""
    return SPOKEN_NAMES.get(code)


def needed(records: blend.Records, table: list[dict], flights_: list[counting.Flight]) -> list[tuple[str, str, int, str]]:
    """Each airline that needs a spoken name, sorted by code: (code, published name, counted flights, why). Why is
    "100 or more flights", "a grouping airline" (C8: some flight is grouped under it) or both. The count is the
    flights with a known result (C2: not "unknown"), closed or not, credited to every airline with a number on them,
    whoever the flight is grouped under. It is not the "so far" figure on the pages (C10's labels, the grouping
    airline only)."""
    by_id = {r["flight_id"]: r for r in table}
    counted = dict.fromkeys(records.published, 0)
    for f in flights_:
        if f.result != "unknown":
            for code in {by_id[fid]["airline"] for fid in f.numbers}:
                counted[code] += 1
    out = []
    for code in sorted(counted):
        reasons = ([f"{FLOOR} or more flights"] if counted[code] >= FLOOR else []) + \
                  (["a grouping airline"] if code in records.airlines else [])
        if reasons:
            out.append((code, records.published[code], counted[code], " and ".join(reasons)))
    return out


def main(argv: list[str] | None = None) -> int:
    """Print the airlines that need a spoken name, each with the one kept or "missing". Exit 1 when one is missing,
    2 with no model."""
    parser = argparse.ArgumentParser(prog="python -m timeline.names", description="The airlines that need a "
                                     "spoken name, and the names kept for them.")
    parser.add_argument("--model", type=Path, required=True, help="the model folder (data/model-<date>)")
    args = parser.parse_args(argv)
    if not (args.model / "flights.parquet").exists():
        print(f"no model under {args.model}; run model.build first", file=sys.stderr)
        return 2
    table, obs, snaps = load(args.model)
    missing = 0
    print("code  published name  flights with a known result, any airline with a number on them, closed or not  why  "
          "spoken name")
    for code, published, flights_n, why in needed(blend.records(table, obs, snaps), table,
                                                  counting.flights(table, counting.last_sighting(snaps))):
        name = spoken(code)
        missing += name is None
        print(f"{code}  {published}  {flights_n:,} {'flight' if flights_n == 1 else 'flights'}  {why}  {name or 'missing'}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
