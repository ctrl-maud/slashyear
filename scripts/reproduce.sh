#!/usr/bin/env bash
# reproduce.sh — rebuild the published pages from the snapshot and run the gates.
# Prints PASS or FAIL and exits non-zero on any gate failure.
set -uo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-python3}
fail=0

step () {
  echo; echo "── $* ──"
  "$@" || { echo "FAILED: $*"; fail=1; }
}

if [ ! -d data/claims ]; then
  echo "no data/claims — run scripts/bootstrap.sh first" >&2
  exit 2
fi

# The published site is built with these caps, not the argument defaults — see docs/PIPELINE.md.
step $PY pipeline/build.py --per-section 24 --births-deaths 14 --min-per-section 1

# The year pages are only one of the published page kinds, and the gates below check all of
# them. On a live site these already exist from the previous run; from a cold snapshot they
# have to be regenerated first or coverage/famous/surface fail on pages that are simply absent.
step $PY pipeline/dates.py       # 366 calendar-day pages
step $PY pipeline/cross.py       # topic, decade and century cross-cuts
step $PY pipeline/entities.py    # subject timelines

step $PY pipeline/verify.py
step $PY pipeline/coverage.py
step $PY pipeline/famous.py
step $PY pipeline/surface.py
step $PY pipeline/integrity.py
step $PY pipeline/lifedates.py
step $PY pipeline/theming.py

echo
if [ "$fail" -eq 0 ]; then echo "PASS — every published sentence resolves to the revision it cites."; else echo "FAIL — see the failing stage above."; fi
exit $fail
