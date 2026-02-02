# Actionable Tasks: Paper Development

> Specific tasks with owners and deadlines

---

## Week 1: Foundation

### Day 1-2: Literature Search
**Agent:** Research Agent  
**File:** `agents/research/AGENTS.md`

```
Task: Conduct systematic literature review on LLM code evaluation

Search queries:
1. "LLM code generation benchmark"
2. "Large language model software engineering"
3. "GPT-4 programming task evaluation"
4. "Code generation benchmark HumanEval MBPP"
5. "SWE-bench LLM bug fixing"

Deliverables:
- papers/literature_review.json (metadata, abstracts)
- papers/categorized.md (grouped by topic)
- Minimum 40 papers identified
```

### Day 3-4: Gap Analysis
**Agent:** Research Agent  

```
Task: Analyze literature gaps

Compare our work vs existing:
- HumanEval: Single function generation
- SWE-bench: Bug fixing only
- MBPP: Python programming
- ClassEval: Class-level generation
- Our contribution: Multi-task SE benchmark

Deliverable: docs/gap_analysis.md
```

### Day 5: RQ Definition
**Owner:** Authors

```
Finalize research questions:

RQ1: How do current LLMs perform across diverse SE tasks?
RQ2: Which models excel at specific task types?
RQ3: What is the relationship between tool usage and performance?
RQ4: How does completion time correlate with accuracy?
RQ5: What are the cost-performance tradeoffs?

Deliverable: docs/research_questions.md
```

---

## Week 2: Data Analysis

### Day 1-2: Data Processing
**Agent:** Refactoring Agent  
**Script:** `analysis/process_data.py`

```python
# Input: results.json
# Output: 
#   - analysis/summary_stats.csv
#   - analysis/model_rankings.csv
#   - analysis/task_performance.csv

Tasks:
1. Parse JSON structure
2. Calculate per-model metrics
3. Calculate per-task metrics
4. Cross-tabulation
5. Export to CSV
```

### Day 3: Statistical Analysis
**Agent:** Research Agent  
**Script:** `analysis/statistics.py`

```python
# Statistical tests:
# - Chi-square for success rate differences
# - ANOVA for time differences
# - Correlation: tools vs success
# - Effect sizes

Outputs:
- analysis/statistical_tests.md
- p-values for all comparisons
```

### Day 4-5: Visualization
**Agent:** Documentation Agent  
**Script:** `analysis/visualizations.py`

```python
# Generate figures:
figures/
  fig1_overall_performance.pdf    # Radar chart
  fig2_success_rates.pdf          # Bar chart
  fig3_completion_times.pdf       # Box plot
  fig4_tool_usage.pdf             # Heatmap
  fig5_model_comparison.pdf       # Grouped bars
  fig6_time_vs_accuracy.pdf       # Scatter
```

---

## Week 3: Writing

### Day 1-2: Methodology
**Agent:** Documentation Agent  
**Output:** `paper/03_methodology.tex`

```
Sections:
3.1 Task Design
    - 5 task descriptions with code snippets
    - Task difficulty rationale
    
3.2 Model Selection
    - 13 models with specs
    - Selection rationale
    
3.3 Evaluation Framework
    - Verification methodology
    - Scoring criteria
    - Tool environment
    
3.4 Metrics
    - Success rate definition
    - Time measurement
    - Statistical methods
```

### Day 3-4: Results
**Agent:** Research Agent  
**Output:** `paper/04_results.tex`

```
Sections:
4.1 Overall Performance
    - Table: Model rankings
    - Figure: Radar chart
    
4.2 Task-Specific Analysis
    - Bug fix: Best performers
    - Feature: Implementation rates
    - Refactor: Code quality
    - Copywriting: Content analysis
    - Research: Report quality
    
4.3 Tool Usage Patterns
    - Correlation with success
    - Efficient vs inefficient patterns
    
4.4 Statistical Significance
    - Key differences
    - Effect sizes
```

### Day 5: Discussion
**Owner:** Authors  
**Output:** `paper/05_discussion.tex`

```
Sections:
5.1 Key Findings
5.2 Implications for Practice
    - Model selection guide
    - Cost considerations
5.3 Limitations
5.4 Threats to Validity
```

---

## Week 4: Integration

### Day 1: Introduction + Related Work
**Agent:** Research Agent  
**Output:** `paper/01_intro.tex`, `paper/02_related.tex`

### Day 2: Abstract + Conclusion
**Owner:** Authors  
**Output:** `paper/00_abstract.tex`, `paper/06_conclusion.tex`

### Day 3: Full Integration
**Owner:** All  
**Output:** `paper/main.tex`

```
Compile checklist:
- All sections combined
- References added
- Figures inserted
- Tables formatted
- Page count check (8-10 pages)
```

### Day 4-5: Internal Review
**Reviewers:** Peers

```
Review checklist per section:
- Technical accuracy
- Clarity
- Completeness
- Grammar/style
- Citation appropriateness
```

---

## Week 5: Revision

### Day 1-2: Address Review Comments
**Owner:** Authors

```
For each comment:
- [ ] Acknowledge
- [ ] Revise text
- [ ] Verify fix
```

### Day 3: Artifact Preparation
**Agent:** Documentation Agent

```
Repository structure:
llm-challenges/
  README.md
  data/
    results.json
    processed/
  analysis/
    scripts/
    outputs/
  paper/
    main.pdf
  reproducibility/
    requirements.txt
    Dockerfile
```

### Day 4: Final Polish
**Owner:** Authors

```
- Proofread entire paper
- Check figure quality
- Verify table alignment
- Final reference check
```

### Day 5: Camera Ready
**Owner:** Authors

```
- IEEE/ACM format compliance
- PDF generation
- Supplementary materials
- Submission metadata
```

---

## Week 6: Submission

### Day 1: Submit
**Owner:** Authors

```
Submission checklist:
- [ ] Paper PDF
- [ ] Abstract
- [ ] Author info
- [ ] Keywords
- [ ] Supplementary materials
- [ ] Artifact evaluation (if applicable)
```

---

## Quick Reference

### File Locations
```
llm-challenges/
  experiment/
    REPORT.md              # Source report
    results.json           # Raw data
    PAPER_PLAN.md          # This planning doc
    TASKS.md               # This task list
    analysis/              # Generated analysis
    paper/                 # LaTeX source
    figures/               # Generated figures
```

### Agent Assignments
| Task Type | Agent | File |
|-----------|-------|------|
| Literature | Research | agents/research/AGENTS.md |
| Writing | Documentation | agents/documentation/AGENTS.md |
| Analysis | Refactoring | agents/refactoring/AGENTS.md |
| Code | Testing | agents/testing/AGENTS.md |
| Planning | Planning | agents/planning/AGENTS.md |

### Key Metrics to Extract
```python
# From results.json
for each model:
    - success_rate = excellent_count / total
    - avg_time = mean(duration)
    - tool_usage = mean(tool_call_count)
    - task_breakdown = per_task_stats
```

---

*Last updated: 2026-02-02*
