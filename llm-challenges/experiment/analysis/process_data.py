#!/usr/bin/env python3
"""
Data Processing Script for LLM Challenge Experiment

Processes results.json and generates summary statistics,
model rankings, and performance metrics for paper analysis.
"""

import json
import csv
from pathlib import Path
from collections import defaultdict
from statistics import mean, stdev, median
import sys

# Add src to path if needed
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))


def load_results(filepath: str = "../results.json") -> list:
    """Load experiment results from JSON file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def categorize_model(model_name: str) -> str:
    """Categorize model by provider."""
    if "openai" in model_name.lower():
        return "OpenAI"
    elif "google" in model_name.lower() or "gemini" in model_name.lower():
        return "Google"
    elif "deepseek" in model_name.lower():
        return "Deepseek"
    elif "ollama" in model_name.lower() or "glm" in model_name.lower() or "kimi" in model_name.lower() or "qwen" in model_name.lower():
        return "Open/Ollama"
    return "Other"


def calculate_success_score(status: str) -> int:
    """Convert status to numeric score."""
    scores = {
        "EXCELLENT": 2,
        "PASS": 1,
        "FAIL": 0,
        "EXECUTION_FAILED": 0
    }
    return scores.get(status.upper(), 0)


def process_results(data: list) -> dict:
    """Process raw results into structured metrics."""
    
    # Initialize data structures
    models = set()
    tasks = set()
    model_task_perf = defaultdict(lambda: defaultdict(dict))
    
    # Parse each result entry
    for entry in data:
        model = entry["model"]
        task = entry["challenge_name"]
        status = entry["status"]
        duration = entry["duration"]
        tool_count = entry.get("tool_call_count", 0)
        
        models.add(model)
        tasks.add(task)
        
        model_task_perf[model][task] = {
            "status": status,
            "score": calculate_success_score(status),
            "duration": duration,
            "tool_count": tool_count,
            "exit_code": entry.get("exit_code", -1)
        }
    
    return {
        "models": sorted(list(models)),
        "tasks": sorted(list(tasks)),
        "performance": model_task_perf
    }


def calculate_model_metrics(processed: dict) -> list:
    """Calculate per-model aggregate metrics."""
    metrics = []
    
    for model in processed["models"]:
        task_data = processed["performance"][model]
        
        scores = [task_data[t]["score"] for t in processed["tasks"] if t in task_data]
        durations = [task_data[t]["duration"] for t in processed["tasks"] if t in task_data]
        tool_counts = [task_data[t]["tool_count"] for t in processed["tasks"] if t in task_data]
        
        # Calculate metrics
        total_score = sum(scores)
        max_possible = len(processed["tasks"]) * 2  # EXCELLENT = 2 points
        success_rate = (sum(1 for s in scores if s > 0) / len(scores)) * 100 if scores else 0
        excellent_rate = (sum(1 for s in scores if s == 2) / len(scores)) * 100 if scores else 0
        
        metrics.append({
            "model": model,
            "category": categorize_model(model),
            "total_score": total_score,
            "max_possible": max_possible,
            "success_rate": round(success_rate, 2),
            "excellent_rate": round(excellent_rate, 2),
            "avg_duration": round(mean(durations), 2) if durations else 0,
            "median_duration": round(median(durations), 2) if durations else 0,
            "total_duration": round(sum(durations), 2),
            "avg_tools": round(mean(tool_counts), 2) if tool_counts else 0,
            "task_count": len(scores)
        })
    
    # Sort by total score descending
    return sorted(metrics, key=lambda x: (-x["total_score"], x["avg_duration"]))


def calculate_task_metrics(processed: dict) -> list:
    """Calculate per-task aggregate metrics."""
    metrics = []
    
    for task in processed["tasks"]:
        task_scores = []
        task_durations = []
        task_tools = []
        
        for model in processed["models"]:
            if task in processed["performance"][model]:
                data = processed["performance"][model][task]
                task_scores.append(data["score"])
                task_durations.append(data["duration"])
                task_tools.append(data["tool_count"])
        
        success_count = sum(1 for s in task_scores if s > 0)
        excellent_count = sum(1 for s in task_scores if s == 2)
        
        metrics.append({
            "task": task,
            "model_count": len(task_scores),
            "success_count": success_count,
            "excellent_count": excellent_count,
            "success_rate": round((success_count / len(task_scores)) * 100, 2) if task_scores else 0,
            "excellent_rate": round((excellent_count / len(task_scores)) * 100, 2) if task_scores else 0,
            "avg_duration": round(mean(task_durations), 2) if task_durations else 0,
            "median_duration": round(median(task_durations), 2) if task_durations else 0,
            "min_duration": round(min(task_durations), 2) if task_durations else 0,
            "max_duration": round(max(task_durations), 2) if task_durations else 0,
            "avg_tools": round(mean(task_tools), 2) if task_tools else 0
        })
    
    return metrics


def calculate_category_metrics(model_metrics: list) -> list:
    """Calculate metrics aggregated by model category."""
    category_data = defaultdict(lambda: {"scores": [], "durations": [], "models": set()})
    
    for m in model_metrics:
        cat = m["category"]
        category_data[cat]["scores"].append(m["total_score"])
        category_data[cat]["durations"].append(m["avg_duration"])
        category_data[cat]["models"].add(m["model"])
    
    metrics = []
    for cat, data in sorted(category_data.items()):
        scores = data["scores"]
        durations = data["durations"]
        
        metrics.append({
            "category": cat,
            "model_count": len(data["models"]),
            "avg_score": round(mean(scores), 2) if scores else 0,
            "std_score": round(stdev(scores), 2) if len(scores) > 1 else 0,
            "min_score": min(scores) if scores else 0,
            "max_score": max(scores) if scores else 0,
            "avg_duration": round(mean(durations), 2) if durations else 0,
            "std_duration": round(stdev(durations), 2) if len(durations) > 1 else 0
        })
    
    return metrics


def generate_detailed_matrix(processed: dict) -> list:
    """Generate detailed model x task performance matrix."""
    matrix = []
    
    for model in processed["models"]:
        row = {"model": model, "category": categorize_model(model)}
        
        for task in processed["tasks"]:
            if task in processed["performance"][model]:
                data = processed["performance"][model][task]
                row[f"{task}_status"] = data["status"]
                row[f"{task}_score"] = data["score"]
                row[f"{task}_duration"] = round(data["duration"], 2)
                row[f"{task}_tools"] = data["tool_count"]
            else:
                row[f"{task}_status"] = "N/A"
                row[f"{task}_score"] = 0
                row[f"{task}_duration"] = 0
                row[f"{task}_tools"] = 0
        
        matrix.append(row)
    
    return matrix


def save_to_csv(data: list, filepath: str, fieldnames: list = None):
    """Save data to CSV file."""
    if not data:
        print(f"Warning: No data to save to {filepath}")
        return
    
    if fieldnames is None:
        fieldnames = list(data[0].keys())
    
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    
    print(f"Saved: {filepath}")


def generate_summary_report(model_metrics: list, task_metrics: list, category_metrics: list) -> str:
    """Generate text summary report."""
    report = []
    report.append("=" * 80)
    report.append("LLM CHALLENGE EXPERIMENT - ANALYSIS SUMMARY")
    report.append("=" * 80)
    report.append("")
    
    # Model Rankings
    report.append("MODEL RANKINGS (by total score)")
    report.append("-" * 80)
    for i, m in enumerate(model_metrics[:5], 1):
        report.append(f"{i}. {m['model']}")
        report.append(f"   Score: {m['total_score']}/{m['max_possible']} "
                     f"(Success: {m['success_rate']}%, Excellent: {m['excellent_rate']}%)")
        report.append(f"   Avg Time: {m['avg_duration']}s, Avg Tools: {m['avg_tools']}")
        report.append("")
    
    # Task Difficulty
    report.append("")
    report.append("TASK DIFFICULTY (by success rate)")
    report.append("-" * 80)
    sorted_tasks = sorted(task_metrics, key=lambda x: x["success_rate"])
    for t in sorted_tasks:
        report.append(f"{t['task']}: {t['success_rate']}% success, "
                     f"avg {t['avg_duration']}s")
    
    # Category Comparison
    report.append("")
    report.append("CATEGORY COMPARISON")
    report.append("-" * 80)
    for c in sorted(category_metrics, key=lambda x: -x["avg_score"]):
        report.append(f"{c['category']}: Avg Score {c['avg_score']} "
                     f"(±{c['std_score']}), Models: {c['model_count']}")
    
    report.append("")
    report.append("=" * 80)
    
    return "\n".join(report)


def main():
    """Main processing pipeline."""
    print("Loading results data...")
    data = load_results()
    print(f"Loaded {len(data)} experiment records")
    
    print("\nProcessing results...")
    processed = process_results(data)
    print(f"Models: {len(processed['models'])}")
    print(f"Tasks: {len(processed['tasks'])}")
    
    # Calculate all metrics
    print("\nCalculating metrics...")
    model_metrics = calculate_model_metrics(processed)
    task_metrics = calculate_task_metrics(processed)
    category_metrics = calculate_category_metrics(model_metrics)
    detailed_matrix = generate_detailed_matrix(processed)
    
    # Save to CSV
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    print("\nSaving results...")
    save_to_csv(model_metrics, output_dir / "model_rankings.csv")
    save_to_csv(task_metrics, output_dir / "task_performance.csv")
    save_to_csv(category_metrics, output_dir / "category_comparison.csv")
    save_to_csv(detailed_matrix, output_dir / "detailed_matrix.csv")
    
    # Generate summary report
    report = generate_summary_report(model_metrics, task_metrics, category_metrics)
    with open(output_dir / "summary_report.txt", 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"Saved: {output_dir / 'summary_report.txt'}")
    
    # Print summary
    print("\n" + report)
    
    print("\n" + "=" * 80)
    print("Processing complete!")
    print(f"Output files in: {output_dir.absolute()}")
    print("=" * 80)


if __name__ == "__main__":
    main()
