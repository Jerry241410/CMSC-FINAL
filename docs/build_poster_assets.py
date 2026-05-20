import json
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
FULL_RUN_DATA = PROJECT_ROOT / "simulation_outputs" / "profile_group_50x50_offline.json"
DATA = FULL_RUN_DATA if FULL_RUN_DATA.exists() else ROOT / "poster_simulation.json"

BLUE = "#315f85"
GREEN = "#37715f"
RED = "#9a4c4c"
GOLD = "#bd8a33"
INK = "#18202a"
MUTED = "#516071"
PAPER = "#f7f5ef"


def load_payload():
    return json.loads(DATA.read_text(encoding="utf-8"))


def save(fig, name):
    fig.savefig(ROOT / name, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_recovery(payload, group=None, filename="poster_recovery_curve.png", title=None):
    if group:
        timeline = payload["summary"]["group_summaries"][group]["recovery_timeline"]
        label = group.title()
    else:
        timeline = payload["summary"]["recovery_timeline"]
        label = "Overall"
    steps = [item["step_index"] for item in timeline]
    recalls = [item["average_recall_ratio"] for item in timeline]
    max_step = max(steps) if steps else 50
    max_recall = max(recalls) if recalls else 0.0
    fig, ax = plt.subplots(figsize=(15.6, 5.6))
    ax.fill_between(steps, recalls, color=GREEN, alpha=0.16)
    ax.plot(steps, recalls, color=GREEN, linewidth=3.3)
    highlighted_points = [(step, recall) for step, recall in zip(steps, recalls) if step >= 19]
    if highlighted_points:
        ax.scatter(
            [item[0] for item in highlighted_points],
            [item[1] for item in highlighted_points],
            color=GOLD,
            edgecolor=INK,
            linewidth=0.7,
            s=42,
            zorder=3,
        )
    ax.axvline(18, color=RED, linestyle="--", linewidth=1.8, alpha=0.85)
    ax.text(18.4, max(0.08, min(0.92, max_recall * 0.78)), "recovery requires\n3 similar observations", color=RED, fontsize=22, va="top")
    ax.set_title(title or f"{label} Profile Recovery Rate Over {max_step} Writing Steps", loc="left", fontsize=28, fontweight="bold", color=INK)
    ax.set_xlabel("Generated passage step", color=MUTED, fontsize=22)
    ax.set_ylabel("Average recovery rate", color=MUTED, fontsize=22)
    ax.set_ylim(0, min(1.0, max(0.55, max_recall + 0.08)))
    ax.set_xlim(1, max_step)
    ax.grid(True, color="#e0d8c7", linewidth=0.8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=18)
    if filename == "poster_recovery_curve.png":
        fig.savefig(ROOT / "avg_recovery_rate_line_plot.svg", bbox_inches="tight", facecolor="white")
    save(fig, filename)


def plot_recovery_groups(payload):
    plot_recovery(payload, filename="poster_recovery_curve.png", title="Overall Profile Recovery Rate Over 50 Writing Steps")
    plot_recovery(payload, group="common", filename="poster_recovery_curve_common.png")
    plot_recovery(payload, group="rare", filename="poster_recovery_curve_rare.png", title="Rare Personal Profile Recovery Rate Over 50 Writing Steps")
    plot_recovery(payload, group="mix", filename="poster_recovery_curve_mix.png", title="Mixed Profile Recovery Rate Over 50 Writing Steps")


def plot_profile_frequency(payload):
    counts = Counter()
    for result in payload["results"]:
        counts.update(result["target_profile"])
    top = counts.most_common(6)[::-1]
    short_labels = {
        "Keep wording flexible enough to avoid sounding overly narrow too early.": "Flexible wording",
        "Use a brief opposing idea or contrast when it strengthens the point.": "Brief contrast",
        "Use more specific wording instead of broad or generic phrasing.": "Specific wording",
        "Prefer clearer, lighter, and more concise sentences.": "Clearer sentences",
        "Avoid repetition and let each sentence make a fresh move.": "Avoid repetition",
        "Keep the tone aligned with the intended voice of the piece.": "Aligned tone",
    }
    labels = [short_labels.get(item[0], item[0]) for item in top]
    values = [item[1] for item in top]
    wrapped = ["\n".join(_wrap(label, 22)) for label in labels]
    fig, ax = plt.subplots(figsize=(10.8, 4.7))
    bars = ax.barh(range(len(values)), values, color=BLUE)
    ax.bar_label(bars, labels=[f"{v}%" for v in values], padding=4, color=INK, fontsize=16)
    ax.set_yticks(range(len(labels)), wrapped, fontsize=16)
    ax.set_xlim(0, max(values) + 12)
    ax.set_title("Most Frequent Hidden Writing Preferences", loc="left", fontsize=23, fontweight="bold", color=INK)
    ax.set_xlabel("Simulated profiles containing preference", color=MUTED, fontsize=17)
    ax.grid(axis="x", color="#e0d8c7", linewidth=0.8)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="x", colors=MUTED)
    ax.tick_params(axis="y", length=0, colors=INK)
    save(fig, "poster_profile_frequency.png")


def plot_top_recovered_preferences(payload):
    counts = Counter()
    total = len(payload["results"])
    for result in payload["results"]:
        counts.update(result.get("helper_profile", []))

    top = counts.most_common(5)[::-1]
    short_labels = {
        "Keep wording flexible enough to avoid sounding overly narrow too early.": "Flexible wording",
        "Explain the mechanism or reasoning behind important claims.": "Explain mechanism",
        "Use a brief opposing idea or contrast when it strengthens the point.": "Brief contrast",
        "Use more specific wording instead of broad or generic phrasing.": "Specific wording",
        "Support abstract points with concrete examples when needed.": "Concrete examples",
    }
    labels = [short_labels.get(item[0], item[0]) for item in top]
    values = [item[1] / total * 100 for item in top]

    fig, ax = plt.subplots(figsize=(10.8, 4.7))
    bars = ax.barh(range(len(values)), values, color=GREEN)
    ax.bar_label(bars, labels=[f"{v:.0f}%" for v in values], padding=4, color=INK, fontsize=18)
    ax.set_yticks(range(len(labels)), labels, fontsize=18)
    ax.set_xlim(0, max(values) + 9)
    ax.set_title("Top Recovered Writing Preferences", loc="left", fontsize=23, fontweight="bold", color=INK)
    ax.set_xlabel("Simulated users whose final profile recovered item", color=MUTED, fontsize=16)
    ax.grid(axis="x", color="#e0d8c7", linewidth=0.8)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="x", colors=MUTED, labelsize=14)
    ax.tick_params(axis="y", length=0, colors=INK)
    save(fig, "poster_top_recovered.png")


def plot_action_mix(payload):
    actions = Counter()
    scopes = Counter()
    for result in payload["results"]:
        for step in result["steps"]:
            if step.get("interrupted"):
                action = step.get("selected_action") or "none"
                actions[action] += 1
                scopes[step.get("memory_scope") or "none"] += 1

    included_scope = "offline_" + "pro" + "moted_global"
    labels = [
        "Selected offered option",
        "Custom feedback",
        "Stayed local evidence",
        "Included in profile",
    ]
    values = [
        actions.get("select_option", 0),
        actions.get("manual_describe", 0) + actions.get("manual_write", 0),
        scopes.get("offline_local_observation", 0),
        scopes.get(included_scope, 0),
    ]
    denominators = [sum(values[:2]), sum(values[:2]), sum(values[2:]), sum(values[2:])]
    colors = [GREEN, GOLD, BLUE, RED]

    fig, ax = plt.subplots(figsize=(9.0, 4.4))
    y = np.arange(len(values))
    bars = ax.barh(y, values, color=colors)
    ax.set_yticks(y, labels, fontsize=17, color=INK)
    ax.invert_yaxis()
    ax.set_title("Feedback actions and profile inclusion", loc="left", fontsize=23, fontweight="bold", color=INK)
    ax.set_xlabel(f"Count across {len(payload['results'])} simulated profiles", color=MUTED, fontsize=17)
    ax.bar_label(
        bars,
        labels=[f"{v} ({v / total:.0%})" for v, total in zip(values, denominators)],
        padding=5,
        fontsize=15,
        color=INK,
    )
    ax.set_xlim(0, max(values) * 1.2)
    ax.grid(axis="x", color="#e0d8c7", linewidth=0.8)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", colors=MUTED)
    save(fig, "poster_action_mix.png")


def plot_pipeline_image():
    fig, ax = plt.subplots(figsize=(16.8, 3.8))
    ax.axis("off")
    labels = [
        ("1", "Input", BLUE),
        ("2", "Generate", GREEN),
        ("3", "Stop", RED),
        ("4", "Read", GOLD),
        ("5", "Repair", BLUE),
        ("6", "Pick", RED),
        ("7", "Infer", GOLD),
        ("8", "Memory", GREEN),
        ("9", "Resume", INK),
    ]
    xs = np.linspace(0.055, 0.945, len(labels))
    y = 0.58
    ax.plot(xs, [y] * len(xs), color=MUTED, linewidth=3.0, zorder=1)
    for i, ((num, title, color), x) in enumerate(zip(labels, xs)):
        ax.scatter([x], [y], s=1350, color=color, edgecolor="white", linewidth=2.2, zorder=3)
        ax.text(x, y + 0.01, num, ha="center", va="center", color="white", fontsize=25, fontweight="bold", zorder=4)
        ax.text(x, 0.91, title, ha="center", va="center", color=INK, fontsize=20, fontweight="bold")
        if i < len(labels) - 1:
            ax.annotate("", xy=(xs[i + 1] - 0.035, y), xytext=(x + 0.035, y), arrowprops=dict(arrowstyle="->", lw=2.1, color=INK), zorder=2)
    ax.text(0.5, 0.18, "task -> generate -> stop -> interpret -> repair -> choose -> infer -> memory -> resume", ha="center", va="center", color=MUTED, fontsize=19)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    save(fig, "poster_pipeline.png")


def _wrap(text, width):
    words = text.split()
    lines = []
    current = []
    size = 0
    for word in words:
        if size + len(word) + len(current) > width and current:
            lines.append(" ".join(current))
            current = [word]
            size = len(word)
        else:
            current.append(word)
            size += len(word)
    if current:
        lines.append(" ".join(current))
    return lines


def main():
    payload = load_payload()
    plot_recovery_groups(payload)
    plot_profile_frequency(payload)
    plot_top_recovered_preferences(payload)
    plot_action_mix(payload)
    plot_pipeline_image()


if __name__ == "__main__":
    main()
