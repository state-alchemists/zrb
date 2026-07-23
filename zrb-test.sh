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

# Complexity ratchet: fail if any function exceeds the current worst (mccabe 47,
# setup_app_keybindings). This blocks NEW hot-spots from landing without failing
# on today's code; tighten the number as offenders are refactored down.
flake8 src/zrb --select=C901 --max-complexity=47

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
