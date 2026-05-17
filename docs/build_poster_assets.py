import json
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "poster_simulation.json"

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


def plot_recovery(payload):
    timeline = payload["summary"]["recovery_timeline"]
    steps = [item["step_index"] for item in timeline]
    recalls = [item["average_recall_ratio"] for item in timeline]
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    ax.fill_between(steps, recalls, color=GREEN, alpha=0.16)
    ax.plot(steps, recalls, color=GREEN, linewidth=3.3)
    ax.scatter(steps[18:], recalls[18:], color=GOLD, edgecolor=INK, linewidth=0.7, s=42, zorder=3)
    ax.axvline(18, color=RED, linestyle="--", linewidth=1.8, alpha=0.85)
    ax.text(18.3, 0.48, "promotion threshold\nstarts to matter", color=RED, fontsize=11, va="top")
    ax.set_title("Recovered Profile Recall Over 30 Writing Steps", loc="left", fontsize=15, fontweight="bold", color=INK)
    ax.set_xlabel("Generated passage step", color=MUTED)
    ax.set_ylabel("Average recall", color=MUTED)
    ax.set_ylim(0, 0.55)
    ax.set_xlim(1, 30)
    ax.grid(True, color="#e0d8c7", linewidth=0.8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(colors=MUTED)
    save(fig, "poster_recovery_curve.png")


def plot_profile_frequency(payload):
    counts = Counter()
    for result in payload["results"]:
        counts.update(result["target_profile"])
    top = counts.most_common(10)[::-1]
    labels = [item[0] for item in top]
    values = [item[1] for item in top]
    wrapped = ["\n".join(_wrap(label, 38)) for label in labels]
    fig, ax = plt.subplots(figsize=(7.6, 5.3))
    bars = ax.barh(range(len(values)), values, color=BLUE)
    ax.bar_label(bars, labels=[f"{v}%" for v in values], padding=4, color=INK, fontsize=10)
    ax.set_yticks(range(len(labels)), wrapped, fontsize=9)
    ax.set_xlim(0, max(values) + 12)
    ax.set_title("Most Frequent Hidden Writing Preferences", loc="left", fontsize=15, fontweight="bold", color=INK)
    ax.set_xlabel("Simulated profiles containing preference", color=MUTED)
    ax.grid(axis="x", color="#e0d8c7", linewidth=0.8)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="x", colors=MUTED)
    ax.tick_params(axis="y", length=0, colors=INK)
    save(fig, "poster_profile_frequency.png")


def plot_promotion_heatmap(payload):
    promoted = defaultdict(int)
    interrupted = defaultdict(int)
    for result in payload["results"]:
        for step in result["steps"]:
            idx = int(step["step_index"])
            if step.get("interrupted"):
                interrupted[idx] += 1
            if step.get("profile_summary_added"):
                promoted[idx] += 1
    steps = list(range(1, 31))
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    width = 0.72
    ax.bar(steps, [interrupted[i] for i in steps], width=width, color="#d8e4eb", label="interruptions")
    ax.bar(steps, [promoted[i] for i in steps], width=width, color=RED, label="global promotions")
    ax.set_title("Interruptions vs. Durable Profile Promotions", loc="left", fontsize=15, fontweight="bold", color=INK)
    ax.set_xlabel("Step", color=MUTED)
    ax.set_ylabel("Count across 100 users", color=MUTED)
    ax.set_xlim(0.25, 30.75)
    ax.grid(axis="y", color="#e0d8c7", linewidth=0.8)
    ax.legend(frameon=False, loc="upper left", fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(colors=MUTED)
    save(fig, "poster_promotion_bars.png")


def plot_action_mix(payload):
    actions = Counter()
    scopes = Counter()
    for result in payload["results"]:
        for step in result["steps"]:
            if step.get("interrupted"):
                action = step.get("selected_action") or "none"
                actions[action] += 1
                scopes[step.get("memory_scope") or "none"] += 1

    fig, axes = plt.subplots(1, 2, figsize=(7.6, 3.45))
    for ax, counter, title, colors in [
        (axes[0], actions, "Repair Action Mix", [GREEN, GOLD, RED]),
        (axes[1], scopes, "Memory Update Scope", [BLUE, GOLD, RED]),
    ]:
        labels = list(counter.keys())
        values = [counter[k] for k in labels]
        short = [label.replace("offline_", "").replace("_", "\n") for label in labels]
        ax.pie(values, labels=short, colors=colors[: len(values)], autopct="%1.0f%%", startangle=90, textprops={"fontsize": 9, "color": INK})
        ax.set_title(title, fontsize=14, fontweight="bold", color=INK)
    save(fig, "poster_action_mix.png")


def plot_pipeline_image():
    fig, ax = plt.subplots(figsize=(11.4, 3.7))
    ax.axis("off")
    labels = [
        ("1", "Input", "user name +\nwriting task", BLUE),
        ("2", "Draft", "Streaming\nWriter Agent", GREEN),
        ("3", "Stop", "user interrupts\nbad sentence", RED),
        ("4", "Diagnose", "Interruption\nInterpreter Agent", GOLD),
        ("5", "Options", "Replacement\nAgent", BLUE),
        ("6", "Choose", "user selects option\nor custom repair", RED),
        ("7", "Infer", "Behavior\nInterpreter Agent", GOLD),
        ("8", "Memory", "Preference\nMemory Agent", GREEN),
        ("9", "Resume", "profile-aware\nnext draft", INK),
    ]
    xs = np.linspace(0.045, 0.955, len(labels))
    y = 0.58
    ax.plot(xs, [y] * len(xs), color=MUTED, linewidth=3.0, zorder=1)
    for i, ((num, title, note, color), x) in enumerate(zip(labels, xs)):
        ax.scatter([x], [y], s=1350, color=color, edgecolor="white", linewidth=2.2, zorder=3)
        ax.text(x, y + 0.01, num, ha="center", va="center", color="white", fontsize=18, fontweight="bold", zorder=4)
        ax.text(x, 0.91, title, ha="center", va="center", color=INK, fontsize=13, fontweight="bold")
        ax.text(x, 0.19, note, ha="center", va="center", color=INK, fontsize=9.5, linespacing=1.05)
        if i < len(labels) - 1:
            ax.annotate("", xy=(xs[i + 1] - 0.035, y), xytext=(x + 0.035, y), arrowprops=dict(arrowstyle="->", lw=2.1, color=INK), zorder=2)
    ax.text(0.5, 0.04, "Each interruption creates a local observation; repeated observations are promoted into the global writing profile.", ha="center", va="center", color=MUTED, fontsize=10.5)
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
    plot_recovery(payload)
    plot_profile_frequency(payload)
    plot_promotion_heatmap(payload)
    plot_action_mix(payload)
    plot_pipeline_image()


if __name__ == "__main__":
    main()
