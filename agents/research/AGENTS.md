# Research Agent - AGENTS.md

> Agent configuration for academic research and journal paper writing tasks.

---

## Purpose

This agent specializes in academic research tasks including:
- Literature review and analysis
- Research methodology design
- Journal paper writing (IEEE, ACM, Springer, etc.)
- Citation and reference management
- Data analysis and visualization
- Research proposal writing
- Peer review preparation

---

## Tools & Capabilities

### Primary Tools

```python
from zrb.llm.tool.web import search_web, fetch_url
from zrb.llm.tool.file import write_file, read_file
from zrb.llm.tool.code import analyze_code
from zrb.llm.tool.bash import bash
```

### Available Actions

1. **search_web**: Search for academic papers and references
2. **fetch_url**: Download and analyze papers from URLs
3. **analyze_code**: Analyze research data/code
4. **write_file**: Write paper sections and drafts
5. **bash**: Run data analysis scripts

---

## Research Tasks

### 1. Literature Review

Conduct comprehensive literature review on a topic.

**Prompt Template:**
```
Conduct a comprehensive literature review on:
Topic: {research_topic}
Scope: {scope_description}
Time Range: {time_range}

Tasks:
1. Search for relevant papers from academic databases
2. Extract key information from each paper
3. Synthesize findings and identify gaps
4. Create organized bibliography

Save to: docs/research/literature_review_{topic}.md
```

**Example Task:**
```python
from zrb import LLMTask, StrInput, TextInput
from zrb.llm.tool.web import search_web, fetch_url
from zrb.llm.tool.file import write_file

literature_review = LLMTask(
    name="literature-review",
    description="Conduct comprehensive literature review",
    input=[
        StrInput(name="topic", description="Research topic"),
        TextInput(name="scope", description="Scope and boundaries"),
        StrInput(name="year_from", default="2020", description="Start year"),
        StrInput(name="year_to", default="2025", description="End year"),
    ],
    message="""
    Conduct a comprehensive literature review on:
    
    Topic: {ctx.input.topic}
    Scope: {ctx.input.scope}
    Time Range: {ctx.input.year_from} - {ctx.input.year_to}
    
    Deliverables:
    1. Search and identify 20-30 relevant papers
    2. Create annotated bibliography with summaries
    3. Synthesize findings into themes
    4. Identify research gaps and opportunities
    
    Organize everything into a structured document.
    """,
    tools=[search_web, fetch_url, write_file],
)
```

### 2. Research Paper Structure

Generate complete journal paper structure.

**Sections to Generate:**

1. **Abstract** (150-250 words)
   - Background and problem
   - Objective/methods
   - Key results
   - Conclusion
   - Keywords (5-6)

2. **Introduction**
   - Problem statement
   - Research motivation
   - Research questions
   - Contributions
   - Paper organization

3. **Related Work**
   - Categorize existing approaches
   - Highlight gaps
   - Position our work

4. **Methodology**
   - Research design
   - Data collection
   - Experimental setup
   - Evaluation metrics

5. **Results**
   - Present findings
   - Tables and figures
   - Statistical analysis

6. **Discussion**
   - Interpret results
   - Compare with prior work
   - Implications and limitations

7. **Conclusion**
   - Summary of contributions
   - Future work

8. **References**
   - 30-50 references
   - Proper citation format

### 3. Citation Management

Manage and format citations.

**Supported Styles:**
- IEEE (for engineering/computer science)
- APA (for social sciences)
- MLA (for humanities)
- ACM (for computer science)
- Chicago
- Harvard

**Tasks:**
1. Format references according to target style
2. Generate BibTeX entries
3. Check for missing citation information
4. Identify and remove duplicates
5. Sort references properly

### 4. Research Methodology Design

Design research methodology section.

**Components:**

1. **Research Design**
   - Type: Experimental/Quasi-experimental/Observational
   - Approach: Quantitative/Qualitative/Mixed
   - Strategy: Survey/Case study/Experiment

2. **Data Collection**
   - Population and sampling method
   - Instruments and tools
   - Data sources
   - Collection procedures
   - Ethical considerations

3. **Data Analysis**
   - Preprocessing steps
   - Analysis techniques
   - Statistical tests
   - Software/tools used

4. **Validity & Reliability**
   - Internal validity measures
   - External validity
   - Reliability assessment
   - Bias mitigation strategies

### 5. Data Analysis & Visualization

Analyze research data and create visualizations.

**Analysis Types:**
- Descriptive statistics
- Inferential statistics
- Hypothesis testing
- Correlation analysis
- Regression analysis
- Machine learning analysis

**Visualizations:**
- Distribution plots (histograms, box plots)
- Comparison charts (bar, line)
- Correlation matrices
- Scatter plots
- Heatmaps
- Network graphs

### 6. Peer Review Response

Prepare response to peer review comments.

**Process:**
1. Categorize comments (major/minor/cosmetic)
2. Draft professional response for each
3. Make required modifications
4. Track all changes
5. Create response letter

---

## Academic Writing Standards

### Language Guidelines

- Use formal academic English
- Avoid contractions (don't, can't)
- Avoid personal pronouns (I, we) where possible
- Use passive voice for objectivity
- Define acronyms on first use
- Be precise and concise

### Structure Guidelines

**Paragraph Structure:**
- Topic sentence
- Supporting evidence
- Analysis
- Transition

**Sentence Guidelines:**
- 15-25 words per sentence
- One main idea per sentence
- Vary sentence structure
- Use connectors for flow

### Common Mistakes to Avoid

1. **Grammar**
   - Subject-verb agreement
   - Tense consistency
   - Article usage (a/an/the)

2. **Style**
   - Vague language
   - Unsupported claims
   - Colloquial expressions

3. **Technical**
   - Undefined terms
   - Inconsistent notation
   - Missing units

---

## Journal-Specific Guidelines

### IEEE Transactions

- Double-column format
- Abstract: 150-250 words
- Keywords: 5-8
- Sections: numbered
- Equations: numbered
- Figures: black and white preferred
- References: IEEE style [1], [2]

### ACM Publications

- Single or double column
- Abstract: 150-200 words
- CCS concepts required
- Keywords: 4-6
- References: ACM style [Author Year]

### Springer Journals

- Springer LNCS or standard format
- Abstract: 150-300 words
- Keywords: 4-6
- Running title and authors
- Compliance with ethical standards

### arXiv Preprints

- LaTeX format preferred
- Abstract: informative
- Comments: version and changes
- Categories: appropriate subject

---

## Paper Templates

### Research Article Template

```markdown
# Title

**Authors**: [Name], [Affiliation], [Email]

## Abstract
[Background] [Objective] [Methods] [Results] [Conclusion]

**Keywords**: keyword1, keyword2, keyword3

## 1. Introduction

### 1.1 Background
Problem context and importance

### 1.2 Related Work
Existing approaches and limitations

### 1.3 Research Questions
- RQ1: ...
- RQ2: ...

### 1.4 Contributions
1. Contribution one
2. Contribution two

## 2. Methodology

### 2.1 Research Design
Approach and rationale

### 2.2 Data Collection
Sources and procedures

### 2.3 Analysis Method
Techniques and tools

## 3. Results

### 3.1 Descriptive Statistics
Basic findings

### 3.2 Statistical Analysis
Hypothesis testing results

### 3.3 Key Findings
Main discoveries

## 4. Discussion

### 4.1 Interpretation
What results mean

### 4.2 Comparison with Prior Work
How we differ

### 4.3 Implications
Theoretical and practical

### 4.4 Limitations
Constraints and scope

## 5. Conclusion

### 5.1 Summary
Key takeaways

### 5.2 Future Work
Next steps

## References
[1] Author. Title. Venue, Year.
```

### Research Proposal Template

```markdown
# Research Proposal: [Title]

## Executive Summary
Brief overview

## Introduction
- Problem statement
- Significance
- Objectives

## Literature Review
- Current state
- Research gaps
- Theoretical framework

## Methodology
- Design
- Data collection
- Analysis plan

## Timeline
| Phase | Duration | Activities |

## Budget
| Item | Cost |

## Expected Outcomes
- Deliverables
- Publications
- Impact

## References
```

---

## Research Workflow

### Complete Research Pipeline

```python
from zrb import cli, Group, LLMTask, CmdTask
from zrb.llm.tool.web import search_web
from zrb.llm.tool.file import write_file

research_group = cli.add_group(Group(name="research", description="Research tasks"))

# Step 1: Literature Review
literature_review = research_group.add_task(LLMTask(
    name="literature-review",
    description="Conduct literature review",
    input=[StrInput(name="topic"), StrInput(name="output", default="lit_review.md")],
    message="Conduct comprehensive literature review on {ctx.input.topic}",
    tools=[search_web, write_file],
))

# Step 2: Methodology Design
methodology = research_group.add_task(LLMTask(
    name="methodology",
    description="Design research methodology",
    message="Design methodology section based on literature review",
    tools=[write_file],
))

# Step 3: Draft Paper
draft_paper = research_group.add_task(LLMTask(
    name="draft",
    description="Draft research paper",
    message="Generate complete research paper draft",
    tools=[write_file],
))

# Step 4: Generate References
references = research_group.add_task(LLMTask(
    name="references",
    description="Format references",
    message="Format all citations in target style",
    tools=[write_file],
))

# Chain workflow
literature_review >> methodology >> draft_paper >> references
```

---

## Quality Checklist

### Before Submission

- [ ] Abstract summarizes all key points
- [ ] Introduction clearly states problem
- [ ] Related work is comprehensive
- [ ] Methodology is reproducible
- [ ] Results are clearly presented
- [ ] Discussion interprets findings
- [ ] Conclusion summarizes contributions
- [ ] All citations are complete
- [ ] No plagiarism detected
- [ ] Figures are high quality
- [ ] Tables are properly formatted
- [ ] Proofread for errors
- [ ] Meets journal formatting requirements
- [ ] Word count within limits
- [ ] Ethics approval (if applicable)
- [ ] Data availability statement
- [ ] Conflict of interest declared
- [ ] Author contributions listed
- [ ] Acknowledgments included
- [ ] Supplementary materials prepared

---

## Related Agents

- `../documentation/AGENTS.md` - For research documentation
- `../planning/AGENTS.md` - For research planning
- `../testing/AGENTS.md` - For validating research code
- `../refactoring/AGENTS.md` - For research code optimization

---

Last updated: 2026-02-02
