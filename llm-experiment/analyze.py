"""Aggregate results/runs.jsonl into markdown tables.

FINDINGS.md is regenerated from this, so every number in it is reproducible
rather than transcribed.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from probes import PROBES_BY_NAME

RESULTS = Path(__file__).parent / "results" / "runs.jsonl"


def load() -> list[dict]:
    """Parse newline- *and* directly-concatenated JSON records.

    A run killed mid-write can leave a record with no trailing newline; the
    next run's append then lands right after it on the same line. Scanning
    with raw_decode (rather than splitlines + json.loads) tolerates that.
    """
    text = RESULTS.read_text()
    decoder, rows, i, n = json.JSONDecoder(), [], 0, len(text)
    while i < n:
        if text[i].isspace():
            i += 1
            continue
        obj, i = decoder.raw_decode(text, i)
        rows.append(obj)
    return rows


def tally(rows: list[dict]) -> tuple[int, int]:
    """(passes, scored). Errored cells are excluded, never counted as failures."""
    scored = [r for r in rows if r["passed"] is not None]
    return sum(bool(r["passed"]) for r in scored), len(scored)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a proportion, in percentage points.

    Wilson rather than the textbook normal approximation because the cells here
    are small and the rates are often near 0 or 1, which is exactly where the
    normal approximation produces bounds outside [0, 1] and understates the
    width.
    """
    if n == 0:
        return 0.0, 100.0
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z / denom * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return 100 * max(0.0, center - half), 100 * min(1.0, center + half)


def rate(rows: list[dict]) -> str:
    """Pass rate with its 95% interval.

    The interval is not decoration. At the n these cells run to, a 10-point gap
    is routinely nothing: every reader of the bare percentages so far -- the
    ADRs and an outside review both -- has read one arm as beating another on a
    difference the interval swallows whole.
    """
    k, n = tally(rows)
    if n == 0:
        return "  --  "
    lo, hi = wilson(k, n)
    return f"{100 * k / n:3.0f}% [{lo:.0f}-{hi:.0f}] {k}/{n}"


def diff(a: list[dict], b: list[dict]) -> tuple[float, float, float]:
    """(difference, low, high) in points for a-minus-b, by Newcombe's method.

    Built from the two Wilson intervals rather than from a pooled standard
    error, which keeps it honest at the small, skewed cells this grid produces.
    """
    ka, na = tally(a)
    kb, nb = tally(b)
    if not na or not nb:
        return 0.0, -100.0, 100.0
    pa, pb = 100 * ka / na, 100 * kb / nb
    la, ha = wilson(ka, na)
    lb, hb = wilson(kb, nb)
    lo = (pa - pb) - ((pa - la) ** 2 + (hb - pb) ** 2) ** 0.5
    hi = (pa - pb) + ((ha - pa) ** 2 + (pb - lb) ** 2) ** 0.5
    return pa - pb, lo, hi


def verdicts(rows: list[dict], col_key: str, cols: list[str]) -> str:
    """Every pairwise arm comparison, and whether it survives its interval.

    Printed under the table because the table cannot say it: two columns of
    percentages invite a comparison the data does not support, and the only
    fix that has ever worked is writing the verdict down next to them.
    """
    lines = []
    for i, left in enumerate(cols):
        for right in cols[i + 1 :]:
            d, lo, hi = diff(
                [r for r in rows if r[col_key] == left],
                [r for r in rows if r[col_key] == right],
            )
            call = "distinguishable" if lo > 0 or hi < 0 else "**not distinguishable**"
            lines.append(
                f"- `{left}` − `{right}`: {d:+.0f}pp, 95% CI [{lo:+.0f}, {hi:+.0f}] — {call}"
            )
    return "\n".join(lines)


def pivot(rows: list[dict], row_key: str, col_key: str, cols: list[str]) -> str:
    grid: dict = defaultdict(lambda: defaultdict(list))
    for r in rows:
        grid[r[row_key]][r[col_key]].append(r)
    out = [
        "| " + row_key + " | " + " | ".join(cols) + " |",
        "|" + "---|" * (len(cols) + 1),
    ]
    for rk in sorted(grid):
        cells = [rate(grid[rk].get(c, [])) for c in cols]
        out.append(f"| {rk} | " + " | ".join(cells) + " |")
    totals = [rate([r for r in rows if r[col_key] == c]) for c in cols]
    out.append("| **all** | " + " | ".join(f"**{t}**" for t in totals) + " |")
    return "\n".join(out)


def section(title: str, body: str) -> str:
    return f"\n## {title}\n\n{body}\n"


def separations(rows: list[dict], cols: list[str]) -> str:
    """The probes on which two arms actually separate, if any.

    The by-probe table is eleven rows of ten-run cells, which is an invitation
    to pick the biggest-looking gap and call it a finding. This does the picking
    by interval instead, and says so plainly when nothing survives -- which has
    been the honest answer more often than not.
    """
    left, right = cols[0], cols[1]
    found = []
    for probe in sorted({r["probe"] for r in rows}):
        at = [r for r in rows if r["probe"] == probe]
        d, lo, hi = diff(
            [r for r in at if r["arm"] == left], [r for r in at if r["arm"] == right]
        )
        if lo > 0 or hi < 0:
            better = left if d > 0 else right
            found.append(
                f"- `{probe}`: {d:+.0f}pp for `{left}` over `{right}`, "
                f"95% CI [{lo:+.0f}, {hi:+.0f}] — **`{better}` wins**"
            )
    if not found:
        return (
            f"No probe separates `{left}` from `{right}` at 95%. Every gap in "
            "the table above is inside its interval."
        )
    return "\n".join(found)


def cost(rows: list[dict], row_key: str, cols: list[str]) -> str:
    """Mean input tokens per cell, beside the pass rate that bought them.

    A pass rate alone cannot answer the question the presets exist to settle,
    because the cheaper prompt is only cheaper if it does not talk the model
    into more turns. Rows without usage data are skipped rather than counted as
    zero -- some cells predate usage recording, and averaging a 0 into them
    would make an arm look cheap for having been measured early.
    """
    grid: dict = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if "input_tokens" in r:
            grid[r[row_key]][r["arm"]].append(r)
    out = [
        f"| {row_key} | " + " | ".join(cols) + " |",
        "|" + "---|" * (len(cols) + 1),
    ]
    for rk in sorted(grid):
        cells = []
        for c in cols:
            got = grid[rk].get(c, [])
            cells.append(
                f"{sum(r['input_tokens'] for r in got) / len(got):,.0f}"
                if got
                else "--"
            )
        out.append(f"| {rk} | " + " | ".join(cells) + " |")
    return "\n".join(out)


def convergence(rows: list[dict]) -> str:
    """What non-convergence costs, as a share of the bill.

    The single most actionable number the harness produces: a cell that hits
    the request limit is a handful of the grid and a large fraction of its
    tokens, which is why a runtime bound on repetition is worth more than any
    amount of prompt trimming (ADR-0077).
    """
    priced = [r for r in rows if "input_tokens" in r]
    if not priced:
        return "_No usage data recorded._"
    lp = [r for r in priced if r.get("looped")]
    cl = [r for r in priced if not r.get("looped")]
    if not lp or not cl:
        return "_No looped cells in this grid._"
    tot = sum(r["input_tokens"] for r in priced)
    lp_tok = sum(r["input_tokens"] for r in lp)
    return "\n".join(
        [
            "| | cells | mean input tok | mean tool calls |",
            "|---|---|---|---|",
            f"| hit the request limit | {len(lp)} | "
            f"{lp_tok / len(lp):,.0f} | {sum(len(r['calls']) for r in lp) / len(lp):.1f} |",
            f"| completed | {len(cl)} | "
            f"{sum(r['input_tokens'] for r in cl) / len(cl):,.0f} | "
            f"{sum(len(r['calls']) for r in cl) / len(cl):.1f} |",
            "",
            f"Cells that ran out of budget are **{len(lp) / len(priced):.0%} "
            f"of scored cells but {lp_tok / tot:.0%} of all input tokens**.",
            "",
            "This is a share of *this harness's* budget, not a production loop "
            "rate: the cap here is a fraction of zrb's shipped "
            "`LLM_MAX_REQUEST_PER_RUN` (300), so a cell counted here would have "
            "kept running in a real session. Read it as non-convergence within "
            "the stated budget.",
        ]
    )


def config_of(row: dict) -> tuple[str, bool, int, str]:
    """The run conditions a row was measured under.

    Defaulted for rows written before the axes existed, which is what they in
    fact ran with: the thin tool surface, no loop guard, 12 requests.

    ``harness_sha`` joins them because the analysis has the same hole the
    resume key had: pooling rows measured against a mock filesystem that
    discarded every write with rows measured against one that does not is a
    single averaged number over two different experiments. Rows predating the
    field report ``legacy``, which keeps them visibly apart rather than
    silently blended.
    """
    return (
        row.get("tools", "thin"),
        bool(row.get("guard", False)),
        int(row.get("request_limit", 12)),
        row.get("harness_sha", "legacy"),
    )


def budget_effect(every: list[dict], want: tuple) -> str:
    """What the request budget alone is worth, where two budgets overlap.

    Its own section because it is not a property of any arm and outranks most of
    what is: a cell cut off mid-task scores as a failure of whichever probe it
    was on, so the budget silently sets a floor under every rate in this file.
    Compared on the intersection of probes actually run at both budgets, since
    a deep re-run is normally targeted at the cells that were cut off.
    """
    surface, guard, _budget, harness = want
    # Harness included: two budgets measured under different mock filesystems
    # differ by more than the budget, which is the comparison this section
    # claims to isolate.
    same = [
        r
        for r in every
        if (
            r.get("tools", "thin"),
            bool(r.get("guard", False)),
            r.get("harness_sha", "legacy"),
        )
        == (surface, guard, harness)
    ]
    budgets = sorted({int(r.get("request_limit") or 12) for r in same})
    if len(budgets) < 2:
        return ""
    low, high = budgets[0], budgets[-1]
    at = {
        b: [r for r in same if int(r.get("request_limit") or 12) == b]
        for b in (low, high)
    }
    shared = {r["probe"] for r in at[low]} & {r["probe"] for r in at[high]}
    if not shared:
        return ""
    at = {b: [r for r in rs if r["probe"] in shared] for b, rs in at.items()}
    d, lo, hi = diff(at[high], at[low])
    call = "distinguishable" if lo > 0 or hi < 0 else "not distinguishable"
    lines = [
        f"| probe | {low} requests | {high} requests |",
        "|---|---|---|",
    ]
    for probe in sorted(shared):
        lines.append(
            f"| {probe} | {rate([r for r in at[low] if r['probe'] == probe])} "
            f"| {rate([r for r in at[high] if r['probe'] == probe])} |"
        )
    lines.append(f"| **all** | **{rate(at[low])}** | **{rate(at[high])}** |")
    cut = {b: sum(bool(r.get("looped")) for r in rs) for b, rs in at.items()}
    lines += [
        "",
        f"Raising the budget from {low} to {high} is worth **{d:+.0f}pp**, "
        f"95% CI [{lo:+.0f}, {hi:+.0f}] — {call}. Cells cut off mid-task fall "
        f"from {cut[low]}/{len(at[low])} to {cut[high]}/{len(at[high])}.",
        "",
        "So most of what this harness recorded as an agent failing to converge "
        "was its own budget ending. That biases every arm comparison one way: a "
        "shorter prompt with fewer tools reaches the same place in fewer turns, "
        "so it collects passes the rulebook it is compared against never gets "
        "to earn.",
    ]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tools", help="analyse only rows run on this tool surface")
    ap.add_argument(
        "--guard",
        choices=("on", "off"),
        help="analyse only rows run with the loop guard on or off",
    )
    ap.add_argument(
        "--request-limit", type=int, help="analyse only rows run at this budget"
    )
    args = ap.parse_args()

    every = load()
    configs = Counter(config_of(r) for r in every)
    # Defaults to the most recently written configuration rather than the
    # largest: a fresh grid is the one you just paid for, and picking by row
    # count silently reports the old one until the new one overtakes it.
    latest = config_of(every[-1]) if every else ("thin", False, 12, "legacy")
    want = (
        args.tools or latest[0],
        (args.guard == "on") if args.guard else latest[1],
        args.request_limit or latest[2],
        # Not a flag: the other three name conditions you choose for a run, while
        # the harness fingerprint names the code that ran it.
        latest[3],
    )
    # One configuration at a time. A `thin`, unguarded row and a `prod`, guarded
    # row differ by 10k characters of tool text and by whether a repeated call is
    # refused; pooling them averages two experiments and reports one number.
    rows = [r for r in every if config_of(r) == want]
    errors = [r for r in rows if r["passed"] is None]
    looped = [r for r in rows if r.get("looped")]
    other = [
        f"{t}/{'guard' if g else 'no-guard'}/{lim}req/{h}: {n:,}"
        for (t, g, lim, h), n in configs.items()
    ]
    out = [
        "# Findings",
        "",
        f"Tool surface **{want[0]}**, loop guard "
        f"**{'on' if want[1] else 'off'}**, request budget **{want[2]}**.",
        "",
        f"{len(rows):,} runs; {len(rows) - len(errors):,} scored, "
        f"{len(errors)} errored, {len(looped)} hit the request limit.",
        "",
        "Generated by `analyze.py`. Pass rates are over scored runs only, and "
        "carry a 95% Wilson interval — read the interval, not the point.",
        "",
        f"Rows on file, by configuration: {'; '.join(sorted(other))}.",
    ]

    x1 = [r for r in rows if r["experiment"] == "X1"]
    ladder = ["zrb-full", "zrb-minimal"]
    out.append(
        section(
            "X1 — preset ladder",
            pivot(x1, "model", "arm", ladder) + "\n\n" + verdicts(x1, "arm", ladder),
        )
    )
    priced = sum("input_tokens" in r for r in rows)
    out.append(
        section(
            "X1 — cost (mean input tokens per cell)",
            cost(x1, "model", ladder)
            + f"\n\nOver the {priced:,} of {len(rows):,} cells with usage recorded. "
            "Read beside the pass rates above: a preset is only cheaper if the "
            "tokens it saves per request are not spent again on extra turns.",
        )
    )
    out.append(section("Cost of non-convergence", convergence(rows)))
    effect = budget_effect(every, want)
    if effect:
        out.append(section("What the request budget alone is worth", effect))
    out.append(
        section(
            "X1 by probe group",
            pivot(
                [{**r, "group": PROBES_BY_NAME[r["probe"]].group} for r in x1],
                "group",
                "arm",
                ladder,
            ),
        )
    )
    out.append(
        section(
            "X1 by probe",
            pivot(x1, "probe", "arm", ladder) + "\n\n" + separations(x1, ladder),
        )
    )

    x2 = [r for r in rows if r["experiment"] == "X2"]
    positions = ["canary-start", "canary-middle", "canary-end"]
    out.append(
        section(
            "X2 — rule position",
            pivot(x2, "model", "arm", positions)
            + "\n\n"
            + verdicts(x2, "arm", positions),
        )
    )

    x3 = [r for r in rows if r["experiment"] == "X3"]
    fam = sorted({r["arm"] for r in x3})
    out.append(section("X3 — family portability", pivot(x3, "model", "arm", fam)))

    x4 = [r for r in rows if r["experiment"] == "X4"]
    base = [r for r in rows if r["experiment"] == "X1" and r["arm"] == "zrb-full"]
    ablations = ["zrb-full", "zrb-full-no-persona", "zrb-full-no-examples"]
    out.append(
        section(
            "X4 — section ablation (zrb-full column is the X1 baseline)",
            pivot(base + x4, "model", "arm", ablations)
            + "\n\n"
            + verdicts(base + x4, "arm", ablations),
        )
    )
    out.append(
        section(
            "X4 by probe group",
            pivot(
                [{**r, "group": PROBES_BY_NAME[r["probe"]].group} for r in base + x4],
                "group",
                "arm",
                ablations,
            ),
        )
    )

    x5 = [r for r in rows if r["experiment"] == "X5"]
    if x5:
        out.append(
            section(
                "X5 — rules `full` has that `minimal` lacks",
                pivot(x5, "probe", "arm", ladder)
                + "\n\n"
                + verdicts(x5, "arm", ladder),
            )
        )
        out.append(section("X5 by model", pivot(x5, "model", "arm", ladder)))

    if errors:
        by_model: dict = defaultdict(list)
        for r in errors:
            by_model[r["model"]].append(r["error"].split(":")[0])
        out.append(
            section(
                "Errored cells",
                "\n".join(
                    f"- `{m}`: {len(v)} " f"({', '.join(sorted(set(v)))})"
                    for m, v in sorted(by_model.items())
                ),
            )
        )

    Path(RESULTS.parent / "FINDINGS.md").write_text("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
