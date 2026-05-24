# Executive Summary

**5 models, 6 challenges, 90 trials** (3 per cell). DeepSeek V4 Flash dominates with a **perfect 18/18** (100% pass, 83.3% EXCELLENT). The refactor challenge is the hardest at **26.7% pass** — the single gate is removing hardcoded credentials (`password123`). GPT-4o is the fastest (31.3s avg) but most erratic (7 failures, many catastrophic). Gemini 3.5 Flash is borderline unusable with **55.6% timeout rate** (10/18). The concurrency-lock check is the most common PASS→EXCELLENT differentiator across bug-fix and integration-bug challenges.

| Model | Trials | Pass | Fail+Timeout | Pass % | Avg Time | Grade |
|-------|--------|------|-------------|--------|----------|-------|
| **deepseek:deepseek-v4-flash** | 18 | 18 | 0 | **100%** | 70.0s | 🏆 |
| **google:gemini-2.5-flash** | 18 | 14 | 4 | **77.8%** | 73.3s | ★★★ |
| **openai:gpt-4o** | 18 | 11 | 7 | **61.1%** | 31.3s | ★★ |
| **ollama:gemma4:31b-cloud** | 18 | 11 | 7 | **61.1%** | 152.8s | ★★ |
| **google:gemini-3.5-flash** | 18 | 8 | 10 | **44.4%** | 384.6s | ★ |

## Deep Dive Analysis

### 1. DeepSeek V4 Flash — The Clear Winner

Perfect across all 6 challenges, 3 trials each. The only model with **100% pass on refactor** — every other model failed or timed out here. Also perfect EXCELLENT on feature, copywriting, and research (3/3 each). No timeouts, no failures. Average 70s is middle of the pack, but reliability is unmatched. **Default recommendation for production use.**

### 2. Why Others Fail — Specific Failure Modes

- **Refactor (26.7% pass, hardest challenge):** The common fail gate is hardcoded credentials — `password123` left in the output. Gemini 2.5 Flash (2/3 fails), Gemma4 (3/3 fails), and GPT-4o (2/3 fails) all miss this. Only DeepSeek V4 Flash consistently removes it. Root cause: models do pattern refactoring but skip the explicit credential-removal step. Fix: add "remove ALL hardcoded credentials" as an explicit prompt check.

- **Feature (66.7% pass):** Failures are all runtime errors — missing imports (`TaskPriority` not defined, `Optional` not imported), decorator issues, undefined symbols. GPT-4o fails 2/3 with import errors; Gemini 2.5 Flash fails 1/3 with an ImportError. These are **compilation failures** the model should catch before declaring done.

- **Copywriting (73.3% pass):** GPT-4o trial 1 fails because `MIGRATION.md` was never created — the model either wrote to a different filename or didn't write a file. Gemma4 has two near-misses (378 and 399 words, just under the 400-word threshold).

- **Research (86.7% pass):** GPT-4o trials 2 and 3 fail completely — `No ADR markdown file found`. The model finished in 11s and 14s but produced no output file. This suggests the model wrote output to stdout or a different path rather than creating the expected file.

- **Integration-bug (86.7% pass):** All failures are from the lock check (PASS instead of EXCELLENT) plus one catastrophic Gemma4 trial where charges are wildly miscalculated (charged $1200 vs expected $500).

### 3. Gemini 3.5 Flash — Broken Tool-Calling

**10 of 18 trials (55.6%) timed out at 600s.** When it completes, quality is high (7/8 completed = EXCELLENT, 1 PASS), but it cannot finish bug-fix (0/3), copywriting (0/3), or refactor (0/3). The timeout pattern is **consistent per challenge** — the model stalls on certain instruction types, likely looping on tool calls or reasoning chains. **Recommendation: exclude from unsupervised evaluation until timeout issue is resolved; investigate lower parallelism or anti-loop prompt guidance.**

### 4. GPT-4o — Fastest, Most Erratic

At **31.3s average**, GPT-4o is 2-5x faster than competitors. But it has **7 failures** — the most of any model — and several are **catastrophic**: missing files, undefined symbols, broken imports. The pattern is fast, plausible, but unverified output. Good for iterative prototyping with human review; risky for unattended operation.

### 5. Gemma4:31b — Inconsistent Open-Weight Contender

Solid on research (3/3) and copywriting (3/3), but **refactor is a total loss (0/3)** — all leave hardcoded `password123`. Integration-bug has a wild outlier (trial 3 charges wrong amounts). Average 152.8s is 2x slower than top models. Useful for non-coding tasks where model preference doesn't matter.

### 6. The Lock Gate — Why PASS ≠ EXCELLENT

The most common PASS→EXCELLENT differentiator is the **concurrency primitive check**. Models that fix the core race condition (e.g., async checkout) but don't add `threading.Lock` or equivalent get 0.85 instead of 1.0. Across bug-fix (4 EXCELLENT vs 7 PASS) and integration-bug (8 EXCELLENT vs 5 PASS), ~40% of trials hit this gate. **Fix: add a verification step to prompts: "After fixing race conditions, add a concurrency primitive (Lock, Semaphore)."**

### 7. Duration & Cost Analysis

| Model | Avg Time | Min | Max | Notes |
|-------|----------|-----|-----|-------|
| openai:gpt-4o | 31.3s | 11.0s | 77.9s | Low variance |
| deepseek:deepseek-v4-flash | 70.0s | 29.5s | 141.0s | Moderate variance |
| google:gemini-2.5-flash | 73.3s | 13.4s | 170.7s | Fast floor on easy tasks |
| ollama:gemma4:31b-cloud | 152.8s | 20.9s | 600.0s | High variance; timeout skew |
| google:gemini-3.5-flash | 384.6s | 66.4s | 600.0s | Skewed by 10 timeouts |

### 8. Token Tracking Gap

All 90 trials show **0 tokens** across all columns. The evaluator does not capture token usage from the `zrb` system. Real consumption is non-trivial, especially for Gemini 3.5 Flash's 600s runs. **Action: wire token tracking into the evaluator's trial runner.**

### 9. Recommendations

| Use Case | Model | Why |
|----------|-------|-----|
| Production / unattended | **deepseek:deepseek-v4-flash** | 100% pass, consistent EXCELLENT |
| Interactive / cost-sensitive | **google:gemini-2.5-flash** | 77.8% pass, fast (~73s), cheaper |
| Quick prototyping | **openai:gpt-4o** | 31s avg, fast iteration, verify output |
| Avoid for now | **google:gemini-3.5-flash** | 55.6% timeout, unusable unsupervised |
| Mixed (Ollama Cloud) | **ollama:gemma4:31b-cloud** | OK for research/copywriting; avoid refactor |

### 10. Optimize zrb Prompts

Highest-leverage prompt fixes:
1. **Refactor**: add "Check for and remove ALL hardcoded credentials (passwords, tokens, keys); replace with environment variables."
2. **Concurrency**: add "After fixing race conditions, verify a proper concurrency primitive (Lock, Semaphore) protects shared state."
3. **Verification**: add "Before finishing, verify imports resolve and the code compiles."

---

# Experiment Report
**Experiment ID**: c9b8e84c-ec9d-4e81-9b9f-53aad2e043b0
**Started**: 2026-05-24T09:38:06.439986+00:00
**Completed**: 2026-05-24T11:19:01.158061+00:00
**Generated**: 2026-05-24T11:19:01.158061+00:00

**Total trials**: 90

## Overall Status

| Status | Count | % |
|--------|-------|---|
| 👍 EXCELLENT | 49 | 54.4 |
| ✅ PASS | 13 | 14.4 |
| ❌ FAIL | 16 | 17.8 |
| ⏱️ TIMEOUT | 12 | 13.3 |

## By Model

| Model | Trials | 👍 | ✅ | ❌ | ⏱️ | ⚠️ | Avg dur (s) |
|-------|--------|----|----|----|----|----|-------------|
| deepseek:deepseek-v4-flash | 18 | 15 | 3 | 0 | 0 | 0 | 70.0 |
| google:gemini-2.5-flash | 18 | 12 | 2 | 3 | 1 | 0 | 73.3 |
| google:gemini-3.5-flash | 18 | 7 | 1 | 0 | 10 | 0 | 384.6 |
| ollama:gemma4:31b-cloud | 18 | 10 | 1 | 6 | 1 | 0 | 152.8 |
| openai:gpt-4o | 18 | 5 | 6 | 7 | 0 | 0 | 31.3 |

## By Test Case

| Test Case | Trials | 👍 | ✅ | ❌ | ⏱️ | ⚠️ |
|-----------|--------|----|----|----|----|----|
| bug-fix | 15 | 4 | 7 | 1 | 3 | 0 |
| copywriting | 15 | 11 | 0 | 1 | 3 | 0 |
| feature | 15 | 9 | 1 | 4 | 1 | 0 |
| integration-bug | 15 | 8 | 5 | 1 | 1 | 0 |
| refactor | 15 | 4 | 0 | 7 | 4 | 0 |
| research | 15 | 13 | 0 | 2 | 0 | 0 |

## Grid

| Model | bug-fix | copywriting | feature | integration-bug | refactor | research |
|-----|-------|-----------|-------|---------------|--------|--------|
| deepseek:deepseek-v4-flash | ✅ 👍 ✅ | 👍 👍 👍 | 👍 👍 👍 | 👍 ✅ 👍 | 👍 👍 👍 | 👍 👍 👍 |
| google:gemini-2.5-flash | 👍 ✅ 👍 | 👍 👍 👍 | 👍 ❌ 👍 | 👍 👍 ✅ | ❌ ⏱️ ❌ | 👍 👍 👍 |
| google:gemini-3.5-flash | ⏱️ ⏱️ ⏱️ | ⏱️ ⏱️ ⏱️ | ⏱️ 👍 👍 | ✅ 👍 👍 | ⏱️ ⏱️ ⏱️ | 👍 👍 👍 |
| ollama:gemma4:31b-cloud | ❌ ✅ 👍 | 👍 👍 👍 | 👍 ❌ 👍 | ⏱️ 👍 ❌ | ❌ ❌ ❌ | 👍 👍 👍 |
| openai:gpt-4o | ✅ ✅ ✅ | ❌ 👍 👍 | ❌ ❌ ✅ | ✅ ✅ 👍 | 👍 ❌ ❌ | 👍 ❌ ❌ |

## Failing / Timeout Trials

| Model | Test Case | Trial | Status | Duration (s) |
|-------|-----------|-------|--------|--------------|
| google:gemini-2.5-flash | feature | 2 | ❌ FAIL | 25.5 |
| google:gemini-2.5-flash | refactor | 1 | ❌ FAIL | 102.4 |
| google:gemini-2.5-flash | refactor | 2 | ⏱️ TIMEOUT | 600.0 |
| google:gemini-2.5-flash | refactor | 3 | ❌ FAIL | 170.7 |
| google:gemini-3.5-flash | bug-fix | 1 | ⏱️ TIMEOUT | 600.0 |
| google:gemini-3.5-flash | bug-fix | 2 | ⏱️ TIMEOUT | 600.0 |
| google:gemini-3.5-flash | bug-fix | 3 | ⏱️ TIMEOUT | 600.0 |
| google:gemini-3.5-flash | copywriting | 1 | ⏱️ TIMEOUT | 600.0 |
| google:gemini-3.5-flash | copywriting | 2 | ⏱️ TIMEOUT | 600.0 |
| google:gemini-3.5-flash | copywriting | 3 | ⏱️ TIMEOUT | 600.0 |
| google:gemini-3.5-flash | feature | 1 | ⏱️ TIMEOUT | 600.0 |
| google:gemini-3.5-flash | refactor | 1 | ⏱️ TIMEOUT | 600.0 |
| google:gemini-3.5-flash | refactor | 2 | ⏱️ TIMEOUT | 600.0 |
| google:gemini-3.5-flash | refactor | 3 | ⏱️ TIMEOUT | 600.0 |
| ollama:gemma4:31b-cloud | bug-fix | 1 | ❌ FAIL | 261.3 |
| ollama:gemma4:31b-cloud | feature | 2 | ❌ FAIL | 245.6 |
| ollama:gemma4:31b-cloud | integration-bug | 1 | ⏱️ TIMEOUT | 600.0 |
| ollama:gemma4:31b-cloud | integration-bug | 3 | ❌ FAIL | 86.6 |
| ollama:gemma4:31b-cloud | refactor | 1 | ❌ FAIL | 131.1 |
| ollama:gemma4:31b-cloud | refactor | 2 | ❌ FAIL | 183.5 |
| ollama:gemma4:31b-cloud | refactor | 3 | ❌ FAIL | 115.1 |
| openai:gpt-4o | copywriting | 1 | ❌ FAIL | 21.1 |
| openai:gpt-4o | feature | 1 | ❌ FAIL | 45.0 |
| openai:gpt-4o | feature | 2 | ❌ FAIL | 46.0 |
| openai:gpt-4o | refactor | 2 | ❌ FAIL | 23.9 |
| openai:gpt-4o | refactor | 3 | ❌ FAIL | 77.9 |
| openai:gpt-4o | research | 2 | ❌ FAIL | 11.0 |
| openai:gpt-4o | research | 3 | ❌ FAIL | 14.1 |

## Summary

| Model | Test Case | Trial | Status | Duration (s) | Score | Total Tokens | Input | Output | Cache | Tool Calls |
|-------|-----------|-------|--------|-------------|-------|--------------|-------|--------|-------|------------|
| deepseek:deepseek-v4-flash | bug-fix | 1 | ✅ PASS | 41.43 | 0.85 | **0** | 0 | 0 | 0 | **0** |
| deepseek:deepseek-v4-flash | bug-fix | 2 | 👍 EXCELLENT | 44.33 | **1.00** | **0** | 0 | 0 | 0 | **0** |
| deepseek:deepseek-v4-flash | bug-fix | 3 | ✅ PASS | 29.48 | 0.85 | **0** | 0 | 0 | 0 | **0** |
| deepseek:deepseek-v4-flash | copywriting | 1 | 👍 EXCELLENT | 53.12 | **1.00** | **0** | 0 | 0 | 0 | **0** |
| deepseek:deepseek-v4-flash | copywriting | 2 | 👍 EXCELLENT | 41.33 | **1.00** | **0** | 0 | 0 | 0 | **0** |
| deepseek:deepseek-v4-flash | copywriting | 3 | 👍 EXCELLENT | 35.82 | **1.00** | **0** | 0 | 0 | 0 | **0** |
| deepseek:deepseek-v4-flash | feature | 1 | 👍 EXCELLENT | 65.53 | **1.00** | **0** | 0 | 0 | 0 | **0** |
| deepseek:deepseek-v4-flash | feature | 2 | 👍 EXCELLENT | 86.17 | **1.00** | **0** | 0 | 0 | 0 | **0** |
| deepseek:deepseek-v4-flash | feature | 3 | 👍 EXCELLENT | 83.93 | **1.00** | **0** | 0 | 0 | 0 | **0** |
| deepseek:deepseek-v4-flash | integration-bug | 1 | 👍 EXCELLENT | 106.61 | **1.00** | **0** | 0 | 0 | 0 | **0** |
| deepseek:deepseek-v4-flash | integration-bug | 2 | ✅ PASS | 104.12 | 0.85 | **0** | 0 | 0 | 0 | **0** |
| deepseek:deepseek-v4-flash | integration-bug | 3 | 👍 EXCELLENT | 72.58 | **1.00** | **0** | 0 | 0 | 0 | **0** |
| deepseek:deepseek-v4-flash | refactor | 1 | 👍 EXCELLENT | 45.59 | **1.00** | **0** | 0 | 0 | 0 | **0** |
| deepseek:deepseek-v4-flash | refactor | 2 | 👍 EXCELLENT | 128.81 | **1.00** | **0** | 0 | 0 | 0 | **0** |
| deepseek:deepseek-v4-flash | refactor | 3 | 👍 EXCELLENT | 141.00 | **1.00** | **0** | 0 | 0 | 0 | **0** |
| deepseek:deepseek-v4-flash | research | 1 | 👍 EXCELLENT | 73.14 | **1.00** | **0** | 0 | 0 | 0 | **0** |
| deepseek:deepseek-v4-flash | research | 2 | 👍 EXCELLENT | 55.53 | **1.00** | **0** | 0 | 0 | 0 | **0** |
| deepseek:deepseek-v4-flash | research | 3 | 👍 EXCELLENT | 51.75 | **1.00** | **0** | 0 | 0 | 0 | **0** |
| google:gemini-2.5-flash | bug-fix | 1 | 👍 EXCELLENT | 23.71 | **1.00** | **0** | 0 | 0 | 0 | **0** |
| google:gemini-2.5-flash | bug-fix | 2 | ✅ PASS | **23.26** | 0.85 | **0** | 0 | 0 | 0 | **0** |
| google:gemini-2.5-flash | bug-fix | 3 | 👍 EXCELLENT | 43.84 | **1.00** | **0** | 0 | 0 | 0 | **0** |
| google:gemini-2.5-flash | copywriting | 1 | 👍 EXCELLENT | 22.58 | **1.00** | **0** | 0 | 0 | 0 | **0** |
| google:gemini-2.5-flash | copywriting | 2 | 👍 EXCELLENT | **13.78** | **1.00** | **0** | 0 | 0 | 0 | **0** |
| google:gemini-2.5-flash | copywriting | 3 | 👍 EXCELLENT | 17.48 | **1.00** | **0** | 0 | 0 | 0 | **0** |
| google:gemini-2.5-flash | feature | 1 | 👍 EXCELLENT | 25.02 | **1.00** | **0** | 0 | 0 | 0 | **0** |
| google:gemini-2.5-flash | feature | 2 | ❌ FAIL | 25.46 | 0.00 | 0 | 0 | 0 | 0 | 0 |
| google:gemini-2.5-flash | feature | 3 | 👍 EXCELLENT | **16.38** | 0.89 | **0** | 0 | 0 | 0 | **0** |
| google:gemini-2.5-flash | integration-bug | 1 | 👍 EXCELLENT | 57.91 | **1.00** | **0** | 0 | 0 | 0 | **0** |
| google:gemini-2.5-flash | integration-bug | 2 | 👍 EXCELLENT | 79.07 | **1.00** | **0** | 0 | 0 | 0 | **0** |
| google:gemini-2.5-flash | integration-bug | 3 | ✅ PASS | 37.39 | 0.85 | **0** | 0 | 0 | 0 | **0** |
| google:gemini-2.5-flash | refactor | 1 | ❌ FAIL | 102.37 | 1.00 | 0 | 0 | 0 | 0 | 0 |
| google:gemini-2.5-flash | refactor | 2 | ⏱️ TIMEOUT | 600.03 |  | 0 | 0 | 0 | 0 | 0 |
| google:gemini-2.5-flash | refactor | 3 | ❌ FAIL | 170.74 | 1.00 | 0 | 0 | 0 | 0 | 0 |
| google:gemini-2.5-flash | research | 1 | 👍 EXCELLENT | 26.02 | **1.00** | **0** | 0 | 0 | 0 | **0** |
| google:gemini-2.5-flash | research | 2 | 👍 EXCELLENT | **13.41** | **1.00** | **0** | 0 | 0 | 0 | **0** |
| google:gemini-2.5-flash | research | 3 | 👍 EXCELLENT | 21.60 | **1.00** | **0** | 0 | 0 | 0 | **0** |
| google:gemini-3.5-flash | bug-fix | 1 | ⏱️ TIMEOUT | 600.02 |  | 0 | 0 | 0 | 0 | 0 |
| google:gemini-3.5-flash | bug-fix | 2 | ⏱️ TIMEOUT | 600.02 |  | 0 | 0 | 0 | 0 | 0 |
| google:gemini-3.5-flash | bug-fix | 3 | ⏱️ TIMEOUT | 600.02 |  | 0 | 0 | 0 | 0 | 0 |
| google:gemini-3.5-flash | copywriting | 1 | ⏱️ TIMEOUT | 600.02 |  | 0 | 0 | 0 | 0 | 0 |
| google:gemini-3.5-flash | copywriting | 2 | ⏱️ TIMEOUT | 600.03 |  | 0 | 0 | 0 | 0 | 0 |
| google:gemini-3.5-flash | copywriting | 3 | ⏱️ TIMEOUT | 600.02 |  | 0 | 0 | 0 | 0 | 0 |
| google:gemini-3.5-flash | feature | 1 | ⏱️ TIMEOUT | 600.02 |  | 0 | 0 | 0 | 0 | 0 |
| google:gemini-3.5-flash | feature | 2 | 👍 EXCELLENT | 118.66 | **1.00** | **0** | 0 | 0 | 0 | **0** |
| google:gemini-3.5-flash | feature | 3 | 👍 EXCELLENT | 151.40 | **1.00** | **0** | 0 | 0 | 0 | **0** |
| google:gemini-3.5-flash | integration-bug | 1 | ✅ PASS | 133.22 | 0.85 | **0** | 0 | 0 | 0 | **0** |
| google:gemini-3.5-flash | integration-bug | 2 | 👍 EXCELLENT | 108.41 | **1.00** | **0** | 0 | 0 | 0 | **0** |
| google:gemini-3.5-flash | integration-bug | 3 | 👍 EXCELLENT | 168.60 | **1.00** | **0** | 0 | 0 | 0 | **0** |
| google:gemini-3.5-flash | refactor | 1 | ⏱️ TIMEOUT | 600.02 |  | 0 | 0 | 0 | 0 | 0 |
| google:gemini-3.5-flash | refactor | 2 | ⏱️ TIMEOUT | 600.02 |  | 0 | 0 | 0 | 0 | 0 |
| google:gemini-3.5-flash | refactor | 3 | ⏱️ TIMEOUT | 600.02 |  | 0 | 0 | 0 | 0 | 0 |
| google:gemini-3.5-flash | research | 1 | 👍 EXCELLENT | 89.20 | **1.00** | **0** | 0 | 0 | 0 | **0** |
| google:gemini-3.5-flash | research | 2 | 👍 EXCELLENT | 66.36 | **1.00** | **0** | 0 | 0 | 0 | **0** |
| google:gemini-3.5-flash | research | 3 | 👍 EXCELLENT | 86.49 | **1.00** | **0** | 0 | 0 | 0 | **0** |
| ollama:gemma4:31b-cloud | bug-fix | 1 | ❌ FAIL | 261.31 | 0.00 | 0 | 0 | 0 | 0 | 0 |
| ollama:gemma4:31b-cloud | bug-fix | 2 | ✅ PASS | 67.23 | 0.85 | **0** | 0 | 0 | 0 | **0** |
| ollama:gemma4:31b-cloud | bug-fix | 3 | 👍 EXCELLENT | 54.79 | **1.00** | **0** | 0 | 0 | 0 | **0** |
| ollama:gemma4:31b-cloud | copywriting | 1 | 👍 EXCELLENT | 20.99 | 0.88 | **0** | 0 | 0 | 0 | **0** |
| ollama:gemma4:31b-cloud | copywriting | 2 | 👍 EXCELLENT | 218.43 | 0.88 | **0** | 0 | 0 | 0 | **0** |
| ollama:gemma4:31b-cloud | copywriting | 3 | 👍 EXCELLENT | 29.63 | **1.00** | **0** | 0 | 0 | 0 | **0** |
| ollama:gemma4:31b-cloud | feature | 1 | 👍 EXCELLENT | 252.75 | **1.00** | **0** | 0 | 0 | 0 | **0** |
| ollama:gemma4:31b-cloud | feature | 2 | ❌ FAIL | 245.59 | 0.00 | 0 | 0 | 0 | 0 | 0 |
| ollama:gemma4:31b-cloud | feature | 3 | 👍 EXCELLENT | 222.26 | **1.00** | **0** | 0 | 0 | 0 | **0** |
| ollama:gemma4:31b-cloud | integration-bug | 1 | ⏱️ TIMEOUT | 600.03 |  | 0 | 0 | 0 | 0 | 0 |
| ollama:gemma4:31b-cloud | integration-bug | 2 | 👍 EXCELLENT | 119.77 | **1.00** | **0** | 0 | 0 | 0 | **0** |
| ollama:gemma4:31b-cloud | integration-bug | 3 | ❌ FAIL | 86.62 | 0.17 | 0 | 0 | 0 | 0 | 0 |
| ollama:gemma4:31b-cloud | refactor | 1 | ❌ FAIL | 131.11 | 1.00 | 0 | 0 | 0 | 0 | 0 |
| ollama:gemma4:31b-cloud | refactor | 2 | ❌ FAIL | 183.46 | 1.00 | 0 | 0 | 0 | 0 | 0 |
| ollama:gemma4:31b-cloud | refactor | 3 | ❌ FAIL | 115.13 | 1.00 | 0 | 0 | 0 | 0 | 0 |
| ollama:gemma4:31b-cloud | research | 1 | 👍 EXCELLENT | 52.94 | 0.88 | **0** | 0 | 0 | 0 | **0** |
| ollama:gemma4:31b-cloud | research | 2 | 👍 EXCELLENT | 42.75 | **1.00** | **0** | 0 | 0 | 0 | **0** |
| ollama:gemma4:31b-cloud | research | 3 | 👍 EXCELLENT | 45.25 | **1.00** | **0** | 0 | 0 | 0 | **0** |
| openai:gpt-4o | bug-fix | 1 | ✅ PASS | 26.73 | 0.85 | **0** | 0 | 0 | 0 | **0** |
| openai:gpt-4o | bug-fix | 2 | ✅ PASS | 24.60 | 0.85 | **0** | 0 | 0 | 0 | **0** |
| openai:gpt-4o | bug-fix | 3 | ✅ PASS | 28.39 | 0.85 | **0** | 0 | 0 | 0 | **0** |
| openai:gpt-4o | copywriting | 1 | ❌ FAIL | 21.12 | 0.00 | 0 | 0 | 0 | 0 | 0 |
| openai:gpt-4o | copywriting | 2 | 👍 EXCELLENT | 26.30 | 0.88 | **0** | 0 | 0 | 0 | **0** |
| openai:gpt-4o | copywriting | 3 | 👍 EXCELLENT | 26.65 | 0.88 | **0** | 0 | 0 | 0 | **0** |
| openai:gpt-4o | feature | 1 | ❌ FAIL | 45.01 | 0.00 | 0 | 0 | 0 | 0 | 0 |
| openai:gpt-4o | feature | 2 | ❌ FAIL | 45.97 | 0.00 | 0 | 0 | 0 | 0 | 0 |
| openai:gpt-4o | feature | 3 | ✅ PASS | 39.29 | 0.67 | **0** | 0 | 0 | 0 | **0** |
| openai:gpt-4o | integration-bug | 1 | ✅ PASS | **23.37** | 0.85 | **0** | 0 | 0 | 0 | **0** |
| openai:gpt-4o | integration-bug | 2 | ✅ PASS | 28.81 | 0.85 | **0** | 0 | 0 | 0 | **0** |
| openai:gpt-4o | integration-bug | 3 | 👍 EXCELLENT | 48.05 | **1.00** | **0** | 0 | 0 | 0 | **0** |
| openai:gpt-4o | refactor | 1 | 👍 EXCELLENT | **34.96** | **1.00** | **0** | 0 | 0 | 0 | **0** |
| openai:gpt-4o | refactor | 2 | ❌ FAIL | 23.89 | 0.88 | 0 | 0 | 0 | 0 | 0 |
| openai:gpt-4o | refactor | 3 | ❌ FAIL | 77.92 | 0.75 | 0 | 0 | 0 | 0 | 0 |
| openai:gpt-4o | research | 1 | 👍 EXCELLENT | 16.41 | 0.88 | **0** | 0 | 0 | 0 | **0** |
| openai:gpt-4o | research | 2 | ❌ FAIL | 11.04 | 0.00 | 0 | 0 | 0 | 0 | 0 |
| openai:gpt-4o | research | 3 | ❌ FAIL | 14.10 | 0.00 | 0 | 0 | 0 | 0 | 0 |

## Per-Trial Details

### deepseek:deepseek-v4-flash / bug-fix / Trial 1

- **Status**: ✅ PASS
- **Duration**: 41.43s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/deepseek_deepseek-v4-flash/bug-fix/trial-1/history/deepseek_deepseek-v4-flash-bug-fix-trial-1.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/deepseek_deepseek-v4-flash/bug-fix/trial-1/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 0.85
  - run_1: ✓ done=10, failed=2, stuck=0
  - run_2: ✓ done=10, failed=2, stuck=0
  - run_3: ✓ done=10, failed=2, stuck=0
  - run_4: ✓ done=10, failed=2, stuck=0
  - run_5: ✓ done=10, failed=2, stuck=0
  - concurrency_primitive: ✗ No Lock primitive detected

### deepseek:deepseek-v4-flash / bug-fix / Trial 2

- **Status**: 👍 EXCELLENT
- **Duration**: 44.33s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/deepseek_deepseek-v4-flash/bug-fix/trial-2/history/deepseek_deepseek-v4-flash-bug-fix-trial-2.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/deepseek_deepseek-v4-flash/bug-fix/trial-2/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - run_1: ✓ done=10, failed=2, stuck=0
  - run_2: ✓ done=10, failed=2, stuck=0
  - run_3: ✓ done=10, failed=2, stuck=0
  - run_4: ✓ done=10, failed=2, stuck=0
  - run_5: ✓ done=10, failed=2, stuck=0
  - concurrency_primitive: ✓ Lock found in source

### deepseek:deepseek-v4-flash / bug-fix / Trial 3

- **Status**: ✅ PASS
- **Duration**: 29.48s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/deepseek_deepseek-v4-flash/bug-fix/trial-3/history/deepseek_deepseek-v4-flash-bug-fix-trial-3.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/deepseek_deepseek-v4-flash/bug-fix/trial-3/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 0.85
  - run_1: ✓ done=10, failed=2, stuck=0
  - run_2: ✓ done=10, failed=2, stuck=0
  - run_3: ✓ done=10, failed=2, stuck=0
  - run_4: ✓ done=10, failed=2, stuck=0
  - run_5: ✓ done=10, failed=2, stuck=0
  - concurrency_primitive: ✗ No Lock primitive detected

### deepseek:deepseek-v4-flash / copywriting / Trial 1

- **Status**: 👍 EXCELLENT
- **Duration**: 53.12s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/deepseek_deepseek-v4-flash/copywriting/trial-1/history/deepseek_deepseek-v4-flash-copywriting-trial-1.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/deepseek_deepseek-v4-flash/copywriting/trial-1/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - migration_file: ✓ Using MIGRATION.md
  - markdown_headings: ✓ Has markdown headings
  - substantial_content: ✓ 1223 words (need ≥400)
  - code_blocks: ✓ 22 fenced code block(s) (need ≥3)
  - auth_header_change: ✓ Authorization: Bearer documented
  - uuid_id_change: ✓ UUID id change documented
  - field_rename: ✓ done→completed rename documented
  - project_id_and_v2_prefix: ✓ project_id + /v2/ prefix covered
  - checklist_or_upgrade: ✓ Checklist or upgrade command present

### deepseek:deepseek-v4-flash / copywriting / Trial 2

- **Status**: 👍 EXCELLENT
- **Duration**: 41.33s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/deepseek_deepseek-v4-flash/copywriting/trial-2/history/deepseek_deepseek-v4-flash-copywriting-trial-2.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/deepseek_deepseek-v4-flash/copywriting/trial-2/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - migration_file: ✓ Using MIGRATION.md
  - markdown_headings: ✓ Has markdown headings
  - substantial_content: ✓ 1178 words (need ≥400)
  - code_blocks: ✓ 23 fenced code block(s) (need ≥3)
  - auth_header_change: ✓ Authorization: Bearer documented
  - uuid_id_change: ✓ UUID id change documented
  - field_rename: ✓ done→completed rename documented
  - project_id_and_v2_prefix: ✓ project_id + /v2/ prefix covered
  - checklist_or_upgrade: ✓ Checklist or upgrade command present

### deepseek:deepseek-v4-flash / copywriting / Trial 3

- **Status**: 👍 EXCELLENT
- **Duration**: 35.82s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/deepseek_deepseek-v4-flash/copywriting/trial-3/history/deepseek_deepseek-v4-flash-copywriting-trial-3.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/deepseek_deepseek-v4-flash/copywriting/trial-3/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - migration_file: ✓ Using MIGRATION.md
  - markdown_headings: ✓ Has markdown headings
  - substantial_content: ✓ 1037 words (need ≥400)
  - code_blocks: ✓ 19 fenced code block(s) (need ≥3)
  - auth_header_change: ✓ Authorization: Bearer documented
  - uuid_id_change: ✓ UUID id change documented
  - field_rename: ✓ done→completed rename documented
  - project_id_and_v2_prefix: ✓ project_id + /v2/ prefix covered
  - checklist_or_upgrade: ✓ Checklist or upgrade command present

### deepseek:deepseek-v4-flash / feature / Trial 1

- **Status**: 👍 EXCELLENT
- **Duration**: 65.53s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/deepseek_deepseek-v4-flash/feature/trial-1/history/deepseek_deepseek-v4-flash-feature-trial-1.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/deepseek_deepseek-v4-flash/feature/trial-1/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - get_projects: ✓ status=200
  - filter_by_status: ✓ status=200, n=1
  - filter_by_assigned_to: ✓ status=200
  - pagination: ✓ status=200, n=2
  - auth_required_on_post: ✓ status=401
  - post_creates_task: ✓ id=5
  - invalid_project_id_404: ✓ status=404
  - put_partial_update: ✓ status=200
  - delete_removes_task: ✓ delete=204, post-get=404

### deepseek:deepseek-v4-flash / feature / Trial 2

- **Status**: 👍 EXCELLENT
- **Duration**: 86.17s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/deepseek_deepseek-v4-flash/feature/trial-2/history/deepseek_deepseek-v4-flash-feature-trial-2.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/deepseek_deepseek-v4-flash/feature/trial-2/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - get_projects: ✓ status=200
  - filter_by_status: ✓ status=200, n=1
  - filter_by_assigned_to: ✓ status=200
  - pagination: ✓ status=200, n=2
  - auth_required_on_post: ✓ status=401
  - post_creates_task: ✓ id=5
  - invalid_project_id_404: ✓ status=404
  - put_partial_update: ✓ status=200
  - delete_removes_task: ✓ delete=204, post-get=404

### deepseek:deepseek-v4-flash / feature / Trial 3

- **Status**: 👍 EXCELLENT
- **Duration**: 83.93s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/deepseek_deepseek-v4-flash/feature/trial-3/history/deepseek_deepseek-v4-flash-feature-trial-3.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/deepseek_deepseek-v4-flash/feature/trial-3/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - get_projects: ✓ status=200
  - filter_by_status: ✓ status=200, n=1
  - filter_by_assigned_to: ✓ status=200
  - pagination: ✓ status=200, n=2
  - auth_required_on_post: ✓ status=401
  - post_creates_task: ✓ id=5
  - invalid_project_id_404: ✓ status=404
  - put_partial_update: ✓ status=200
  - delete_removes_task: ✓ delete=204, post-get=404

### deepseek:deepseek-v4-flash / integration-bug / Trial 1

- **Status**: 👍 EXCELLENT
- **Duration**: 106.61s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/deepseek_deepseek-v4-flash/integration-bug/trial-1/history/deepseek_deepseek-v4-flash-integration-bug-trial-1.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/deepseek_deepseek-v4-flash/integration-bug/trial-1/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - trial_1: ✓ stock=0, successful=5, charged=$500.00
  - trial_2: ✓ stock=2, successful=3, charged=$300.00
  - trial_3: ✓ stock=1, successful=4, charged=$400.00
  - trial_4: ✓ stock=2, successful=3, charged=$300.00
  - trial_5: ✓ stock=4, successful=1, charged=$100.00
  - trial_6: ✓ stock=0, successful=5, charged=$500.00
  - locking_mechanism: ✓ Lock detected in source

### deepseek:deepseek-v4-flash / integration-bug / Trial 2

- **Status**: ✅ PASS
- **Duration**: 104.12s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/deepseek_deepseek-v4-flash/integration-bug/trial-2/history/deepseek_deepseek-v4-flash-integration-bug-trial-2.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/deepseek_deepseek-v4-flash/integration-bug/trial-2/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 0.85
  - trial_1: ✓ stock=0, successful=5, charged=$500.00
  - trial_2: ✓ stock=2, successful=3, charged=$300.00
  - trial_3: ✓ stock=1, successful=4, charged=$400.00
  - trial_4: ✓ stock=2, successful=3, charged=$300.00
  - trial_5: ✓ stock=4, successful=1, charged=$100.00
  - trial_6: ✓ stock=0, successful=5, charged=$500.00
  - locking_mechanism: ✗ No Lock primitive detected

### deepseek:deepseek-v4-flash / integration-bug / Trial 3

- **Status**: 👍 EXCELLENT
- **Duration**: 72.58s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/deepseek_deepseek-v4-flash/integration-bug/trial-3/history/deepseek_deepseek-v4-flash-integration-bug-trial-3.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/deepseek_deepseek-v4-flash/integration-bug/trial-3/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - trial_1: ✓ stock=0, successful=5, charged=$500.00
  - trial_2: ✓ stock=2, successful=3, charged=$300.00
  - trial_3: ✓ stock=1, successful=4, charged=$400.00
  - trial_4: ✓ stock=2, successful=3, charged=$300.00
  - trial_5: ✓ stock=4, successful=1, charged=$100.00
  - trial_6: ✓ stock=0, successful=5, charged=$500.00
  - locking_mechanism: ✓ Lock detected in source

### deepseek:deepseek-v4-flash / refactor / Trial 1

- **Status**: 👍 EXCELLENT
- **Duration**: 45.59s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/deepseek_deepseek-v4-flash/refactor/trial-1/history/deepseek_deepseek-v4-flash-refactor-trial-1.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/deepseek_deepseek-v4-flash/refactor/trial-1/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - refactor_file: ✓ Checking pipeline_refactored.py
  - env_var_config: ✓ Env-var config present
  - no_hardcoded_credential: ✓ No hardcoded credential
  - sql_injection_check: ✓ SQL queries appear parameterized
  - etl_pattern: ✓ extract=True, transform=True, load=True
  - separation_of_concerns: ✓ 15 function(s), 5 class(es)
  - regex_parsing: ✓ Uses re module
  - type_hints_and_docstrings: ✓ types=True, docstrings=True
  - script_runs: ✓ Script exited 0
  - report_html: ✓ Sections present and source data preserved

### deepseek:deepseek-v4-flash / refactor / Trial 2

- **Status**: 👍 EXCELLENT
- **Duration**: 128.81s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/deepseek_deepseek-v4-flash/refactor/trial-2/history/deepseek_deepseek-v4-flash-refactor-trial-2.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/deepseek_deepseek-v4-flash/refactor/trial-2/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - refactor_file: ✓ Checking pipeline_refactored.py
  - env_var_config: ✓ Env-var config present
  - no_hardcoded_credential: ✓ No hardcoded credential
  - sql_injection_check: ✓ SQL queries appear parameterized
  - etl_pattern: ✓ extract=True, transform=True, load=True
  - separation_of_concerns: ✓ 15 function(s), 5 class(es)
  - regex_parsing: ✓ Uses re module
  - type_hints_and_docstrings: ✓ types=True, docstrings=True
  - script_runs: ✓ Script exited 0
  - report_html: ✓ Sections present and source data preserved

### deepseek:deepseek-v4-flash / refactor / Trial 3

- **Status**: 👍 EXCELLENT
- **Duration**: 141.00s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/deepseek_deepseek-v4-flash/refactor/trial-3/history/deepseek_deepseek-v4-flash-refactor-trial-3.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/deepseek_deepseek-v4-flash/refactor/trial-3/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - refactor_file: ✓ Checking pipeline_refactored.py
  - env_var_config: ✓ Env-var config present
  - no_hardcoded_credential: ✓ No hardcoded credential
  - sql_injection_check: ✓ SQL queries appear parameterized
  - etl_pattern: ✓ extract=True, transform=True, load=True
  - separation_of_concerns: ✓ 7 function(s), 0 class(es)
  - regex_parsing: ✓ Uses re module
  - type_hints_and_docstrings: ✓ types=True, docstrings=True
  - script_runs: ✓ Script exited 0
  - report_html: ✓ Sections present and source data preserved

### deepseek:deepseek-v4-flash / research / Trial 1

- **Status**: 👍 EXCELLENT
- **Duration**: 73.14s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/deepseek_deepseek-v4-flash/research/trial-1/history/deepseek_deepseek-v4-flash-research-trial-1.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/deepseek_deepseek-v4-flash/research/trial-1/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - adr_file: ✓ Using ADR-001-notification-architecture.md
  - substantial_content: ✓ 1941 words (need ≥500)
  - adr_sections: ✓ found=['context', 'decision', 'consequences', 'alternatives']
  - status_field: ✓ Status field present
  - evaluates_both_options: ✓ kafka=True, redis=True
  - clear_recommendation: ✓ Recommendation present
  - technical_properties: ✓ covered 11/12 (throughput, ordering, retention, consumer group...)
  - constraint_context: ✓ covered 6 constraint terms
  - pros_and_cons: ✓ pros=True, cons=True

### deepseek:deepseek-v4-flash / research / Trial 2

- **Status**: 👍 EXCELLENT
- **Duration**: 55.53s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/deepseek_deepseek-v4-flash/research/trial-2/history/deepseek_deepseek-v4-flash-research-trial-2.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/deepseek_deepseek-v4-flash/research/trial-2/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - adr_file: ✓ Using ADR-001-notification-architecture.md
  - substantial_content: ✓ 1537 words (need ≥500)
  - adr_sections: ✓ found=['context', 'decision', 'consequences', 'alternatives']
  - status_field: ✓ Status field present
  - evaluates_both_options: ✓ kafka=True, redis=True
  - clear_recommendation: ✓ Recommendation present
  - technical_properties: ✓ covered 9/12 (throughput, retention, consumer group, exactly-once...)
  - constraint_context: ✓ covered 7 constraint terms
  - pros_and_cons: ✓ pros=True, cons=True

### deepseek:deepseek-v4-flash / research / Trial 3

- **Status**: 👍 EXCELLENT
- **Duration**: 51.75s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/deepseek_deepseek-v4-flash/research/trial-3/history/deepseek_deepseek-v4-flash-research-trial-3.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/deepseek_deepseek-v4-flash/research/trial-3/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - adr_file: ✓ Using ADR-001-notification-architecture.md
  - substantial_content: ✓ 954 words (need ≥500)
  - adr_sections: ✓ found=['context', 'decision', 'consequences', 'alternatives']
  - status_field: ✓ Status field present
  - evaluates_both_options: ✓ kafka=True, redis=True
  - clear_recommendation: ✓ Recommendation present
  - technical_properties: ✓ covered 8/12 (throughput, retention, consumer group, exactly-once...)
  - constraint_context: ✓ covered 5 constraint terms
  - pros_and_cons: ✓ pros=True, cons=True

### google:gemini-2.5-flash / bug-fix / Trial 1

- **Status**: 👍 EXCELLENT
- **Duration**: 23.71s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-2.5-flash/bug-fix/trial-1/history/google_gemini-2.5-flash-bug-fix-trial-1.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-2.5-flash/bug-fix/trial-1/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - run_1: ✓ done=10, failed=2, stuck=0
  - run_2: ✓ done=10, failed=2, stuck=0
  - run_3: ✓ done=10, failed=2, stuck=0
  - run_4: ✓ done=10, failed=2, stuck=0
  - run_5: ✓ done=10, failed=2, stuck=0
  - concurrency_primitive: ✓ Lock found in source

### google:gemini-2.5-flash / bug-fix / Trial 2

- **Status**: ✅ PASS
- **Duration**: 23.26s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-2.5-flash/bug-fix/trial-2/history/google_gemini-2.5-flash-bug-fix-trial-2.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-2.5-flash/bug-fix/trial-2/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 0.85
  - run_1: ✓ done=10, failed=2, stuck=0
  - run_2: ✓ done=10, failed=2, stuck=0
  - run_3: ✓ done=10, failed=2, stuck=0
  - run_4: ✓ done=10, failed=2, stuck=0
  - run_5: ✓ done=10, failed=2, stuck=0
  - concurrency_primitive: ✗ No Lock primitive detected

### google:gemini-2.5-flash / bug-fix / Trial 3

- **Status**: 👍 EXCELLENT
- **Duration**: 43.84s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-2.5-flash/bug-fix/trial-3/history/google_gemini-2.5-flash-bug-fix-trial-3.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-2.5-flash/bug-fix/trial-3/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - run_1: ✓ done=10, failed=2, stuck=0
  - run_2: ✓ done=10, failed=2, stuck=0
  - run_3: ✓ done=10, failed=2, stuck=0
  - run_4: ✓ done=10, failed=2, stuck=0
  - run_5: ✓ done=10, failed=2, stuck=0
  - concurrency_primitive: ✓ Lock found in source

### google:gemini-2.5-flash / copywriting / Trial 1

- **Status**: 👍 EXCELLENT
- **Duration**: 22.58s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-2.5-flash/copywriting/trial-1/history/google_gemini-2.5-flash-copywriting-trial-1.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-2.5-flash/copywriting/trial-1/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - migration_file: ✓ Using MIGRATION.md
  - markdown_headings: ✓ Has markdown headings
  - substantial_content: ✓ 676 words (need ≥400)
  - code_blocks: ✓ 13 fenced code block(s) (need ≥3)
  - auth_header_change: ✓ Authorization: Bearer documented
  - uuid_id_change: ✓ UUID id change documented
  - field_rename: ✓ done→completed rename documented
  - project_id_and_v2_prefix: ✓ project_id + /v2/ prefix covered
  - checklist_or_upgrade: ✓ Checklist or upgrade command present

### google:gemini-2.5-flash / copywriting / Trial 2

- **Status**: 👍 EXCELLENT
- **Duration**: 13.78s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-2.5-flash/copywriting/trial-2/history/google_gemini-2.5-flash-copywriting-trial-2.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-2.5-flash/copywriting/trial-2/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - migration_file: ✓ Using MIGRATION.md
  - markdown_headings: ✓ Has markdown headings
  - substantial_content: ✓ 597 words (need ≥400)
  - code_blocks: ✓ 13 fenced code block(s) (need ≥3)
  - auth_header_change: ✓ Authorization: Bearer documented
  - uuid_id_change: ✓ UUID id change documented
  - field_rename: ✓ done→completed rename documented
  - project_id_and_v2_prefix: ✓ project_id + /v2/ prefix covered
  - checklist_or_upgrade: ✓ Checklist or upgrade command present

### google:gemini-2.5-flash / copywriting / Trial 3

- **Status**: 👍 EXCELLENT
- **Duration**: 17.48s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-2.5-flash/copywriting/trial-3/history/google_gemini-2.5-flash-copywriting-trial-3.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-2.5-flash/copywriting/trial-3/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - migration_file: ✓ Using MIGRATION.md
  - markdown_headings: ✓ Has markdown headings
  - substantial_content: ✓ 609 words (need ≥400)
  - code_blocks: ✓ 13 fenced code block(s) (need ≥3)
  - auth_header_change: ✓ Authorization: Bearer documented
  - uuid_id_change: ✓ UUID id change documented
  - field_rename: ✓ done→completed rename documented
  - project_id_and_v2_prefix: ✓ project_id + /v2/ prefix covered
  - checklist_or_upgrade: ✓ Checklist or upgrade command present

### google:gemini-2.5-flash / feature / Trial 1

- **Status**: 👍 EXCELLENT
- **Duration**: 25.02s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-2.5-flash/feature/trial-1/history/google_gemini-2.5-flash-feature-trial-1.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-2.5-flash/feature/trial-1/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - get_projects: ✓ status=200
  - filter_by_status: ✓ status=200, n=1
  - filter_by_assigned_to: ✓ status=200
  - pagination: ✓ status=200, n=2
  - auth_required_on_post: ✓ status=401
  - post_creates_task: ✓ id=5
  - invalid_project_id_404: ✓ status=404
  - put_partial_update: ✓ status=200
  - delete_removes_task: ✓ delete=204, post-get=404

### google:gemini-2.5-flash / feature / Trial 2

- **Status**: ❌ FAIL
- **Duration**: 25.46s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-2.5-flash/feature/trial-2/history/google_gemini-2.5-flash-feature-trial-2.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-2.5-flash/feature/trial-2/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 0.0
  - import: ✗ Traceback (most recent call last):
  File "<string>", line 7, in <module>
    from app.main import app
  File "/Users/gofrendigunawan/llm-challenges/experiment/google_gemini-2.5-flash/feature/trial-2/workdir/app/main.py", line 3, in <module>
    from .models import Task, TaskCreate, TaskUpdate, Project, TaskStatus, TaskPriority
ImportError: cannot import name 'TaskPriority' from 'app.models' (/Users/gofrendigunawan/llm-challenges/experiment/google_gemini-2.5-flash/feature/trial-2/workdir/app/mod

### google:gemini-2.5-flash / feature / Trial 3

- **Status**: 👍 EXCELLENT
- **Duration**: 16.38s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-2.5-flash/feature/trial-3/history/google_gemini-2.5-flash-feature-trial-3.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-2.5-flash/feature/trial-3/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 0.8888888888888888
  - get_projects: ✓ status=200
  - filter_by_status: ✓ status=200, n=1
  - filter_by_assigned_to: ✓ status=200
  - pagination: ✓ status=200, n=2
  - auth_required_on_post: ✓ status=401
  - post_creates_task: ✓ id=5
  - invalid_project_id_404: ✓ status=404
  - put_partial_update: ✓ status=200
  - delete_removes_task: ✗ delete=204, post-get=405

### google:gemini-2.5-flash / integration-bug / Trial 1

- **Status**: 👍 EXCELLENT
- **Duration**: 57.91s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-2.5-flash/integration-bug/trial-1/history/google_gemini-2.5-flash-integration-bug-trial-1.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-2.5-flash/integration-bug/trial-1/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - trial_1: ✓ stock=0, successful=5, charged=$500.00
  - trial_2: ✓ stock=2, successful=3, charged=$300.00
  - trial_3: ✓ stock=1, successful=4, charged=$400.00
  - trial_4: ✓ stock=2, successful=3, charged=$300.00
  - trial_5: ✓ stock=4, successful=1, charged=$100.00
  - trial_6: ✓ stock=0, successful=5, charged=$500.00
  - locking_mechanism: ✓ Lock detected in source

### google:gemini-2.5-flash / integration-bug / Trial 2

- **Status**: 👍 EXCELLENT
- **Duration**: 79.07s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-2.5-flash/integration-bug/trial-2/history/google_gemini-2.5-flash-integration-bug-trial-2.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-2.5-flash/integration-bug/trial-2/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - trial_1: ✓ stock=0, successful=5, charged=$500.00
  - trial_2: ✓ stock=2, successful=3, charged=$300.00
  - trial_3: ✓ stock=1, successful=4, charged=$400.00
  - trial_4: ✓ stock=2, successful=3, charged=$300.00
  - trial_5: ✓ stock=4, successful=1, charged=$100.00
  - trial_6: ✓ stock=0, successful=5, charged=$500.00
  - locking_mechanism: ✓ Lock detected in source

### google:gemini-2.5-flash / integration-bug / Trial 3

- **Status**: ✅ PASS
- **Duration**: 37.39s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-2.5-flash/integration-bug/trial-3/history/google_gemini-2.5-flash-integration-bug-trial-3.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-2.5-flash/integration-bug/trial-3/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 0.85
  - trial_1: ✓ stock=0, successful=5, charged=$500.00
  - trial_2: ✓ stock=2, successful=3, charged=$300.00
  - trial_3: ✓ stock=1, successful=4, charged=$400.00
  - trial_4: ✓ stock=2, successful=3, charged=$300.00
  - trial_5: ✓ stock=4, successful=1, charged=$100.00
  - trial_6: ✓ stock=0, successful=5, charged=$500.00
  - locking_mechanism: ✗ No Lock primitive detected

### google:gemini-2.5-flash / refactor / Trial 1

- **Status**: ❌ FAIL
- **Duration**: 102.37s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-2.5-flash/refactor/trial-1/history/google_gemini-2.5-flash-refactor-trial-1.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-2.5-flash/refactor/trial-1/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - refactor_file: ✓ Checking pipeline_refactored.py
  - env_var_config: ✓ Env-var config present
  - no_hardcoded_credential: ✗ Hardcoded 'password123' still present
  - sql_injection_check: ✓ SQL queries appear parameterized
  - etl_pattern: ✓ extract=True, transform=True, load=True
  - separation_of_concerns: ✓ 4 function(s), 0 class(es)
  - regex_parsing: ✓ Uses re module
  - type_hints_and_docstrings: ✓ types=True, docstrings=True
  - script_runs: ✓ Script exited 0
  - report_html: ✓ Sections present and source data preserved

### google:gemini-2.5-flash / refactor / Trial 2

- **Status**: ⏱️ TIMEOUT
- **Duration**: 600.03s
- **Exit code**: -1
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-2.5-flash/refactor/trial-2/history/google_gemini-2.5-flash-refactor-trial-2.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-2.5-flash/refactor/trial-2/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0

### google:gemini-2.5-flash / refactor / Trial 3

- **Status**: ❌ FAIL
- **Duration**: 170.74s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-2.5-flash/refactor/trial-3/history/google_gemini-2.5-flash-refactor-trial-3.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-2.5-flash/refactor/trial-3/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - refactor_file: ✓ Checking pipeline_refactored.py
  - env_var_config: ✓ Env-var config present
  - no_hardcoded_credential: ✗ Hardcoded 'password123' still present
  - sql_injection_check: ✓ SQL queries appear parameterized
  - etl_pattern: ✓ extract=True, transform=True, load=True
  - separation_of_concerns: ✓ 5 function(s), 0 class(es)
  - regex_parsing: ✓ Uses re module
  - type_hints_and_docstrings: ✓ types=True, docstrings=True
  - script_runs: ✓ Script exited 0
  - report_html: ✓ Sections present and source data preserved

### google:gemini-2.5-flash / research / Trial 1

- **Status**: 👍 EXCELLENT
- **Duration**: 26.02s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-2.5-flash/research/trial-1/history/google_gemini-2.5-flash-research-trial-1.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-2.5-flash/research/trial-1/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - adr_file: ✓ Using ADR-001-notification-architecture.md
  - substantial_content: ✓ 695 words (need ≥500)
  - adr_sections: ✓ found=['context', 'decision', 'consequences', 'alternatives']
  - status_field: ✓ Status field present
  - evaluates_both_options: ✓ kafka=True, redis=True
  - clear_recommendation: ✓ Recommendation present
  - technical_properties: ✓ covered 8/12 (throughput, ordering, retention, consumer group...)
  - constraint_context: ✓ covered 7 constraint terms
  - pros_and_cons: ✓ pros=True, cons=True

### google:gemini-2.5-flash / research / Trial 2

- **Status**: 👍 EXCELLENT
- **Duration**: 13.41s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-2.5-flash/research/trial-2/history/google_gemini-2.5-flash-research-trial-2.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-2.5-flash/research/trial-2/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - adr_file: ✓ Using ADR-001-notification-architecture.md
  - substantial_content: ✓ 708 words (need ≥500)
  - adr_sections: ✓ found=['context', 'decision', 'consequences', 'alternatives']
  - status_field: ✓ Status field present
  - evaluates_both_options: ✓ kafka=True, redis=True
  - clear_recommendation: ✓ Recommendation present
  - technical_properties: ✓ covered 9/12 (throughput, retention, consumer group, exactly-once...)
  - constraint_context: ✓ covered 7 constraint terms
  - pros_and_cons: ✓ pros=True, cons=True

### google:gemini-2.5-flash / research / Trial 3

- **Status**: 👍 EXCELLENT
- **Duration**: 21.60s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-2.5-flash/research/trial-3/history/google_gemini-2.5-flash-research-trial-3.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-2.5-flash/research/trial-3/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - adr_file: ✓ Using ADR-001-notification-architecture.md
  - substantial_content: ✓ 863 words (need ≥500)
  - adr_sections: ✓ found=['context', 'decision', 'consequences', 'alternatives']
  - status_field: ✓ Status field present
  - evaluates_both_options: ✓ kafka=True, redis=True
  - clear_recommendation: ✓ Recommendation present
  - technical_properties: ✓ covered 9/12 (throughput, retention, consumer group, exactly-once...)
  - constraint_context: ✓ covered 7 constraint terms
  - pros_and_cons: ✓ pros=True, cons=True

### google:gemini-3.5-flash / bug-fix / Trial 1

- **Status**: ⏱️ TIMEOUT
- **Duration**: 600.02s
- **Exit code**: -1
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-3.5-flash/bug-fix/trial-1/history/google_gemini-3.5-flash-bug-fix-trial-1.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-3.5-flash/bug-fix/trial-1/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0

### google:gemini-3.5-flash / bug-fix / Trial 2

- **Status**: ⏱️ TIMEOUT
- **Duration**: 600.02s
- **Exit code**: -1
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-3.5-flash/bug-fix/trial-2/history/google_gemini-3.5-flash-bug-fix-trial-2.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-3.5-flash/bug-fix/trial-2/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0

### google:gemini-3.5-flash / bug-fix / Trial 3

- **Status**: ⏱️ TIMEOUT
- **Duration**: 600.02s
- **Exit code**: -1
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-3.5-flash/bug-fix/trial-3/history/google_gemini-3.5-flash-bug-fix-trial-3.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-3.5-flash/bug-fix/trial-3/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0

### google:gemini-3.5-flash / copywriting / Trial 1

- **Status**: ⏱️ TIMEOUT
- **Duration**: 600.02s
- **Exit code**: -1
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-3.5-flash/copywriting/trial-1/history/google_gemini-3.5-flash-copywriting-trial-1.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-3.5-flash/copywriting/trial-1/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0

### google:gemini-3.5-flash / copywriting / Trial 2

- **Status**: ⏱️ TIMEOUT
- **Duration**: 600.03s
- **Exit code**: -1
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-3.5-flash/copywriting/trial-2/history/google_gemini-3.5-flash-copywriting-trial-2.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-3.5-flash/copywriting/trial-2/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0

### google:gemini-3.5-flash / copywriting / Trial 3

- **Status**: ⏱️ TIMEOUT
- **Duration**: 600.02s
- **Exit code**: -1
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-3.5-flash/copywriting/trial-3/history/google_gemini-3.5-flash-copywriting-trial-3.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-3.5-flash/copywriting/trial-3/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0

### google:gemini-3.5-flash / feature / Trial 1

- **Status**: ⏱️ TIMEOUT
- **Duration**: 600.02s
- **Exit code**: -1
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-3.5-flash/feature/trial-1/history/google_gemini-3.5-flash-feature-trial-1.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-3.5-flash/feature/trial-1/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0

### google:gemini-3.5-flash / feature / Trial 2

- **Status**: 👍 EXCELLENT
- **Duration**: 118.66s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-3.5-flash/feature/trial-2/history/google_gemini-3.5-flash-feature-trial-2.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-3.5-flash/feature/trial-2/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - get_projects: ✓ status=200
  - filter_by_status: ✓ status=200, n=1
  - filter_by_assigned_to: ✓ status=200
  - pagination: ✓ status=200, n=2
  - auth_required_on_post: ✓ status=401
  - post_creates_task: ✓ id=5
  - invalid_project_id_404: ✓ status=404
  - put_partial_update: ✓ status=200
  - delete_removes_task: ✓ delete=200, post-get=404

### google:gemini-3.5-flash / feature / Trial 3

- **Status**: 👍 EXCELLENT
- **Duration**: 151.40s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-3.5-flash/feature/trial-3/history/google_gemini-3.5-flash-feature-trial-3.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-3.5-flash/feature/trial-3/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - get_projects: ✓ status=200
  - filter_by_status: ✓ status=200, n=1
  - filter_by_assigned_to: ✓ status=200
  - pagination: ✓ status=200, n=2
  - auth_required_on_post: ✓ status=401
  - post_creates_task: ✓ id=5
  - invalid_project_id_404: ✓ status=404
  - put_partial_update: ✓ status=200
  - delete_removes_task: ✓ delete=204, post-get=404

### google:gemini-3.5-flash / integration-bug / Trial 1

- **Status**: ✅ PASS
- **Duration**: 133.22s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-3.5-flash/integration-bug/trial-1/history/google_gemini-3.5-flash-integration-bug-trial-1.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-3.5-flash/integration-bug/trial-1/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 0.85
  - trial_1: ✓ stock=0, successful=5, charged=$500.00
  - trial_2: ✓ stock=2, successful=3, charged=$300.00
  - trial_3: ✓ stock=1, successful=4, charged=$400.00
  - trial_4: ✓ stock=2, successful=3, charged=$300.00
  - trial_5: ✓ stock=4, successful=1, charged=$100.00
  - trial_6: ✓ stock=0, successful=5, charged=$500.00
  - locking_mechanism: ✗ No Lock primitive detected

### google:gemini-3.5-flash / integration-bug / Trial 2

- **Status**: 👍 EXCELLENT
- **Duration**: 108.41s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-3.5-flash/integration-bug/trial-2/history/google_gemini-3.5-flash-integration-bug-trial-2.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-3.5-flash/integration-bug/trial-2/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - trial_1: ✓ stock=0, successful=5, charged=$500.00
  - trial_2: ✓ stock=2, successful=3, charged=$300.00
  - trial_3: ✓ stock=1, successful=4, charged=$400.00
  - trial_4: ✓ stock=2, successful=3, charged=$300.00
  - trial_5: ✓ stock=4, successful=1, charged=$100.00
  - trial_6: ✓ stock=0, successful=5, charged=$500.00
  - locking_mechanism: ✓ Lock detected in source

### google:gemini-3.5-flash / integration-bug / Trial 3

- **Status**: 👍 EXCELLENT
- **Duration**: 168.60s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-3.5-flash/integration-bug/trial-3/history/google_gemini-3.5-flash-integration-bug-trial-3.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-3.5-flash/integration-bug/trial-3/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - trial_1: ✓ stock=0, successful=5, charged=$500.00
  - trial_2: ✓ stock=2, successful=3, charged=$300.00
  - trial_3: ✓ stock=1, successful=4, charged=$400.00
  - trial_4: ✓ stock=2, successful=3, charged=$300.00
  - trial_5: ✓ stock=4, successful=1, charged=$100.00
  - trial_6: ✓ stock=0, successful=5, charged=$500.00
  - locking_mechanism: ✓ Lock detected in source

### google:gemini-3.5-flash / refactor / Trial 1

- **Status**: ⏱️ TIMEOUT
- **Duration**: 600.02s
- **Exit code**: -1
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-3.5-flash/refactor/trial-1/history/google_gemini-3.5-flash-refactor-trial-1.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-3.5-flash/refactor/trial-1/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0

### google:gemini-3.5-flash / refactor / Trial 2

- **Status**: ⏱️ TIMEOUT
- **Duration**: 600.02s
- **Exit code**: -1
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-3.5-flash/refactor/trial-2/history/google_gemini-3.5-flash-refactor-trial-2.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-3.5-flash/refactor/trial-2/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0

### google:gemini-3.5-flash / refactor / Trial 3

- **Status**: ⏱️ TIMEOUT
- **Duration**: 600.02s
- **Exit code**: -1
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-3.5-flash/refactor/trial-3/history/google_gemini-3.5-flash-refactor-trial-3.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-3.5-flash/refactor/trial-3/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0

### google:gemini-3.5-flash / research / Trial 1

- **Status**: 👍 EXCELLENT
- **Duration**: 89.20s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-3.5-flash/research/trial-1/history/google_gemini-3.5-flash-research-trial-1.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-3.5-flash/research/trial-1/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - adr_file: ✓ Using ADR-001-notification-architecture.md
  - substantial_content: ✓ 1521 words (need ≥500)
  - adr_sections: ✓ found=['context', 'decision', 'consequences', 'alternatives']
  - status_field: ✓ Status field present
  - evaluates_both_options: ✓ kafka=True, redis=True
  - clear_recommendation: ✓ Recommendation present
  - technical_properties: ✓ covered 10/12 (throughput, ordering, retention, consumer group...)
  - constraint_context: ✓ covered 7 constraint terms
  - pros_and_cons: ✓ pros=True, cons=True

### google:gemini-3.5-flash / research / Trial 2

- **Status**: 👍 EXCELLENT
- **Duration**: 66.36s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-3.5-flash/research/trial-2/history/google_gemini-3.5-flash-research-trial-2.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-3.5-flash/research/trial-2/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - adr_file: ✓ Using ADR-001-notification-architecture.md
  - substantial_content: ✓ 1013 words (need ≥500)
  - adr_sections: ✓ found=['context', 'decision', 'consequences', 'alternatives']
  - status_field: ✓ Status field present
  - evaluates_both_options: ✓ kafka=True, redis=True
  - clear_recommendation: ✓ Recommendation present
  - technical_properties: ✓ covered 12/12 (throughput, ordering, retention, consumer group...)
  - constraint_context: ✓ covered 7 constraint terms
  - pros_and_cons: ✓ pros=True, cons=True

### google:gemini-3.5-flash / research / Trial 3

- **Status**: 👍 EXCELLENT
- **Duration**: 86.49s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-3.5-flash/research/trial-3/history/google_gemini-3.5-flash-research-trial-3.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/google_gemini-3.5-flash/research/trial-3/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - adr_file: ✓ Using ADR-001-notification-architecture.md
  - substantial_content: ✓ 1569 words (need ≥500)
  - adr_sections: ✓ found=['context', 'decision', 'consequences', 'alternatives']
  - status_field: ✓ Status field present
  - evaluates_both_options: ✓ kafka=True, redis=True
  - clear_recommendation: ✓ Recommendation present
  - technical_properties: ✓ covered 11/12 (throughput, ordering, retention, consumer group...)
  - constraint_context: ✓ covered 7 constraint terms
  - pros_and_cons: ✓ pros=True, cons=True

### ollama:gemma4:31b-cloud / bug-fix / Trial 1

- **Status**: ❌ FAIL
- **Duration**: 261.31s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/ollama_gemma4_31b-cloud/bug-fix/trial-1/history/ollama_gemma4_31b-cloud-bug-fix-trial-1.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/ollama_gemma4_31b-cloud/bug-fix/trial-1/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 0.0
  - run_1: ✗ done=10, failed=0, stuck=2
  - run_2: ✗ done=10, failed=0, stuck=2
  - run_3: ✗ done=10, failed=0, stuck=2
  - run_4: ✗ done=10, failed=0, stuck=2
  - run_5: ✗ done=10, failed=0, stuck=2
  - concurrency_primitive: ✗ No Lock primitive detected

### ollama:gemma4:31b-cloud / bug-fix / Trial 2

- **Status**: ✅ PASS
- **Duration**: 67.23s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/ollama_gemma4_31b-cloud/bug-fix/trial-2/history/ollama_gemma4_31b-cloud-bug-fix-trial-2.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/ollama_gemma4_31b-cloud/bug-fix/trial-2/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 0.85
  - run_1: ✓ done=10, failed=2, stuck=0
  - run_2: ✓ done=10, failed=2, stuck=0
  - run_3: ✓ done=10, failed=2, stuck=0
  - run_4: ✓ done=10, failed=2, stuck=0
  - run_5: ✓ done=10, failed=2, stuck=0
  - concurrency_primitive: ✗ No Lock primitive detected

### ollama:gemma4:31b-cloud / bug-fix / Trial 3

- **Status**: 👍 EXCELLENT
- **Duration**: 54.79s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/ollama_gemma4_31b-cloud/bug-fix/trial-3/history/ollama_gemma4_31b-cloud-bug-fix-trial-3.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/ollama_gemma4_31b-cloud/bug-fix/trial-3/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - run_1: ✓ done=10, failed=2, stuck=0
  - run_2: ✓ done=10, failed=2, stuck=0
  - run_3: ✓ done=10, failed=2, stuck=0
  - run_4: ✓ done=10, failed=2, stuck=0
  - run_5: ✓ done=10, failed=2, stuck=0
  - concurrency_primitive: ✓ Lock found in source

### ollama:gemma4:31b-cloud / copywriting / Trial 1

- **Status**: 👍 EXCELLENT
- **Duration**: 20.99s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/ollama_gemma4_31b-cloud/copywriting/trial-1/history/ollama_gemma4_31b-cloud-copywriting-trial-1.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/ollama_gemma4_31b-cloud/copywriting/trial-1/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 0.875
  - migration_file: ✓ Using MIGRATION.md
  - markdown_headings: ✓ Has markdown headings
  - substantial_content: ✗ 378 words (need ≥400)
  - code_blocks: ✓ 11 fenced code block(s) (need ≥3)
  - auth_header_change: ✓ Authorization: Bearer documented
  - uuid_id_change: ✓ UUID id change documented
  - field_rename: ✓ done→completed rename documented
  - project_id_and_v2_prefix: ✓ project_id + /v2/ prefix covered
  - checklist_or_upgrade: ✓ Checklist or upgrade command present

### ollama:gemma4:31b-cloud / copywriting / Trial 2

- **Status**: 👍 EXCELLENT
- **Duration**: 218.43s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/ollama_gemma4_31b-cloud/copywriting/trial-2/history/ollama_gemma4_31b-cloud-copywriting-trial-2.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/ollama_gemma4_31b-cloud/copywriting/trial-2/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 0.875
  - migration_file: ✓ Using MIGRATION.md
  - markdown_headings: ✓ Has markdown headings
  - substantial_content: ✗ 399 words (need ≥400)
  - code_blocks: ✓ 11 fenced code block(s) (need ≥3)
  - auth_header_change: ✓ Authorization: Bearer documented
  - uuid_id_change: ✓ UUID id change documented
  - field_rename: ✓ done→completed rename documented
  - project_id_and_v2_prefix: ✓ project_id + /v2/ prefix covered
  - checklist_or_upgrade: ✓ Checklist or upgrade command present

### ollama:gemma4:31b-cloud / copywriting / Trial 3

- **Status**: 👍 EXCELLENT
- **Duration**: 29.63s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/ollama_gemma4_31b-cloud/copywriting/trial-3/history/ollama_gemma4_31b-cloud-copywriting-trial-3.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/ollama_gemma4_31b-cloud/copywriting/trial-3/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - migration_file: ✓ Using MIGRATION.md
  - markdown_headings: ✓ Has markdown headings
  - substantial_content: ✓ 417 words (need ≥400)
  - code_blocks: ✓ 11 fenced code block(s) (need ≥3)
  - auth_header_change: ✓ Authorization: Bearer documented
  - uuid_id_change: ✓ UUID id change documented
  - field_rename: ✓ done→completed rename documented
  - project_id_and_v2_prefix: ✓ project_id + /v2/ prefix covered
  - checklist_or_upgrade: ✓ Checklist or upgrade command present

### ollama:gemma4:31b-cloud / feature / Trial 1

- **Status**: 👍 EXCELLENT
- **Duration**: 252.75s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/ollama_gemma4_31b-cloud/feature/trial-1/history/ollama_gemma4_31b-cloud-feature-trial-1.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/ollama_gemma4_31b-cloud/feature/trial-1/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - get_projects: ✓ status=200
  - filter_by_status: ✓ status=200, n=1
  - filter_by_assigned_to: ✓ status=200
  - pagination: ✓ status=200, n=2
  - auth_required_on_post: ✓ status=401
  - post_creates_task: ✓ id=5
  - invalid_project_id_404: ✓ status=404
  - put_partial_update: ✓ status=200
  - delete_removes_task: ✓ delete=200, post-get=404

### ollama:gemma4:31b-cloud / feature / Trial 2

- **Status**: ❌ FAIL
- **Duration**: 245.59s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/ollama_gemma4_31b-cloud/feature/trial-2/history/ollama_gemma4_31b-cloud-feature-trial-2.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/ollama_gemma4_31b-cloud/feature/trial-2/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 0.0
  - import: ✗ Traceback (most recent call last):
  File "<string>", line 7, in <module>
    from app.main import app
  File "/Users/gofrendigunawan/llm-challenges/experiment/ollama_gemma4_31b-cloud/feature/trial-2/workdir/app/main.py", line 17, in <module>
    status: Optional[TaskStatus] = None,
                     ^^^^^^^^^^
NameError: name 'TaskStatus' is not defined


### ollama:gemma4:31b-cloud / feature / Trial 3

- **Status**: 👍 EXCELLENT
- **Duration**: 222.26s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/ollama_gemma4_31b-cloud/feature/trial-3/history/ollama_gemma4_31b-cloud-feature-trial-3.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/ollama_gemma4_31b-cloud/feature/trial-3/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - get_projects: ✓ status=200
  - filter_by_status: ✓ status=200, n=1
  - filter_by_assigned_to: ✓ status=200
  - pagination: ✓ status=200, n=2
  - auth_required_on_post: ✓ status=401
  - post_creates_task: ✓ id=5
  - invalid_project_id_404: ✓ status=404
  - put_partial_update: ✓ status=200
  - delete_removes_task: ✓ delete=200, post-get=404

### ollama:gemma4:31b-cloud / integration-bug / Trial 1

- **Status**: ⏱️ TIMEOUT
- **Duration**: 600.03s
- **Exit code**: -1
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/ollama_gemma4_31b-cloud/integration-bug/trial-1/history/ollama_gemma4_31b-cloud-integration-bug-trial-1.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/ollama_gemma4_31b-cloud/integration-bug/trial-1/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0

### ollama:gemma4:31b-cloud / integration-bug / Trial 2

- **Status**: 👍 EXCELLENT
- **Duration**: 119.77s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/ollama_gemma4_31b-cloud/integration-bug/trial-2/history/ollama_gemma4_31b-cloud-integration-bug-trial-2.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/ollama_gemma4_31b-cloud/integration-bug/trial-2/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - trial_1: ✓ stock=0, successful=5, charged=$500.00
  - trial_2: ✓ stock=2, successful=3, charged=$300.00
  - trial_3: ✓ stock=1, successful=4, charged=$400.00
  - trial_4: ✓ stock=2, successful=3, charged=$300.00
  - trial_5: ✓ stock=4, successful=1, charged=$100.00
  - trial_6: ✓ stock=0, successful=5, charged=$500.00
  - locking_mechanism: ✓ Lock detected in source

### ollama:gemma4:31b-cloud / integration-bug / Trial 3

- **Status**: ❌ FAIL
- **Duration**: 86.62s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/ollama_gemma4_31b-cloud/integration-bug/trial-3/history/ollama_gemma4_31b-cloud-integration-bug-trial-3.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/ollama_gemma4_31b-cloud/integration-bug/trial-3/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 0.16666666666666666
  - trial_1: ✗ charge mismatch (charged=1200.00, expected=500.00)
  - trial_2: ✗ charge mismatch (charged=600.00, expected=500.00)
  - trial_3: ✗ charge mismatch (charged=1100.00, expected=500.00)
  - trial_4: ✗ charge mismatch (charged=800.00, expected=500.00)
  - trial_5: ✓ stock=0, successful=5, charged=$500.00
  - trial_6: ✗ charge mismatch (charged=1200.00, expected=500.00)
  - locking_mechanism: ✗ No Lock primitive detected

### ollama:gemma4:31b-cloud / refactor / Trial 1

- **Status**: ❌ FAIL
- **Duration**: 131.11s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/ollama_gemma4_31b-cloud/refactor/trial-1/history/ollama_gemma4_31b-cloud-refactor-trial-1.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/ollama_gemma4_31b-cloud/refactor/trial-1/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - refactor_file: ✓ Checking pipeline_refactored.py
  - env_var_config: ✓ Env-var config present
  - no_hardcoded_credential: ✗ Hardcoded 'password123' still present
  - sql_injection_check: ✓ SQL queries appear parameterized
  - etl_pattern: ✓ extract=True, transform=True, load=True
  - separation_of_concerns: ✓ 5 function(s), 1 class(es)
  - regex_parsing: ✓ Uses re module
  - type_hints_and_docstrings: ✓ types=True, docstrings=True
  - script_runs: ✓ Script exited 0
  - report_html: ✓ Sections present and source data preserved

### ollama:gemma4:31b-cloud / refactor / Trial 2

- **Status**: ❌ FAIL
- **Duration**: 183.46s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/ollama_gemma4_31b-cloud/refactor/trial-2/history/ollama_gemma4_31b-cloud-refactor-trial-2.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/ollama_gemma4_31b-cloud/refactor/trial-2/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - refactor_file: ✓ Checking pipeline_refactored.py
  - env_var_config: ✓ Env-var config present
  - no_hardcoded_credential: ✗ Hardcoded 'password123' still present
  - sql_injection_check: ✓ SQL queries appear parameterized
  - etl_pattern: ✓ extract=True, transform=True, load=True
  - separation_of_concerns: ✓ 5 function(s), 1 class(es)
  - regex_parsing: ✓ Uses re module
  - type_hints_and_docstrings: ✓ types=True, docstrings=True
  - script_runs: ✓ Script exited 0
  - report_html: ✓ Sections present and source data preserved

### ollama:gemma4:31b-cloud / refactor / Trial 3

- **Status**: ❌ FAIL
- **Duration**: 115.13s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/ollama_gemma4_31b-cloud/refactor/trial-3/history/ollama_gemma4_31b-cloud-refactor-trial-3.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/ollama_gemma4_31b-cloud/refactor/trial-3/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - refactor_file: ✓ Checking pipeline_refactored.py
  - env_var_config: ✓ Env-var config present
  - no_hardcoded_credential: ✗ Hardcoded 'password123' still present
  - sql_injection_check: ✓ SQL queries appear parameterized
  - etl_pattern: ✓ extract=True, transform=True, load=True
  - separation_of_concerns: ✓ 5 function(s), 1 class(es)
  - regex_parsing: ✓ Uses re module
  - type_hints_and_docstrings: ✓ types=True, docstrings=True
  - script_runs: ✓ Script exited 0
  - report_html: ✓ Sections present and source data preserved

### ollama:gemma4:31b-cloud / research / Trial 1

- **Status**: 👍 EXCELLENT
- **Duration**: 52.94s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/ollama_gemma4_31b-cloud/research/trial-1/history/ollama_gemma4_31b-cloud-research-trial-1.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/ollama_gemma4_31b-cloud/research/trial-1/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 0.875
  - adr_file: ✓ Using ADR-001-notification-architecture.md
  - substantial_content: ✗ 451 words (need ≥500)
  - adr_sections: ✓ found=['context', 'decision', 'consequences', 'alternatives']
  - status_field: ✓ Status field present
  - evaluates_both_options: ✓ kafka=True, redis=True
  - clear_recommendation: ✓ Recommendation present
  - technical_properties: ✓ covered 10/12 (throughput, retention, consumer group, exactly-once...)
  - constraint_context: ✓ covered 7 constraint terms
  - pros_and_cons: ✓ pros=True, cons=True

### ollama:gemma4:31b-cloud / research / Trial 2

- **Status**: 👍 EXCELLENT
- **Duration**: 42.75s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/ollama_gemma4_31b-cloud/research/trial-2/history/ollama_gemma4_31b-cloud-research-trial-2.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/ollama_gemma4_31b-cloud/research/trial-2/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - adr_file: ✓ Using ADR-001-notification-architecture.md
  - substantial_content: ✓ 561 words (need ≥500)
  - adr_sections: ✓ found=['context', 'decision', 'consequences', 'alternatives']
  - status_field: ✓ Status field present
  - evaluates_both_options: ✓ kafka=True, redis=True
  - clear_recommendation: ✓ Recommendation present
  - technical_properties: ✓ covered 10/12 (throughput, retention, consumer group, exactly-once...)
  - constraint_context: ✓ covered 5 constraint terms
  - pros_and_cons: ✓ pros=True, cons=True

### ollama:gemma4:31b-cloud / research / Trial 3

- **Status**: 👍 EXCELLENT
- **Duration**: 45.25s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/ollama_gemma4_31b-cloud/research/trial-3/history/ollama_gemma4_31b-cloud-research-trial-3.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/ollama_gemma4_31b-cloud/research/trial-3/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - adr_file: ✓ Using ADR-001-notification-architecture.md
  - substantial_content: ✓ 531 words (need ≥500)
  - adr_sections: ✓ found=['context', 'decision', 'consequences', 'alternatives']
  - status_field: ✓ Status field present
  - evaluates_both_options: ✓ kafka=True, redis=True
  - clear_recommendation: ✓ Recommendation present
  - technical_properties: ✓ covered 9/12 (throughput, retention, consumer group, exactly-once...)
  - constraint_context: ✓ covered 6 constraint terms
  - pros_and_cons: ✓ pros=True, cons=True

### openai:gpt-4o / bug-fix / Trial 1

- **Status**: ✅ PASS
- **Duration**: 26.73s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/openai_gpt-4o/bug-fix/trial-1/history/openai_gpt-4o-bug-fix-trial-1.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/openai_gpt-4o/bug-fix/trial-1/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 0.85
  - run_1: ✓ done=10, failed=2, stuck=0
  - run_2: ✓ done=10, failed=2, stuck=0
  - run_3: ✓ done=10, failed=2, stuck=0
  - run_4: ✓ done=10, failed=2, stuck=0
  - run_5: ✓ done=10, failed=2, stuck=0
  - concurrency_primitive: ✗ No Lock primitive detected

### openai:gpt-4o / bug-fix / Trial 2

- **Status**: ✅ PASS
- **Duration**: 24.60s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/openai_gpt-4o/bug-fix/trial-2/history/openai_gpt-4o-bug-fix-trial-2.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/openai_gpt-4o/bug-fix/trial-2/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 0.85
  - run_1: ✓ done=10, failed=2, stuck=0
  - run_2: ✓ done=10, failed=2, stuck=0
  - run_3: ✓ done=10, failed=2, stuck=0
  - run_4: ✓ done=10, failed=2, stuck=0
  - run_5: ✓ done=10, failed=2, stuck=0
  - concurrency_primitive: ✗ No Lock primitive detected

### openai:gpt-4o / bug-fix / Trial 3

- **Status**: ✅ PASS
- **Duration**: 28.39s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/openai_gpt-4o/bug-fix/trial-3/history/openai_gpt-4o-bug-fix-trial-3.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/openai_gpt-4o/bug-fix/trial-3/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 0.85
  - run_1: ✓ done=10, failed=2, stuck=0
  - run_2: ✓ done=10, failed=2, stuck=0
  - run_3: ✓ done=10, failed=2, stuck=0
  - run_4: ✓ done=10, failed=2, stuck=0
  - run_5: ✓ done=10, failed=2, stuck=0
  - concurrency_primitive: ✗ No Lock primitive detected

### openai:gpt-4o / copywriting / Trial 1

- **Status**: ❌ FAIL
- **Duration**: 21.12s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/openai_gpt-4o/copywriting/trial-1/history/openai_gpt-4o-copywriting-trial-1.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/openai_gpt-4o/copywriting/trial-1/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 0.0
  - migration_file: ✗ MIGRATION.md not found

### openai:gpt-4o / copywriting / Trial 2

- **Status**: 👍 EXCELLENT
- **Duration**: 26.30s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/openai_gpt-4o/copywriting/trial-2/history/openai_gpt-4o-copywriting-trial-2.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/openai_gpt-4o/copywriting/trial-2/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 0.875
  - migration_file: ✓ Using MIGRATION.md
  - markdown_headings: ✓ Has markdown headings
  - substantial_content: ✗ 375 words (need ≥400)
  - code_blocks: ✓ 13 fenced code block(s) (need ≥3)
  - auth_header_change: ✓ Authorization: Bearer documented
  - uuid_id_change: ✓ UUID id change documented
  - field_rename: ✓ done→completed rename documented
  - project_id_and_v2_prefix: ✓ project_id + /v2/ prefix covered
  - checklist_or_upgrade: ✓ Checklist or upgrade command present

### openai:gpt-4o / copywriting / Trial 3

- **Status**: 👍 EXCELLENT
- **Duration**: 26.65s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/openai_gpt-4o/copywriting/trial-3/history/openai_gpt-4o-copywriting-trial-3.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/openai_gpt-4o/copywriting/trial-3/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 0.875
  - migration_file: ✓ Using MIGRATION.md
  - markdown_headings: ✓ Has markdown headings
  - substantial_content: ✗ 341 words (need ≥400)
  - code_blocks: ✓ 13 fenced code block(s) (need ≥3)
  - auth_header_change: ✓ Authorization: Bearer documented
  - uuid_id_change: ✓ UUID id change documented
  - field_rename: ✓ done→completed rename documented
  - project_id_and_v2_prefix: ✓ project_id + /v2/ prefix covered
  - checklist_or_upgrade: ✓ Checklist or upgrade command present

### openai:gpt-4o / feature / Trial 1

- **Status**: ❌ FAIL
- **Duration**: 45.01s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/openai_gpt-4o/feature/trial-1/history/openai_gpt-4o-feature-trial-1.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/openai_gpt-4o/feature/trial-1/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 0.0
  - import: ✗ Traceback (most recent call last):
  File "<string>", line 7, in <module>
    from app.main import app
  File "/Users/gofrendigunawan/llm-challenges/experiment/openai_gpt-4o/feature/trial-1/workdir/app/main.py", line 35, in <module>
    @app.post("/tasks", response_model=Task, dependencies=[require_api_key])
     ~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/gofrendigunawan/.local-venv/lib/python3.13/site-packages/fastapi/routing.py", line 1072, in decora

### openai:gpt-4o / feature / Trial 2

- **Status**: ❌ FAIL
- **Duration**: 45.97s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/openai_gpt-4o/feature/trial-2/history/openai_gpt-4o-feature-trial-2.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/openai_gpt-4o/feature/trial-2/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 0.0
  - import: ✗ Traceback (most recent call last):
  File "<string>", line 7, in <module>
    from app.main import app
  File "/Users/gofrendigunawan/llm-challenges/experiment/openai_gpt-4o/feature/trial-2/workdir/app/main.py", line 16, in <module>
    async def list_tasks(status: Optional[str] = None, priority: Optional[str] = None, assigned_to: Optional[str] = None, page: int = 1, page_size: int = 20):
                                 ^^^^^^^^
NameError: name 'Optional' is not defined


### openai:gpt-4o / feature / Trial 3

- **Status**: ✅ PASS
- **Duration**: 39.29s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/openai_gpt-4o/feature/trial-3/history/openai_gpt-4o-feature-trial-3.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/openai_gpt-4o/feature/trial-3/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 0.6666666666666666
  - get_projects: ✓ status=200
  - filter_by_status: ✗ status=500, n=0
  - filter_by_assigned_to: ✗ status=500
  - pagination: ✗ status=500, n=0
  - auth_required_on_post: ✓ status=401
  - post_creates_task: ✓ id=5
  - invalid_project_id_404: ✓ status=404
  - put_partial_update: ✓ status=200
  - delete_removes_task: ✓ delete=200, post-get=404

### openai:gpt-4o / integration-bug / Trial 1

- **Status**: ✅ PASS
- **Duration**: 23.37s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/openai_gpt-4o/integration-bug/trial-1/history/openai_gpt-4o-integration-bug-trial-1.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/openai_gpt-4o/integration-bug/trial-1/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 0.85
  - trial_1: ✓ stock=0, successful=5, charged=$500.00
  - trial_2: ✓ stock=2, successful=3, charged=$300.00
  - trial_3: ✓ stock=1, successful=4, charged=$400.00
  - trial_4: ✓ stock=2, successful=3, charged=$300.00
  - trial_5: ✓ stock=4, successful=1, charged=$100.00
  - trial_6: ✓ stock=0, successful=5, charged=$500.00
  - locking_mechanism: ✗ No Lock primitive detected

### openai:gpt-4o / integration-bug / Trial 2

- **Status**: ✅ PASS
- **Duration**: 28.81s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/openai_gpt-4o/integration-bug/trial-2/history/openai_gpt-4o-integration-bug-trial-2.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/openai_gpt-4o/integration-bug/trial-2/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 0.85
  - trial_1: ✓ stock=0, successful=5, charged=$500.00
  - trial_2: ✓ stock=2, successful=3, charged=$300.00
  - trial_3: ✓ stock=1, successful=4, charged=$400.00
  - trial_4: ✓ stock=2, successful=3, charged=$300.00
  - trial_5: ✓ stock=4, successful=1, charged=$100.00
  - trial_6: ✓ stock=0, successful=5, charged=$500.00
  - locking_mechanism: ✗ No Lock primitive detected

### openai:gpt-4o / integration-bug / Trial 3

- **Status**: 👍 EXCELLENT
- **Duration**: 48.05s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/openai_gpt-4o/integration-bug/trial-3/history/openai_gpt-4o-integration-bug-trial-3.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/openai_gpt-4o/integration-bug/trial-3/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - trial_1: ✓ stock=0, successful=5, charged=$500.00
  - trial_2: ✓ stock=0, successful=5, charged=$500.00
  - trial_3: ✓ stock=0, successful=5, charged=$500.00
  - trial_4: ✓ stock=0, successful=5, charged=$500.00
  - trial_5: ✓ stock=0, successful=5, charged=$500.00
  - trial_6: ✓ stock=0, successful=5, charged=$500.00
  - locking_mechanism: ✓ Lock detected in source

### openai:gpt-4o / refactor / Trial 1

- **Status**: 👍 EXCELLENT
- **Duration**: 34.96s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/openai_gpt-4o/refactor/trial-1/history/openai_gpt-4o-refactor-trial-1.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/openai_gpt-4o/refactor/trial-1/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 1.0
  - refactor_file: ✓ Checking pipeline_refactored.py
  - env_var_config: ✓ Env-var config present
  - no_hardcoded_credential: ✓ No hardcoded credential
  - sql_injection_check: ✓ SQL queries appear parameterized
  - etl_pattern: ✓ extract=True, transform=True, load=True
  - separation_of_concerns: ✓ 0 function(s), 1 class(es)
  - regex_parsing: ✓ Uses re module
  - type_hints_and_docstrings: ✓ types=True, docstrings=True
  - script_runs: ✓ Script exited 0
  - report_html: ✓ Sections present and source data preserved

### openai:gpt-4o / refactor / Trial 2

- **Status**: ❌ FAIL
- **Duration**: 23.89s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/openai_gpt-4o/refactor/trial-2/history/openai_gpt-4o-refactor-trial-2.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/openai_gpt-4o/refactor/trial-2/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 0.875
  - refactor_file: ✓ Checking pipeline_refactored.py
  - env_var_config: ✓ Env-var config present
  - no_hardcoded_credential: ✗ Hardcoded 'password123' still present
  - sql_injection_check: ✓ SQL queries appear parameterized
  - etl_pattern: ✗ extract=False, transform=True, load=True
  - separation_of_concerns: ✓ 6 function(s), 0 class(es)
  - regex_parsing: ✓ Uses re module
  - type_hints_and_docstrings: ✓ types=True, docstrings=True
  - script_runs: ✓ Script exited 0
  - report_html: ✓ Sections present and source data preserved

### openai:gpt-4o / refactor / Trial 3

- **Status**: ❌ FAIL
- **Duration**: 77.92s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/openai_gpt-4o/refactor/trial-3/history/openai_gpt-4o-refactor-trial-3.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/openai_gpt-4o/refactor/trial-3/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 0.75
  - refactor_file: ✓ Checking pipeline.py
  - env_var_config: ✓ Env-var config present
  - no_hardcoded_credential: ✗ Hardcoded 'password123' still present
  - sql_injection_check: ✓ SQL queries appear parameterized
  - etl_pattern: ✓ extract=True, transform=True, load=True
  - separation_of_concerns: ✓ 5 function(s), 0 class(es)
  - regex_parsing: ✓ Uses re module
  - type_hints_and_docstrings: ✓ types=True, docstrings=True
  - script_runs: ✗ exit=1: Traceback (most recent call last):
  File "/Users/gofrendigunawan/llm-challenges/experiment/openai_gpt-4o/refactor/trial-3/workdir/pipeline.py", line 136, in <module>
    proc_data()
    ^^^^^^^^^
NameError: name 'proc_data' is not defined

  - report_html: ✗ report.html not generated

### openai:gpt-4o / research / Trial 1

- **Status**: 👍 EXCELLENT
- **Duration**: 16.41s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/openai_gpt-4o/research/trial-1/history/openai_gpt-4o-research-trial-1.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/openai_gpt-4o/research/trial-1/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 0.875
  - adr_file: ✓ Using ADR-001-notification-architecture.md
  - substantial_content: ✗ 326 words (need ≥500)
  - adr_sections: ✓ found=['context', 'decision', 'consequences', 'alternatives']
  - status_field: ✓ Status field present
  - evaluates_both_options: ✓ kafka=True, redis=True
  - clear_recommendation: ✓ Recommendation present
  - technical_properties: ✓ covered 5/12 (exactly-once, at-least-once, operational, stream...)
  - constraint_context: ✓ covered 5 constraint terms
  - pros_and_cons: ✓ pros=True, cons=True

### openai:gpt-4o / research / Trial 2

- **Status**: ❌ FAIL
- **Duration**: 11.04s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/openai_gpt-4o/research/trial-2/history/openai_gpt-4o-research-trial-2.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/openai_gpt-4o/research/trial-2/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 0.0
  - adr_file: ✗ No ADR markdown file found

### openai:gpt-4o / research / Trial 3

- **Status**: ❌ FAIL
- **Duration**: 14.10s
- **Exit code**: 0
- **History path**: /Users/gofrendigunawan/llm-challenges/experiment/openai_gpt-4o/research/trial-3/history/openai_gpt-4o-research-trial-3.json
- **Stdout log path**: /Users/gofrendigunawan/llm-challenges/experiment/openai_gpt-4o/research/trial-3/stdout.log
- **Tokens**: total=0, input=0, output=0, cache=0
- **Validation score**: 0.0
  - adr_file: ✗ No ADR markdown file found

