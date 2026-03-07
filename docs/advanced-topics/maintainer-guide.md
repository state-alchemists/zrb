🔖 [Documentation Home](../../README.md) > [Advanced Topics](./) > Maintainer Guide

# Maintainer Guide

This guide is for developers who contribute to or maintain the Zrb project itself. It outlines the project's architecture, conventions, and release process.

---

## Table of Contents

- [Publishing Zrb](#publishing-zrb)
- [Inspecting Import Performance](#inspecting-import-performance)
- [Profiling Zrb](#profiling-zrb)
- [Testing Strategies](#testing-strategies)
- [Evaluating the LLM Agent](#evaluating-and-improving-the-llm-agent)
- [Quick Reference](#quick-reference)

---

## Publishing Zrb

To publish Zrb, you need a PyPI account and an API token.

### Prerequisites

| Platform | URL |
|----------|-----|
| PyPI | https://pypi.org/ |
| TestPyPI | https://test.pypi.org/ |

### Configuration

```bash
poetry config pypi-token.pypi <your-api-token>
```

### Publishing

```bash
source ./project.sh
docker login -U stalchmst
zrb publish all
```

---

## Inspecting Import Performance

To inspect import performance and decide if a module should be lazy-loaded:

```bash
pip install benchmark-imports
python -m benchmark_imports zrb
```

---

## Profiling Zrb

To diagnose performance issues, generate a profile and visualize it.

### Generate Profile

```bash
python -m cProfile -o .cprofile.prof -m zrb --help
```

### Visualization Options

| Tool | Output | Command |
|------|--------|---------|
| `snakeviz` | Interactive HTML | `pip install snakeviz && snakeviz .cprofile.prof` |
| `flameprof` | Flame graph SVG | `pip install flameprof && flameprof .cprofile.prof > flamegraph.svg` |

---

## Testing Strategies

The test suite uses `pytest` fixtures and `unittest.mock.patch` (as decorators or context managers) to isolate components and ensure correctness.

Refer to existing tests in the `test/` directory for examples.

---

## Evaluating and Improving the LLM Agent

To maintain and improve the quality of the Zrb LLM agent, the project uses a set of automated evaluation challenges located in the `llm-challenges/` directory.

> 💡 **See:** `llm-challenges/AGENTS.md` for full evaluation protocol instructions.

### Process Overview

| Step | Action |
|------|--------|
| 1. Execute | Run challenges for all model combinations |
| 2. Analyze | Review generated REPORT.md for failures |
| 3. Optimize | Refactor prompts or tools |
| 4. Verify | Re-run challenges to confirm improvements |

### Running Challenges

```bash
cd llm-challenges/

# Quick verification test
python runner.py --models openai:gpt-4o google-gla:gemini-1.5-pro --timeout 120 --verbose

# Full test suite
python runner.py --timeout 3600 --parallelism 12 --verbose --models <model-list>
```

### Analyzing Results

| Output | Location |
|--------|----------|
| Report | `llm-challenges/experiment/REPORT.md` |
| Results | `llm-challenges/experiment/results.json` |

### Optimization Targets

| Target | Location |
|--------|----------|
| Prompts | `src/zrb/llm/prompt/markdown/` |
| Tools | `src/zrb/llm/tool/` |

---

## Quick Reference

| Task | Command |
|------|---------|
| Publish | `zrb publish all` |
| Profile imports | `python -m benchmark_imports zrb` |
| Generate profile | `python -m cProfile -o .cprofile.prof -m zrb --help` |
| Visualize (snakeviz) | `snakeviz .cprofile.prof` |
| Visualize (flame) | `flameprof .cprofile.prof > flamegraph.svg` |
| Run LLM challenges | `python runner.py --models <list> --verbose` |

---