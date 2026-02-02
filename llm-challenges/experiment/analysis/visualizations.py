#!/usr/bin/env python3
"""
Visualization Generator for LLM Challenge Experiment

Creates publication-ready figures for the research paper.
"""

import json
import csv
from pathlib import Path
from collections import defaultdict
import sys

# Try to import matplotlib
try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.patches import Rectangle
    import numpy as np
    HAS_MATPLOTLIB = True
except ImportError:
    print("Warning: matplotlib not available, generating data files only")
    HAS_MATPLOTLIB = False


def load_data():
    """Load processed data."""
    with open("../results.json", 'r') as f:
        return json.load(f)


def process_for_viz(data):
    """Process data for visualization."""
    models = defaultdict(lambda: {"tasks": {}, "total_score": 0})
    tasks = set()
    
    for entry in data:
        model = entry["model"]
        task = entry["challenge_name"]
        status = entry["status"]
        duration = entry["duration"]
        tools = entry.get("tool_call_count", 0)
        
        tasks.add(task)
        
        score = 2 if status == "EXCELLENT" else (1 if status == "PASS" else 0)
        
        models[model]["tasks"][task] = {
            "score": score,
            "duration": duration,
            "tools": tools,
            "status": status
        }
        models[model]["total_score"] += score
    
    return models, sorted(tasks)


def shorten_model_name(name):
    """Create shorter model names for figures."""
    replacements = {
        "openai:gpt-": "GPT-",
        "google-gla:gemini-": "Gemini-",
        "deepseek:deepseek-": "Deepseek-",
        "ollama:glm-4.7:cloud": "GLM-4.7",
        "ollama:kimi-k2.5:cloud": "Kimi-K2.5",
        "ollama:qwen3-vl:235b-cloud": "Qwen3-VL",
    }
    
    for old, new in replacements.items():
        name = name.replace(old, new)
    return name


def categorize_model(name):
    """Categorize by provider."""
    if "openai" in name:
        return "OpenAI", "#10a37f"
    elif "google" in name or "gemini" in name:
        return "Google", "#4285f4"
    elif "deepseek" in name:
        return "Deepseek", "#4d6bfa"
    elif "ollama" in name or "glm" in name or "kimi" in name or "qwen" in name:
        return "Open/Ollama", "#ff6b6b"
    return "Other", "#999999"


def generate_figure1_performance_radar(models, tasks):
    """Figure 1: Radar chart of model performance across tasks."""
    if not HAS_MATPLOTLIB:
        return None
    
    # Select top 6 models for clarity
    top_models = sorted(models.items(), key=lambda x: -x[1]["total_score"])[:6]
    
    # Prepare data
    categories = sorted(tasks)
    N = len(categories)
    
    # Compute angle for each axis
    angles = [n / float(N) * 2 * np.pi for n in range(N)]
    angles += angles[:1]  # Close the polygon
    
    fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(projection='polar'))
    
    for model_name, data in top_models:
        values = [data["tasks"].get(t, {"score": 0})["score"] for t in categories]
        values += values[:1]  # Close the polygon
        
        _, color = categorize_model(model_name)
        short_name = shorten_model_name(model_name)
        
        ax.plot(angles, values, 'o-', linewidth=2, label=short_name, color=color)
        ax.fill(angles, values, alpha=0.1, color=color)
    
    # Set category labels
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels([t.title() for t in categories], size=11)
    
    # Set y-axis
    ax.set_ylim(0, 2)
    ax.set_yticks([0, 1, 2])
    ax.set_yticklabels(["Fail", "Pass", "Excellent"], size=9)
    
    ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), fontsize=10)
    ax.set_title("Model Performance Across Tasks", size=14, pad=20, weight='bold')
    ax.grid(True)
    
    plt.tight_layout()
    plt.savefig("../figures/fig1_performance_radar.pdf", dpi=300, bbox_inches='tight')
    plt.savefig("../figures/fig1_performance_radar.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("Generated: fig1_performance_radar")


def generate_figure2_success_rates(models, tasks):
    """Figure 2: Bar chart of success rates per task."""
    if not HAS_MATPLOTLIB:
        return None
    
    # Calculate success rates per task
    task_success = {}
    for task in tasks:
        excellent = sum(1 for m in models.values() if m["tasks"].get(task, {}).get("score") == 2)
        passed = sum(1 for m in models.values() if m["tasks"].get(task, {}).get("score") >= 1)
        task_success[task] = {
            "excellent": excellent / len(models) * 100,
            "passed": (passed - excellent) / len(models) * 100,
            "failed": (len(models) - passed) / len(models) * 100
        }
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    x = np.arange(len(tasks))
    width = 0.6
    
    excellent_vals = [task_success[t]["excellent"] for t in tasks]
    passed_vals = [task_success[t]["passed"] for t in tasks]
    failed_vals = [task_success[t]["failed"] for t in tasks]
    
    ax.bar(x, excellent_vals, width, label='Excellent', color='#2ecc71')
    ax.bar(x, passed_vals, width, bottom=excellent_vals, label='Pass', color='#f39c12')
    ax.bar(x, failed_vals, width, bottom=[e+p for e,p in zip(excellent_vals, passed_vals)], 
           label='Fail', color='#e74c3c')
    
    ax.set_xlabel('Task Category', fontsize=12, weight='bold')
    ax.set_ylabel('Percentage of Models (%)', fontsize=12, weight='bold')
    ax.set_title('Success Rate by Task Category', fontsize=14, weight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels([t.title() for t in tasks], rotation=15, ha='right')
    ax.legend(loc='upper right')
    ax.set_ylim(0, 110)
    
    # Add value labels
    for i, task in enumerate(tasks):
        total = excellent_vals[i] + passed_vals[i]
        if total > 5:
            ax.text(i, total/2, f'{total:.0f}%', ha='center', va='center', 
                   fontsize=10, weight='bold', color='white')
    
    plt.tight_layout()
    plt.savefig("../figures/fig2_success_rates.pdf", dpi=300, bbox_inches='tight')
    plt.savefig("../figures/fig2_success_rates.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("Generated: fig2_success_rates")


def generate_figure3_completion_times(models, tasks):
    """Figure 3: Box plot of completion times."""
    if not HAS_MATPLOTLIB:
        return None
    
    fig, ax = plt.subplots(figsize=(12, 7))
    
    # Prepare data for box plot
    task_data = []
    task_labels = []
    task_colors = []
    
    for task in sorted(tasks):
        durations = [m["tasks"].get(task, {}).get("duration", 0) for m in models.values()]
        durations = [d for d in durations if d > 0]
        
        task_data.append(durations)
        task_labels.append(task.title())
        
        # Color by difficulty (median time)
        median_time = np.median(durations) if durations else 0
        if median_time < 50:
            task_colors.append('#2ecc71')  # Easy
        elif median_time < 200:
            task_colors.append('#f39c12')  # Medium
        else:
            task_colors.append('#e74c3c')  # Hard
    
    bp = ax.boxplot(task_data, labels=task_labels, patch_artist=True)
    
    for patch, color in zip(bp['boxes'], task_colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    
    ax.set_xlabel('Task Category', fontsize=12, weight='bold')
    ax.set_ylabel('Completion Time (seconds)', fontsize=12, weight='bold')
    ax.set_title('Task Completion Time Distribution', fontsize=14, weight='bold')
    ax.set_yscale('log')
    ax.grid(True, alpha=0.3, axis='y')
    
    # Add legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='#2ecc71', alpha=0.7, label='Fast (<50s)'),
        Patch(facecolor='#f39c12', alpha=0.7, label='Medium (50-200s)'),
        Patch(facecolor='#e74c3c', alpha=0.7, label='Slow (>200s)')
    ]
    ax.legend(handles=legend_elements, loc='upper right')
    
    plt.xticks(rotation=15, ha='right')
    plt.tight_layout()
    plt.savefig("../figures/fig3_completion_times.pdf", dpi=300, bbox_inches='tight')
    plt.savefig("../figures/fig3_completion_times.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("Generated: fig3_completion_times")


def generate_figure4_tool_usage(models, tasks):
    """Figure 4: Heatmap of tool usage."""
    if not HAS_MATPLOTLIB:
        return None
    
    # Prepare data matrix
    model_names = sorted(models.keys())
    task_names = sorted(tasks)
    
    matrix = []
    for model in model_names:
        row = []
        for task in task_names:
            tools = models[model]["tasks"].get(task, {}).get("tools", 0)
            row.append(tools)
        matrix.append(row)
    
    fig, ax = plt.subplots(figsize=(10, 10))
    
    im = ax.imshow(matrix, cmap='YlOrRd', aspect='auto')
    
    # Set ticks
    ax.set_xticks(np.arange(len(task_names)))
    ax.set_yticks(np.arange(len(model_names)))
    ax.set_xticklabels([t.title() for t in task_names], rotation=45, ha='right')
    ax.set_yticklabels([shorten_model_name(m) for m in model_names], fontsize=9)
    
    # Add colorbar
    cbar = ax.figure.colorbar(im, ax=ax)
    cbar.ax.set_ylabel('Tool Call Count', rotation=-90, va="bottom", fontsize=11)
    
    # Add text annotations
    for i in range(len(model_names)):
        for j in range(len(task_names)):
            text = ax.text(j, i, int(matrix[i][j]), ha="center", va="center", 
                          color="black" if matrix[i][j] < 50 else "white", fontsize=8)
    
    ax.set_title("Tool Usage Heatmap by Model and Task", fontsize=14, weight='bold', pad=10)
    ax.set_xlabel("Task Category", fontsize=12, weight='bold')
    ax.set_ylabel("Model", fontsize=12, weight='bold')
    
    plt.tight_layout()
    plt.savefig("../figures/fig4_tool_usage.pdf", dpi=300, bbox_inches='tight')
    plt.savefig("../figures/fig4_tool_usage.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("Generated: fig4_tool_usage")


def generate_figure5_model_ranking(models):
    """Figure 5: Horizontal bar chart of model rankings."""
    if not HAS_MATPLOTLIB:
        return None
    
    # Sort models by total score
    sorted_models = sorted(models.items(), key=lambda x: -x[1]["total_score"])
    
    fig, ax = plt.subplots(figsize=(12, 8))
    
    model_names = [shorten_model_name(m[0]) for m in sorted_models]
    scores = [m[1]["total_score"] for m in sorted_models]
    colors = [categorize_model(m[0])[1] for m in sorted_models]
    
    y_pos = np.arange(len(model_names))
    
    bars = ax.barh(y_pos, scores, color=colors, alpha=0.8, edgecolor='black', linewidth=0.5)
    
    ax.set_yticks(y_pos)
    ax.set_yticklabels(model_names, fontsize=10)
    ax.invert_yaxis()
    ax.set_xlabel('Total Score (Max 10)', fontsize=12, weight='bold')
    ax.set_title('Model Performance Ranking', fontsize=14, weight='bold')
    ax.set_xlim(0, 10.5)
    
    # Add score labels
    for i, (bar, score) in enumerate(zip(bars, scores)):
        ax.text(score + 0.1, i, str(score), va='center', fontsize=10, weight='bold')
    
    # Add legend
    legend_elements = [
        mpatches.Patch(color='#10a37f', label='OpenAI'),
        mpatches.Patch(color='#4285f4', label='Google'),
        mpatches.Patch(color='#4d6bfa', label='Deepseek'),
        mpatches.Patch(color='#ff6b6b', label='Open/Ollama')
    ]
    ax.legend(handles=legend_elements, loc='lower right')
    
    ax.grid(True, alpha=0.3, axis='x')
    plt.tight_layout()
    plt.savefig("../figures/fig5_model_ranking.pdf", dpi=300, bbox_inches='tight')
    plt.savefig("../figures/fig5_model_ranking.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("Generated: fig5_model_ranking")


def generate_figure6_time_vs_accuracy(models, tasks):
    """Figure 6: Scatter plot of time vs accuracy."""
    if not HAS_MATPLOTLIB:
        return None
    
    fig, ax = plt.subplots(figsize=(10, 7))
    
    providers = defaultdict(lambda: {"times": [], "scores": [], "models": []})
    
    for model_name, data in models.items():
        provider, color = categorize_model(model_name)
        
        avg_time = np.mean([t["duration"] for t in data["tasks"].values()])
        avg_score = np.mean([t["score"] for t in data["tasks"].values()])
        
        providers[provider]["times"].append(avg_time)
        providers[provider]["scores"].append(avg_score)
        providers[provider]["models"].append(shorten_model_name(model_name))
    
    for provider, data in providers.items():
        _, color = categorize_model(data["models"][0].lower())
        ax.scatter(data["times"], data["scores"], c=color, label=provider, 
                  s=100, alpha=0.7, edgecolors='black', linewidth=1)
        
        # Add model labels
        for i, model in enumerate(data["models"]):
            ax.annotate(model, (data["times"][i], data["scores"][i]), 
                       xytext=(5, 5), textcoords='offset points', fontsize=8)
    
    ax.set_xlabel('Average Completion Time (seconds)', fontsize=12, weight='bold')
    ax.set_ylabel('Average Score (0-2)', fontsize=12, weight='bold')
    ax.set_title('Time vs Quality Tradeoff', fontsize=14, weight='bold')
    ax.set_xscale('log')
    ax.legend(loc='lower right')
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 2.2)
    
    plt.tight_layout()
    plt.savefig("../figures/fig6_time_vs_accuracy.pdf", dpi=300, bbox_inches='tight')
    plt.savefig("../figures/fig6_time_vs_accuracy.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("Generated: fig6_time_vs_accuracy")


def generate_csv_for_external_viz(models, tasks):
    """Generate CSV files for external visualization tools."""
    
    # 1. Performance matrix
    with open("../figures/data_performance_matrix.csv", 'w', newline='') as f:
        writer = csv.writer(f)
        header = ["Model", "Category"] + [t.title() for t in sorted(tasks)] + ["Total"]
        writer.writerow(header)
        
        for model_name in sorted(models.keys()):
            category, _ = categorize_model(model_name)
            row = [shorten_model_name(model_name), category]
            
            total = 0
            for task in sorted(tasks):
                score = models[model_name]["tasks"].get(task, {}).get("score", 0)
                row.append(score)
                total += score
            
            row.append(total)
            writer.writerow(row)
    
    print("Generated: data_performance_matrix.csv")
    
    # 2. Time comparison
    with open("../figures/data_time_comparison.csv", 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Model", "Task", "Duration", "Tools", "Score"])
        
        for model_name, data in models.items():
            for task, task_data in data["tasks"].items():
                writer.writerow([
                    shorten_model_name(model_name),
                    task,
                    task_data["duration"],
                    task_data["tools"],
                    task_data["score"]
                ])
    
    print("Generated: data_time_comparison.csv")


def main():
    """Main visualization pipeline."""
    print("Loading data...")
    data = load_data()
    models, tasks = process_for_viz(data)
    
    print(f"Models: {len(models)}")
    print(f"Tasks: {len(tasks)}")
    
    # Ensure output directory exists
    Path("../figures").mkdir(exist_ok=True)
    
    if HAS_MATPLOTLIB:
        print("\nGenerating visualizations...")
        generate_figure1_performance_radar(models, tasks)
        generate_figure2_success_rates(models, tasks)
        generate_figure3_completion_times(models, tasks)
        generate_figure4_tool_usage(models, tasks)
        generate_figure5_model_ranking(models)
        generate_figure6_time_vs_accuracy(models, tasks)
        print("\nAll figures generated!")
    else:
        print("\nMatplotlib not available, skipping figure generation")
    
    print("\nGenerating CSV data files...")
    generate_csv_for_external_viz(models, tasks)
    
    print("\nDone!")


if __name__ == "__main__":
    main()
