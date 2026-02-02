#!/usr/bin/env python3
"""
Statistical Analysis for LLM Challenge Experiment

Performs rigorous statistical tests for paper publication:
- Chi-square test for independence
- ANOVA for group comparisons
- Pearson/Spearman correlations
- Effect size calculations (Cohen's d)
"""

import json
import csv
from pathlib import Path
from collections import defaultdict
from statistics import mean, stdev, variance
import math
import sys

# Try to import scipy for advanced statistics
try:
    from scipy import stats
    from scipy.stats import chi2_contingency, f_oneway, pearsonr, spearmanr
    HAS_SCIPY = True
except ImportError:
    print("Warning: scipy not available, using manual calculations")
    HAS_SCIPY = False


def load_data(filepath="../results.json"):
    """Load experiment results."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def categorize_model(name):
    """Categorize by provider."""
    if "openai" in name.lower():
        return "OpenAI"
    elif "google" in name.lower() or "gemini" in name.lower():
        return "Google"
    elif "deepseek" in name.lower():
        return "Deepseek"
    elif "ollama" in name.lower() or "glm" in name.lower() or "kimi" in name.lower() or "qwen" in name.lower():
        return "Open/Ollama"
    return "Other"


def score_status(status):
    """Convert status to numeric score."""
    return 2 if status == "EXCELLENT" else (1 if status == "PASS" else 0)


def chi_square_test(data):
    """
    Test 1: Chi-square test for independence
    H0: Model category and success are independent
    H1: They are dependent
    """
    print("=" * 80)
    print("TEST 1: Chi-Square Test for Independence")
    print("=" * 80)
    print("H0: Model category and task success are independent")
    print("H1: Model category affects task success")
    print()
    
    # Build contingency table
    categories = defaultdict(lambda: {"success": 0, "fail": 0})
    
    for entry in data:
        cat = categorize_model(entry["model"])
        status = entry["status"]
        
        if status in ["EXCELLENT", "PASS"]:
            categories[cat]["success"] += 1
        else:
            categories[cat]["fail"] += 1
    
    # Create contingency table
    table = []
    cat_names = []
    for cat, counts in sorted(categories.items()):
        table.append([counts["success"], counts["fail"]])
        cat_names.append(cat)
    
    print("Contingency Table:")
    print(f"{'Category':<15} {'Success':<10} {'Fail':<10}")
    print("-" * 40)
    for i, cat in enumerate(cat_names):
        print(f"{cat:<15} {table[i][0]:<10} {table[i][1]:<10}")
    print()
    
    if HAS_SCIPY:
        chi2, p_value, dof, expected = chi2_contingency(table)
        
        print(f"Chi-square statistic: {chi2:.4f}")
        print(f"p-value: {p_value:.6f}")
        print(f"Degrees of freedom: {dof}")
        print()
        
        print("Expected frequencies:")
        for i, cat in enumerate(cat_names):
            print(f"  {cat}: Success={expected[i][0]:.2f}, Fail={expected[i][1]:.2f}")
        print()
        
        alpha = 0.05
        if p_value < alpha:
            print(f"[SIGNIFICANT] (p < {alpha}): Reject H0")
            print("   Model category DOES affect success rate")
        else:
            print(f"[NOT SIGNIFICANT] (p >= {alpha}): Fail to reject H0")
            print("   No evidence that category affects success")
    else:
        print("(Scipy not available for chi-square calculation)")
    
    print()
    return {
        "test": "Chi-Square",
        "categories": cat_names,
        "table": table,
        "significant": HAS_SCIPY and p_value < 0.05 if HAS_SCIPY else None
    }


def anova_analysis(data):
    """
    Test 2: One-way ANOVA
    H0: All model categories have equal mean completion times
    H1: At least one category differs
    """
    print("=" * 80)
    print("TEST 2: One-Way ANOVA (Completion Times)")
    print("=" * 80)
    print("H0: All categories have equal mean completion times")
    print("H1: At least one category differs")
    print()
    
    # Group durations by category
    cat_durations = defaultdict(list)
    for entry in data:
        cat = categorize_model(entry["model"])
        cat_durations[cat].append(entry["duration"])
    
    # Summary statistics
    print("Summary Statistics by Category:")
    print(f"{'Category':<15} {'N':<6} {'Mean':<10} {'Std':<10} {'Min':<8} {'Max':<8}")
    print("-" * 75)
    
    groups = []
    group_names = []
    for cat in sorted(cat_durations.keys()):
        durations = cat_durations[cat]
        groups.append(durations)
        group_names.append(cat)
        
        n = len(durations)
        m = mean(durations)
        s = stdev(durations) if len(durations) > 1 else 0
        min_d = min(durations)
        max_d = max(durations)
        
        print(f"{cat:<15} {n:<6} {m:<10.2f} {s:<10.2f} {min_d:<8.1f} {max_d:<8.1f}")
    print()
    
    if HAS_SCIPY and len(groups) >= 2:
        f_stat, p_value = f_oneway(*groups)
        
        print(f"F-statistic: {f_stat:.4f}")
        print(f"p-value: {p_value:.6f}")
        print()
        
        alpha = 0.05
        if p_value < alpha:
            print(f"[SIGNIFICANT] (p < {alpha}): Reject H0")
            print("   At least one category differs in completion time")
        else:
            print(f"[NOT SIGNIFICANT] (p >= {alpha}): Fail to reject H0")
            print("   No significant difference in completion times")
    else:
        print("(Scipy not available or insufficient groups for ANOVA)")
    
    print()
    return {
        "test": "ANOVA",
        "groups": group_names,
        "durations": cat_durations,
        "significant": HAS_SCIPY and p_value < 0.05 if HAS_SCIPY else None
    }


def correlation_analysis(data):
    """
    Test 3: Correlation Analysis
    - Tool count vs Success score
    - Duration vs Success score
    """
    print("=" * 80)
    print("TEST 3: Correlation Analysis")
    print("=" * 80)
    print()
    
    # Prepare data
    tool_counts = []
    durations = []
    scores = []
    
    for entry in data:
        tool_counts.append(entry.get("tool_call_count", 0))
        durations.append(entry["duration"])
        scores.append(score_status(entry["status"]))
    
    results = {}
    
    # Correlation 1: Tool count vs Score
    print("3.1: Tool Count vs Success Score")
    print("-" * 40)
    
    if HAS_SCIPY:
        pearson_r, pearson_p = pearsonr(tool_counts, scores)
        spearman_r, spearman_p = spearmanr(tool_counts, scores)
        
        print(f"Pearson r: {pearson_r:.4f} (p={pearson_p:.6f})")
        print(f"Spearman rho: {spearman_r:.4f} (p={spearman_p:.6f})")
        
        if pearson_p < 0.05:
            direction = "positive" if pearson_r > 0 else "negative"
            print(f"[SIGNIFICANT]: {direction} correlation")
        else:
            print("[NOT SIGNIFICANT]: No linear correlation")
    else:
        pearson_r = manual_pearson(tool_counts, scores)
        print(f"Pearson r (manual): {pearson_r:.4f}")
    
    results["tools_vs_score"] = {"r": pearson_r if HAS_SCIPY else pearson_r}
    print()
    
    # Correlation 2: Duration vs Score
    print("3.2: Duration vs Success Score")
    print("-" * 40)
    
    if HAS_SCIPY:
        pearson_r, pearson_p = pearsonr(durations, scores)
        spearman_r, spearman_p = spearmanr(durations, scores)
        
        print(f"Pearson r: {pearson_r:.4f} (p={pearson_p:.6f})")
        print(f"Spearman rho: {spearman_r:.4f} (p={spearman_p:.6f})")
        
        if pearson_p < 0.05:
            direction = "positive" if pearson_r > 0 else "negative"
            print(f"[SIGNIFICANT]: {direction} correlation")
        else:
            print("[NOT SIGNIFICANT]: No linear correlation")
    else:
        pearson_r = manual_pearson(durations, scores)
        print(f"Pearson r (manual): {pearson_r:.4f}")
    
    results["duration_vs_score"] = {"r": pearson_r if HAS_SCIPY else pearson_r}
    print()
    
    return results


def manual_pearson(x, y):
    """Calculate Pearson r manually."""
    n = len(x)
    if n != len(y) or n == 0:
        return 0
    
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    
    numerator = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    denom_x = math.sqrt(sum((xi - mean_x) ** 2 for xi in x))
    denom_y = math.sqrt(sum((yi - mean_y) ** 2 for yi in y))
    
    if denom_x == 0 or denom_y == 0:
        return 0
    
    return numerator / (denom_x * denom_y)


def cohens_d(group1, group2):
    """Calculate Cohen's d effect size."""
    n1, n2 = len(group1), len(group2)
    if n1 == 0 or n2 == 0:
        return 0
    
    mean1, mean2 = mean(group1), mean(group2)
    var1 = variance(group1) if n1 > 1 else 0
    var2 = variance(group2) if n2 > 1 else 0
    
    # Pooled standard deviation
    pooled_std = math.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))
    
    if pooled_std == 0:
        return 0
    
    return (mean1 - mean2) / pooled_std


def effect_size_analysis(data):
    """
    Test 4: Effect Size Analysis (Cohen's d)
    Compare top performers vs others
    """
    print("=" * 80)
    print("TEST 4: Effect Size Analysis (Cohen's d)")
    print("=" * 80)
    print()
    
    # Group by model performance
    model_scores = defaultdict(list)
    for entry in data:
        model_scores[entry["model"]].append(score_status(entry["status"]))
    
    # Calculate average scores
    avg_scores = {m: mean(s) for m, s in model_scores.items()}
    top_model = max(avg_scores, key=avg_scores.get)
    bottom_model = min(avg_scores, key=avg_scores.get)
    
    top_scores = model_scores[top_model]
    bottom_scores = model_scores[bottom_model]
    
    d = cohens_d(top_scores, bottom_scores)
    
    print(f"Comparing: {top_model} vs {bottom_model}")
    print(f"Top model avg: {avg_scores[top_model]:.2f}")
    print(f"Bottom model avg: {avg_scores[bottom_model]:.2f}")
    print(f"Cohen's d: {d:.4f}")
    print()
    
    # Interpretation
    if abs(d) < 0.2:
        interpretation = "negligible"
    elif abs(d) < 0.5:
        interpretation = "small"
    elif abs(d) < 0.8:
        interpretation = "medium"
    else:
        interpretation = "large"
    
    print(f"Effect size: {interpretation}")
    print()
    
    # Compare categories
    print("Category Comparisons:")
    print("-" * 40)
    
    cat_scores = defaultdict(list)
    for entry in data:
        cat = categorize_model(entry["model"])
        cat_scores[cat].append(score_status(entry["status"]))
    
    cats = list(cat_scores.keys())
    for i in range(len(cats)):
        for j in range(i+1, len(cats)):
            d = cohens_d(cat_scores[cats[i]], cat_scores[cats[j]])
            print(f"{cats[i]} vs {cats[j]}: d = {d:.4f}")
    
    print()
    return {
        "test": "Effect Size",
        "top_vs_bottom": d,
        "interpretation": interpretation
    }


def task_difficulty_analysis(data):
    """
    Test 5: Task Difficulty Comparison
    """
    print("=" * 80)
    print("TEST 5: Task Difficulty Analysis")
    print("=" * 80)
    print()
    
    task_stats = defaultdict(lambda: {"scores": [], "durations": []})
    
    for entry in data:
        task = entry["challenge_name"]
        task_stats[task]["scores"].append(score_status(entry["status"]))
        task_stats[task]["durations"].append(entry["duration"])
    
    print("Task Statistics:")
    print(f"{'Task':<15} {'N':<6} {'Avg Score':<12} {'Success %':<12} {'Avg Time':<10}")
    print("-" * 65)
    
    difficulties = []
    for task, stats in sorted(task_stats.items()):
        n = len(stats["scores"])
        avg_score = mean(stats["scores"])
        success_rate = sum(1 for s in stats["scores"] if s > 0) / n * 100
        avg_time = mean(stats["durations"])
        
        print(f"{task:<15} {n:<6} {avg_score:<12.2f} {success_rate:<12.1f} {avg_time:<10.1f}")
        
        difficulties.append({
            "task": task,
            "success_rate": success_rate,
            "avg_score": avg_score,
            "avg_time": avg_time
        })
    
    print()
    
    # Rank by difficulty (inverse success rate)
    print("Difficulty Ranking (by success rate):")
    sorted_tasks = sorted(difficulties, key=lambda x: x["success_rate"])
    for i, t in enumerate(sorted_tasks, 1):
        print(f"{i}. {t['task']}: {t['success_rate']:.1f}% success")
    
    print()
    return difficulties


def generate_report(all_results, output_dir):
    """Generate comprehensive statistical report."""
    report_path = output_dir / "statistical_report.txt"
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("STATISTICAL ANALYSIS REPORT\n")
        f.write("LLM Challenge Experiment\n")
        f.write("=" * 80 + "\n\n")
        
        f.write("SUMMARY OF FINDINGS:\n")
        f.write("-" * 40 + "\n\n")
        
        # Key findings
        f.write("1. CHI-SQUARE TEST:\n")
        if all_results["chi2"]["significant"] is not None:
            sig = "SIGNIFICANT" if all_results["chi2"]["significant"] else "NOT SIGNIFICANT"
            f.write(f"   Result: {sig}\n")
            f.write(f"   Interpretation: Model category {'does' if all_results['chi2']['significant'] else 'does not'} affect success\n")
        f.write("\n")
        
        f.write("2. ANOVA (Completion Times):\n")
        if all_results["anova"]["significant"] is not None:
            sig = "SIGNIFICANT" if all_results["anova"]["significant"] else "NOT SIGNIFICANT"
            f.write(f"   Result: {sig}\n")
        f.write("\n")
        
        f.write("3. CORRELATIONS:\n")
        if "tools_vs_score" in all_results["correlation"]:
            r = all_results["correlation"]["tools_vs_score"]["r"]
            f.write(f"   Tool count vs Score: r = {r:.4f}\n")
        if "duration_vs_score" in all_results["correlation"]:
            r = all_results["correlation"]["duration_vs_score"]["r"]
            f.write(f"   Duration vs Score: r = {r:.4f}\n")
        f.write("\n")
        
        f.write("4. EFFECT SIZE:\n")
        f.write(f"   Cohen's d (top vs bottom): {all_results['effect']['top_vs_bottom']:.4f}\n")
        f.write(f"   Interpretation: {all_results['effect']['interpretation']} effect\n")
        f.write("\n")
        
        f.write("=" * 80 + "\n")
        f.write("END OF REPORT\n")
        f.write("=" * 80 + "\n")
    
    print(f"Saved: {report_path}")


def main():
    """Main statistical analysis pipeline."""
    print("\n" + "=" * 80)
    print("STATISTICAL ANALYSIS FOR LLM CHALLENGE EXPERIMENT")
    print("=" * 80 + "\n")
    
    if not HAS_SCIPY:
        print("WARNING: scipy not installed. Using manual calculations.")
        print("For full statistical tests, install: pip install scipy\n")
    
    print("Loading data...")
    data = load_data()
    print(f"Loaded {len(data)} records\n")
    
    # Create output directory
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    # Run all tests
    all_results = {}
    
    all_results["chi2"] = chi_square_test(data)
    all_results["anova"] = anova_analysis(data)
    all_results["correlation"] = correlation_analysis(data)
    all_results["effect"] = effect_size_analysis(data)
    all_results["difficulty"] = task_difficulty_analysis(data)
    
    # Generate report
    generate_report(all_results, output_dir)
    
    print("\n" + "=" * 80)
    print("STATISTICAL ANALYSIS COMPLETE")
    print("=" * 80)
    print("\nKey Takeaways:")
    print("1. Check if model category significantly affects success")
    print("2. Compare completion time differences")
    print("3. Examine correlation between tool usage and performance")
    print("4. Evaluate effect sizes for practical significance")
    print("\nResults saved to: output/statistical_report.txt")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
