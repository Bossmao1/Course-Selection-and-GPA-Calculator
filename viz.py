from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib as mpl


def _setup_cn_font() -> None:
    """设置中文字体 + 负号显示。尽量跨平台。"""
    mpl.rcParams["axes.unicode_minus"] = False

    candidates = [
        "Microsoft YaHei",        # Windows
        "SimHei",                 # Windows
        "PingFang SC",            # macOS
        "Heiti SC",               # macOS
        "Noto Sans CJK SC",       # Linux
        "Source Han Sans SC",     # 思源黑体
        "WenQuanYi Zen Hei",      # Linux
    ]

    from matplotlib.font_manager import FontProperties, findfont

    for name in candidates:
        try:
            fp = FontProperties(family=name)
            path = findfont(fp, fallback_to_default=False)
            if path and path.lower().endswith((".ttf", ".ttc", ".otf")):
                mpl.rcParams["font.family"] = name
                return
        except Exception:
            pass
    # 找不到就继续用默认字体（但可能仍乱码）


def _collect_semester_gpa(plan) -> tuple[list[str], list[float], list[str]]:
    """
    返回：
    - labels: ['1秋','1春',...]
    - values: 对应柱子高度（未完成用 0）
    - notes: 备注（'' 或 '缺N门'）
    只包含“该学期已选学分 > 0”的学期。
    """
    # 这里不强依赖 core.py 的 PLAN_SEMESTERS 常量，用 GUI 常见顺序
    semesters = []
    for y in range(1, 5):
        semesters.extend([f"{y}秋", f"{y}春", f"{y}夏"])

    labels: list[str] = []
    values: list[float] = []
    notes: list[str] = []

    for sem in semesters:
        try:
            c = plan.semester_credits(sem)
        except Exception:
            continue

        if c <= 0:
            continue

        avg, missing = plan.semester_gpa(sem)
        labels.append(sem)
        if avg is None:
            values.append(0.0)
            notes.append(f"缺{missing}门" if missing > 0 else "暂无")
        else:
            values.append(float(avg))
            notes.append("")

    return labels, values, notes


def _collect_yearly_gpa(plan) -> tuple[list[str], list[float], list[str]]:
    """
    返回：
    - labels: ['1年','2年',...]
    - values: 对应柱子高度（未完成用 0）
    - notes: 备注（'' 或 '缺N门'）
    只包含“该年有选课记录”的年。
    """
    ymap = plan.yearly_gpa()  # {1: (avg_or_none, missing), ...}

    labels: list[str] = []
    values: list[float] = []
    notes: list[str] = []

    for y in sorted(ymap.keys()):
        avg, missing = ymap[y]
        labels.append(f"{y}年")
        if avg is None:
            values.append(0.0)
            notes.append(f"缺{missing}门" if missing > 0 else "暂无")
        else:
            values.append(float(avg))
            notes.append("")

    return labels, values, notes


def plot_gpa_bars(plan) -> None:
    """
    生成两张柱状图：
    1) 每学期 GPA
    2) 每学年 GPA
    """
    _setup_cn_font()

    # ====== Figure A：每学期 GPA ======
    sem_labels, sem_values, sem_notes = _collect_semester_gpa(plan)

    if sem_labels:
        plt.figure()
        bars = plt.bar(sem_labels, sem_values)
        plt.ylim(0, 4.0)
        plt.title("每学期绩点（学分加权）")
        plt.xlabel("学期")
        plt.ylabel("GPA")

        # 文字标注：数值或“缺N门”
        for rect, val, note in zip(bars, sem_values, sem_notes):
            x = rect.get_x() + rect.get_width() / 2
            y = rect.get_height()
            if note:
                plt.text(x, y + 0.05, note, ha="center", va="bottom")
            else:
                plt.text(x, y + 0.05, f"{val:.3f}", ha="center", va="bottom")

        plt.xticks(rotation=45)
        plt.tight_layout()
    else:
        plt.figure()
        plt.title("每学期绩点（学分加权）")
        plt.text(0.5, 0.5, "暂无可统计学期（请先选课）", ha="center", va="center")
        plt.axis("off")
        plt.tight_layout()

    # ====== Figure B：每学年 GPA ======
    year_labels, year_values, year_notes = _collect_yearly_gpa(plan)

    if year_labels:
        plt.figure()
        bars = plt.bar(year_labels, year_values)
        plt.ylim(0, 4.0)
        plt.title("每学年绩点（学分加权）")
        plt.xlabel("学年")
        plt.ylabel("GPA")

        for rect, val, note in zip(bars, year_values, year_notes):
            x = rect.get_x() + rect.get_width() / 2
            y = rect.get_height()
            if note:
                plt.text(x, y + 0.05, note, ha="center", va="bottom")
            else:
                plt.text(x, y + 0.05, f"{val:.3f}", ha="center", va="bottom")

        plt.tight_layout()
    else:
        plt.figure()
        plt.title("每学年绩点（学分加权）")
        plt.text(0.5, 0.5, "暂无可统计学年（请先选课）", ha="center", va="center")
        plt.axis("off")
        plt.tight_layout()

    plt.show()


# 兼容 GUI：如果 GUI 点“可视化”调用 plot_plan(plan)，就让它同时画 GPA 图
def plot_plan(plan) -> None:
    """
    你如果原来已有其它可视化（例如学期学分柱状图、必修/选修饼图），
    可以把它们放在这里，然后最后调用 plot_gpa_bars(plan)。
    这里为了保证功能完整，至少提供 GPA 两张图。
    """
    plot_gpa_bars(plan)
