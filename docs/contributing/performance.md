🔖 [Documentation Home](../README.md) > [Contributing](./) > Performance

# Performance: Imports and Profiling

Startup time is a feature of this CLI, so where an import costs time is a decision, not trivia. This page covers the two measurements behind that decision: what `import zrb` loads, and where a command spends its wall clock. For the rule that follows the first measurement, see [Coding Conventions → Imports and lazy loading](coding-conventions.md#imports-and-lazy-loading).

## Inspecting Import Performance

To decide whether a module should be lazy-loaded, use the stdlib `-X importtime`:

```bash
python -X importtime -c "import zrb" 2>importtime.log
```

Each line has **self** (µs in that module's own body) and **cumulative** (self + children) time. Sort by **self** — high cumulative with low self just means a heavy child. Use a warm run (import once first); the first run is dominated by cold disk I/O.

## Profiling Zrb

```bash
python -m cProfile -o .cprofile.prof -m zrb --help
```

| Tool | Output | Command |
|------|--------|---------|
| `snakeviz` | Interactive HTML | `pip install snakeviz && snakeviz .cprofile.prof` |
| `flameprof` | Flame graph SVG | `pip install flameprof && flameprof .cprofile.prof > flamegraph.svg` |

## Quick Reference

| Task | Command |
|------|---------|
| Profile imports | `python -X importtime -c "import zrb" 2>importtime.log` |
| Generate profile | `python -m cProfile -o .cprofile.prof -m zrb --help` |
| Visualize (snakeviz) | `snakeviz .cprofile.prof` |
| Visualize (flame) | `flameprof .cprofile.prof > flamegraph.svg` |

---

🔖 [Documentation Home](../README.md) > [Contributing](./) > Performance
