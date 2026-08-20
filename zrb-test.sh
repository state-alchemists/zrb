set -e

# Targets are the path args (file / dir / file::test). Accept any number of them.
# Back-compat: if none are given but $TEST is set, use $TEST as the single target.
if [ "$#" -eq 0 ] && [ -n "$TEST" ]; then
    set -- "$TEST"
fi

# Lint: pyflakes-class checks (unused imports/vars/redefinitions) on src only.
# F-class catches real bugs without flagging style debt; test/ is not gated yet
# because it carries pre-existing unused-import noise.
flake8 src/zrb --select=F

# Complexity ratchet: fail if any function exceeds the current worst (mccabe 46,
# setup_app_keybindings). This blocks NEW hot-spots from landing without failing
# on today's code; tighten the number as offenders are refactored down.
flake8 src/zrb --select=C901 --max-complexity=46

# Second ratchet, on *true* per-function complexity. mccabe sums a nested
# function's branches into its enclosing function, so a registration function
# (serve_chat_api, setup_app_keybindings) scores as high as genuinely tangled
# logic and pins the flake8 number above at 47. radon scores each function on
# its own, which is the number worth holding down. Tighten as offenders fall.
python - <<'PY'
import json, subprocess, sys

LIMIT = 21
report = json.loads(
    subprocess.run(
        ["radon", "cc", "src/zrb", "--json"], capture_output=True, text=True, check=True
    ).stdout
)
over = [
    (block["complexity"], f"{path}:{block['lineno']} {block['name']}")
    for path, blocks in report.items()
    if isinstance(blocks, list)
    for block in blocks
    if block["complexity"] > LIMIT
]
if over:
    print(f"Per-function complexity above the ratchet ({LIMIT}):")
    for score, where in sorted(over, reverse=True):
        print(f"  {score:3d}  {where}")
    sys.exit(1)
PY

# Private-test-access ratchet: count test/ references into *other* objects'
# private attributes (excluding self.foo, which is a class reading its own
# state, not a coupling problem). Fails if this count exceeds the baseline,
# so the debt can't grow even before more of it is paid down. Tighten this
# number as more accessors replace private reaches.
python - <<'PY'
import re, sys
from pathlib import Path

LIMIT = 400
pattern = re.compile(r'\b\w+\._[a-zA-Z]\w*')
count = sum(
    1
    for path in Path("test").rglob("*.py")
    for m in pattern.finditer(path.read_text())
    if not m.group().startswith("self.")
)
if count > LIMIT:
    print(f"Non-self private test access grew from baseline ({LIMIT}) to {count}.")
    sys.exit(1)
PY

# Static type check. pyright is clean in "standard" mode (pyrightconfig.json);
# keep it that way. Run only on a full pass — it type-checks the whole tree
# regardless of the path args, so gating it per-file would be misleading.
if [ "$#" -eq 0 ]; then
    pyright src/zrb
fi

# Enforce the documented >=90% coverage bar, but only on a FULL run. A scoped run
# (one or more paths passed in) exercises only part of the tree, so a global
# threshold would fail spuriously there.
cov_fail_under=""
if [ "$#" -eq 0 ]; then
    cov_fail_under="--cov-fail-under=90"
fi

pytest \
    --ignore-glob="**/template/**" \
    --ignore-glob="**/fastapp_template/**" \
    --ignore="playground" \
    --ignore="llm-challenges" \
    --cov=zrb \
    --cov-config=".coveragerc" \
    --cov-report="html" \
    --cov-report="term-missing:skip-covered" \
    ${cov_fail_under} \
    "$@"
