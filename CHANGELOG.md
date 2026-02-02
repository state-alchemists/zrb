# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Agent System**: Added specialized agent configurations for various tasks
  - `agents/documentation/AGENTS.md` - Documentation agent
  - `agents/planning/AGENTS.md` - Planning agent  
  - `agents/testing/AGENTS.md` - Testing agent
  - `agents/refactoring/AGENTS.md` - Refactoring agent
  - `agents/research/AGENTS.md` - Research and academic writing agent
  - `agents/AGENTS.md` - Agent index and quick start guide

- **Research Paper**: Comprehensive evaluation of LLMs on software engineering tasks
  - Full paper draft in IEEE format (8-10 pages)
  - 13 LLM models evaluated across 5 SE tasks
  - Statistical analysis with automated verification
  - Publication-ready figures and data
  - Location: `llm-challenges/experiment/`

- **Data Analysis Pipeline**
  - `analysis/process_data.py` - Data processing and metrics calculation
  - `analysis/stat_tests.py` - Statistical tests (chi-square, ANOVA, correlations)
  - `analysis/visualizations.py` - Publication-ready figure generation
  - CSV exports for all analysis results

- **Documentation**
  - Updated `AGENTS.md` with project overview and agent information
  - Added paper reference and research highlights
  - Planning documents for paper development

### Research Findings
- **Key Discovery**: Tool usage does not correlate with task success (r=0.077, p=0.575)
- **Performance**: 4 models achieved perfect scores (GPT-5.1, Gemini-3 Pro, Deepseek, GLM-4.7)
- **Efficiency**: 8× speed variation observed between top performers
- **Task Difficulty**: Coding tasks at 100% success, research at 90.9%

### Statistics
- **Models Evaluated**: 13 (OpenAI, Google, Deepseek, Ollama)
- **Tasks**: 5 (bug-fix, feature, refactor, copywriting, research)
- **Total Runs**: 55 experiment records
- **Paper Sections**: 6 (Intro, Related Work, Methodology, Results, Discussion, Conclusion)

## [2.0.15] - 2024-XX-XX

### Previous Releases
See git history for changes prior to this documentation update.

---

## Template

### Added
- New features

### Changed
- Changes in existing functionality

### Deprecated
- Soon-to-be removed features

### Removed
- Now removed features

### Fixed
- Bug fixes

### Security
- Security improvements
