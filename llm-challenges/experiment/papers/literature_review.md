# Literature Review: LLM Evaluation for Software Engineering

> Systematic review of related work in LLM code evaluation

---

## 1. Code Generation Benchmarks

### 1.1 HumanEval
**Reference:** Chen et al. (2021) - "Evaluating Large Language Models Trained on Code"  
**URL:** https://github.com/openai/human-eval

**Summary:**
- 164 hand-written programming problems
- Function-level code generation
- Pass@k metric for evaluation
- Python-focused

**Relation to our work:**
- Our work extends beyond function-level to full SE tasks
- HumanEval tests isolated functions, we test integrated workflows

---

### 1.2 MBPP (Mostly Basic Python Programming)
**Reference:** Austin et al. (2021) - "Program Synthesis with Large Language Models"  
**URL:** https://github.com/google-research/google-research/tree/master/mbpp

**Summary:**
- 974 Python programming problems
- Crowd-sourced from programming communities
- Standardized test cases

**Relation to our work:**
- MBPP focuses on stand-alone problems
- Our benchmark includes realistic, interconnected tasks

---

## 2. Software Engineering Benchmarks

### 2.1 SWE-bench
**Reference:** Jimenez et al. (2023) - "SWE-bench: Can Language Models Resolve Real-world GitHub Issues?"  
**URL:** https://www.swebench.com
**Paper:** https://openreview.net/forum?id=VTF8yNQM66

**Summary:**
- 2,294 real GitHub issues from 12 Python repositories
- Tests bug fixing and feature implementation
- Uses actual codebase context
- Automated test verification

**Key Findings:**
- GPT-4 solves 1.7% of issues (original study)
- Claude 3.5 Sonnet achieves ~20% (2024 results)
- Major improvement area for LLMs

**Relation to our work:**
- SWE-bench focuses on real-world issues
- Our work provides controlled, reproducible tasks
- Complementary approaches

---

### 2.2 SWE-bench Lite & Verified
**Reference:** SWE-bench+ (2024)  
**URL:** https://arxiv.org/html/2410.06992v2

**Summary:**
- Lite: 300 bug-fixing focused issues
- Verified: 500 verified issues with clear descriptions
- Addresses data quality issues

**Relation to our work:**
- Our verification approach similar to Verified
- We provide 5 distinct task types vs single focus

---

### 2.3 SWT-bench
**Reference:** NeurIPS 2024  
**URL:** https://github.com/logic-star-ai/swt-bench

**Summary:**
- Focus on test generation
- Real-world GitHub issues
- Evaluates testing capability

---

### 2.4 ClassEval
**Reference:** (Repository-level code generation)

**Summary:**
- Class-level code generation
- Multiple method implementation
- Context-aware generation

**Relation to our work:**
- We include refactoring tasks (class-level improvements)
- Our feature task involves class design

---

## 3. LLM Comparison Studies

### 3.1 GPT-4 vs CodeLlama Evaluation
**Reference:** "Evaluating LLM-Guided Software Programming" (2024)  
**URL:** https://arxiv.org/html/2402.14261v1

**Summary:**
- Compares GPT-3.5, GPT-4, and CodeLlama
- Five different software engineering tasks
- Performance varies significantly by task type

**Key Findings:**
- GPT-4 consistently outperforms on complex tasks
- CodeLlama competitive for basic programming
- Task-specific model selection beneficial

**Relation to our work:**
- Similar multi-task evaluation approach
- We expand to more models (13) and task types (5)
- We include automated verification

---

### 3.2 GPT-4 vs Human Performance
**Reference:** "Comparing Large Language Models and Human Developers"  
**URL:** https://advanced.onlinelibrary.wiley.com/doi/10.1002/advs.202412279

**Summary:**
- GPT-4 tested on front-end developer, software engineer roles
- Multiple role-specific tests
- Comparison with human performance

**Key Findings:**
- GPT-4 passes all three role tests
- Competitive with human developers in certain contexts

---

### 3.3 CodeLlama vs GPT-4 Pair Programming
**Reference:** "Evaluation of human and AI cooperation in pair programming"  
**URL:** https://www.researchgate.net/publication/395791979

**Summary:**
- GPT-4 vs CodeLlama in pair programming scenarios
- Productivity metrics comparison
- Human-AI collaboration patterns

**Key Findings:**
- GPT-4: 89% success in function generation
- CodeLlama: Lower but acceptable performance
- Collaboration style affects outcomes

---

## 4. Survey Papers

### 4.1 Survey on LLMs for Code Generation
**Reference:** ACM Computing Surveys (2025)  
**URL:** https://dl.acm.org/doi/10.1145/3747588

**Summary:**
- Comprehensive survey of 250+ papers
- Taxonomy of code generation approaches
- Model comparison: ChatGPT, GPT-4, LLaMA, CodeLlama

**Key Insights:**
- Rapid evolution in the field
- Open vs closed model comparison ongoing
- Need for standardized benchmarks

**Relation to our work:**
- Our benchmark addresses need for standardized SE evaluation
- We provide open dataset for community use

---

### 4.2 LLMs for Code Analysis
**Reference:** USENIX Security 2024  
**URL:** https://www.usenix.org/system/files/sec24fall-prepub-2205-fang.pdf

**Summary:**
- Systematic evaluation of GPT and LLaMA models
- Code analysis capabilities
- Security and vulnerability detection

---

## 5. Evaluation Methodology Papers

### 5.1 Fixing SWE-bench
**Reference:** Toloka AI (2025)  
**URL:** https://toloka.ai/blog/fixing-swe-bench

**Summary:**
- Analysis of SWE-bench limitations
- Proposed improvements to evaluation
- Data quality considerations

**Key Points:**
- Real-world issues may be ambiguous
- Verification challenges
- Need for controlled evaluation

**Relation to our work:**
- We provide controlled, verifiable tasks
- Automated verification pipeline
- Clear success criteria

---

## 6. Related Papers by Topic

### 6.1 Bug Fixing
- "Can Language Models Fix Bugs?" (various)
- SWE-bench series
- Our contribution: Concurrency bug fixing evaluation

### 6.2 Code Refactoring
- "LLM-based Code Refactoring" 
- Limited existing benchmarks
- Our contribution: Structured refactoring tasks

### 6.3 Technical Writing
- Limited evaluation in SE context
- Our contribution: Copywriting with verification

### 6.4 Research Synthesis
- "Large Language Models for Scientific Research"
- Our contribution: Research task with quality metrics

---

## 7. Model Comparison Papers

| Model | Key Papers | Performance |
|-------|-----------|-------------|
| GPT-4 | OpenAI (2023), Various evaluations | State-of-the-art |
| GPT-4o | OpenAI (2024) | Faster, multimodal |
| Gemini | Google (2024) | Competitive with GPT-4 |
| CodeLlama | Meta (2023) | Best open-source |
| Deepseek | Deepseek AI (2024) | Strong coding |
| Claude | Anthropic (2024) | Long context |

---

## 8. Gap Analysis

### Current Benchmark Limitations

| Benchmark | Scope | Verification | Our Improvement |
|-----------|-------|--------------|-----------------|
| HumanEval | Function-level | Unit tests | Full workflows |
| MBPP | Function-level | Unit tests | Integrated tasks |
| SWE-bench | Real issues | Test suite | Controlled tasks |
| ClassEval | Class-level | Unit tests | Multiple task types |

### Our Contributions

1. **Multi-task coverage**: 5 distinct SE activities
2. **Automated verification**: Objective success criteria
3. **Controlled environment**: Reproducible results
4. **Comprehensive models**: 13 state-of-the-art LLMs
5. **Public dataset**: Raw data available

---

## 9. Citations for Paper

### Must-Cite Papers
```bibtex
@article{chen2021evaluating,
  title={Evaluating large language models trained on code},
  author={Chen, Mark and Tworek, Jerry and Jun, Heewoo and Yuan, Qiming and Pinto, Henrique Ponde de Oliveira and Kaplan, Jared and Edwards, Harri and Burda, Yuri and Joseph, Nicholas and Brockman, Greg and others},
  journal={arXiv preprint arXiv:2107.03374},
  year={2021}
}

@article{jimenez2023swe,
  title={SWE-bench: Can language models resolve real-world github issues?},
  author={Jimenez, Carlos E and Yang, John and Wettig, Alexander and Yao, Shunyu and Pei, Kexin and Press, Ofir and Kaplan, Karthik R},
  journal={arXiv preprint arXiv:2310.06770},
  year={2023}
}

@article{llm_code_survey_2025,
  title={A Survey on Large Language Models for Code Generation},
  journal={ACM Computing Surveys},
  year={2025}
}
```

---

## 10. Research Directions Identified

### From Literature Review

1. **Multi-modal evaluation**: Code + documentation + diagrams
2. **Long-context handling**: Repository-level understanding
3. **Agent-based evaluation**: Multi-step SE workflows
4. **Domain-specific**: Web, mobile, systems programming
5. **Human-AI collaboration**: Pair programming scenarios

### Our Position

Our work addresses:
- Multi-task evaluation (gap #1 partially)
- Agent-based workflows (gap #3)
- Standardized verification (general need)

Future work could address:
- Multi-modal tasks
- Domain-specific benchmarks
- Long-context repository tasks

---

*Literature review compiled: 2026-02-02*  
*Total papers reviewed: 15+ key papers*  
*Recommended citations for paper: 30-50*
