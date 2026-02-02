# Research Questions

> Research questions for the LLM Performance Evaluation paper

---

## Primary Research Questions

### RQ1: Overall Performance Ranking
**Question:** How do current state-of-the-art LLMs perform across diverse software engineering tasks?

**Motivation:** Practitioners need to know which models are most capable for general SE work.

**Metrics:**
- Total score (sum of task scores)
- Success rate (percentage of tasks completed)
- Excellent rate (percentage achieving highest grade)

**Expected Findings:**
- Top-tier models (GPT-5.x, Gemini-3 Pro) score perfectly
- Performance varies significantly by model family
- API models generally outperform open models

---

### RQ2: Task-Specific Strengths and Weaknesses
**Question:** Which models excel at specific types of software engineering tasks?

**Motivation:** Different SE activities require different capabilities (coding vs writing vs analysis).

**Analysis Dimensions:**
| Task | Key Capability | Success Criteria |
|------|----------------|------------------|
| Bug-fix | Debugging, concurrency | Correct fix, race condition resolved |
| Feature | API development, CRUD | All endpoints functional |
| Refactor | Code quality, patterns | Maintainability improvements |
| Copywriting | Technical communication | Content coverage, engagement |
| Research | Information synthesis | Coverage, accuracy, citations |

**Hypotheses:**
- H2.1: Coding-focused models excel at bug-fix and feature
- H2.2: Larger context models perform better at research
- H2.3: Speed-optimized models may sacrifice quality

---

### RQ3: Tool Usage Patterns vs Performance
**Question:** What is the relationship between tool usage frequency and task success?

**Motivation:** Understanding whether "thinking longer" (more tool calls) leads to better results.

**Metrics:**
- Tool call count per task
- Tool diversity (number of unique tools)
- Correlation with success score

**Analysis:**
```
Pearson correlation: tool_count vs success_score
Comparison: High-tool vs Low-tool approaches
Case study: Gemini-3 Flash (917 tools) vs GPT-5.1 (3 tools) on bug-fix
```

**Expected Findings:**
- Diminishing returns after certain tool count
- Efficient models achieve results with fewer calls
- Task complexity affects optimal tool usage

---

### RQ4: Time-Efficiency Tradeoffs
**Question:** How does completion time correlate with output quality?

**Motivation:** Practical deployment requires balancing speed and accuracy.

**Metrics:**
- Completion time per task
- Time-to-quality ratio
- Cost-effectiveness (time × API cost)

**Key Comparisons:**
| Model | Bug-fix Time | Quality | Efficiency Score |
|-------|-------------|---------|------------------|
| GPT-5.1 | 18.76s | Excellent | Very High |
| Gemini-2.5 Flash | 20.70s | Excellent | Very High |
| Deepseek | 378.21s | Excellent | Moderate |

**Hypothesis:**
- H4.1: No strong correlation between time and quality
- H4.2: Model architecture matters more than inference time

---

### RQ5: Cost-Performance Tradeoffs
**Question:** What are the cost-performance tradeoffs across model tiers?

**Motivation:** Organizations need to optimize budget allocation for LLM usage.

**Cost Model:**
```
Estimated Cost = (Input Tokens × Input Price) + (Output Tokens × Output Price)
Performance per Dollar = Success Score / Estimated Cost
```

**Categories:**
- **Budget Tier:** Gemini Flash, GPT-4o
- **Mid Tier:** GPT-5.1, Gemini Pro
- **Premium Tier:** GPT-5.2, Gemini-3 Pro

**Expected Findings:**
- Best value in mid-tier models
- Diminishing returns in premium tier
- Open models offer cost advantage

---

## Secondary Research Questions

### RQ6: Consistency Analysis
**Question:** How consistent are models across repeated task attempts?

**Note:** Current data has single attempt per model-task. Future work.

---

### RQ7: Error Pattern Analysis
**Question:** What are common failure modes across models?

**Analysis:**
- Research task: Reference/citation failures (3 models)
- Copywriting task: Missing keywords (3 models)
- Type hint/docstring gaps (2 models)

---

### RQ8: Model Family Comparison
**Question:** Do models from the same provider show similar performance characteristics?

**Provider Analysis:**
| Provider | Models | Consistency |
|----------|--------|-------------|
| OpenAI | 3 | High (std: 0.58) |
| Google | 4 | Moderate (std: 0.96) |
| Ollama | 3 | Moderate (std: 1.0) |

---

## Analysis Plan

### Statistical Tests

1. **Chi-Square Test**
   - Compare success rates between model categories
   - Test: Are differences statistically significant?

2. **ANOVA**
   - Compare mean completion times across models
   - Factor: Model provider

3. **Correlation Analysis**
   - Pearson r: Tool count vs Success
   - Pearson r: Duration vs Quality

4. **Effect Size (Cohen's d)**
   - Magnitude of differences between top performers

### Visualization Plan

| Figure | RQ | Type | Description |
|--------|-----|------|-------------|
| Fig 1 | RQ1 | Radar | Multi-dimensional model comparison |
| Fig 2 | RQ2 | Heatmap | Model × Task performance matrix |
| Fig 3 | RQ3 | Scatter | Tool count vs Success rate |
| Fig 4 | RQ4 | Box plot | Duration distribution by task |
| Fig 5 | RQ5 | Bar | Performance per dollar |
| Fig 6 | RQ8 | Grouped bar | Provider comparison |

---

## Expected Contributions

1. **First comprehensive multi-task SE benchmark**
   - Covers 5 distinct SE activities
   - 11 state-of-the-art models
   - Automated verification

2. **Evidence-based model selection guidelines**
   - Task-specific recommendations
   - Cost-performance analysis
   - Speed-quality tradeoffs

3. **Public dataset and methodology**
   - Reproducible benchmark
   - Extensible framework
   - Raw data available

---

## Limitations to Address

1. **Single attempt per model-task**
   - No variance estimation
   - Non-deterministic behavior not captured

2. **Synthetic tasks**
   - May not represent real-world complexity
   - Controlled environment

3. **English-only evaluation**
   - Not tested on multilingual codebases

4. **Python-centric**
   - Results may not generalize to other languages

---

*Document version: 1.0*  
*Created: 2026-02-02*
