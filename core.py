from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
import json
import os
import re


# =========================
# 全局常量（GUI 会引用）
# =========================
SEASONS = ["秋", "春", "夏"]

# GUI 右侧按学期（含夏）
PLAN_SEMESTERS = [
    "1秋", "1春", "1夏",
    "2秋", "2春", "2夏",
    "3秋", "3春", "3夏",
    "4秋", "4春", "4夏",
]

DEFAULT_CONFIG_PATH = "config.json"

# 培养方案模块学分要求：用于“培养计划学分进度表”
PROGRAM_CREDIT_REQUIREMENTS: Dict[str, float] = {
    "思政": 18.5,
    "体育": 4.0,
    "专业必修": 33.0,
    "专业选修": 15.0,
    # 若你后续补齐通识/外语/美育/军训等课程，并在课程里标 category，可继续加：
    "大类平台": 72.5,
    "学院平台": 25.5,
    #"通识": 47.0,
    # "总计": 167.5,
}


# =========================
# 正则：学期解析
# =========================
# 课程方案学期：允许 "1秋" 或 "秋"
COURSE_SEM_RE = re.compile(r"^([1-9]\d*)?(秋|春|夏)$")
# 实际学期：必须 "1秋" 这种
ACTUAL_SEM_RE = re.compile(r"^[1-9]\d*(秋|春|夏)$")


def extract_season(semester_str: str) -> str:
    m = COURSE_SEM_RE.fullmatch(str(semester_str).strip())
    if not m:
        raise ValueError(f"非法学期标记：{semester_str}（应为 1秋/2春/秋/春/夏 等）")
    season = m.group(2)
    if season not in SEASONS:
        raise ValueError(f"非法季节：{season}")
    return season


def ensure_actual_semester(sem: str) -> str:
    sem = str(sem).strip()
    if not ACTUAL_SEM_RE.fullmatch(sem):
        raise ValueError(f"实际学期必须形如 1秋/2春/3夏，当前：{sem}")
    return sem


def season_of_actual_semester(sem: str) -> str:
    sem = ensure_actual_semester(sem)
    return sem[-1]


def validate_gpa(gpa: Optional[float]) -> Optional[float]:
    if gpa is None:
        return None
    try:
        v = float(gpa)
    except Exception:
        raise ValueError("绩点必须是数字（0~4.0）或留空。")
    if v < 0.0 or v > 4.0:
        raise ValueError("绩点必须在 0~4.0 之间。")
    return round(v, 2)


# =========================
# 数据结构
# =========================
@dataclass(frozen=True)
class Course:
    course_id: str
    name: str
    course_type: str  # "必修"/"选修"
    credits: float
    semester: str     # 方案学期：1秋/2春/... 或 秋/春/夏
    hours: Optional[str] = None
    category: str = "未分类"  # 培养方案模块分类


@dataclass
class PlanItem:
    course_id: str
    actual_semester: str  # 你实际修读的学期：1秋/2春/...
    gpa: Optional[float] = None  # 0~4.0，允许 None（尚未填写/未出分）


# =========================
# Catalog：课程目录
# =========================
class Catalog:
    def __init__(self, courses: List[Course]):
        self._by_id: Dict[str, Course] = {}
        for c in courses:
            if c.course_id in self._by_id:
                raise ValueError(f"课程编号重复：{c.course_id}")
            _ = extract_season(c.semester)  # 校验 semester 合法
            self._by_id[c.course_id] = c

    def get(self, course_id: str) -> Course:
        if course_id not in self._by_id:
            raise KeyError(f"未找到课程编号：{course_id}")
        return self._by_id[course_id]

    def all(self) -> List[Course]:
        return list(self._by_id.values())

    def required_courses(self) -> List[Course]:
        return [c for c in self._by_id.values() if c.course_type == "必修"]

    def offered_in_by_type(self, season: str) -> Dict[str, List[Course]]:
        season = str(season).strip()
        if season not in SEASONS:
            raise ValueError(f"season 必须是 {SEASONS} 之一，当前：{season}")

        req: List[Course] = []
        ele: List[Course] = []
        for c in self._by_id.values():
            if extract_season(c.semester) != season:
                continue
            (req if c.course_type == "必修" else ele).append(c)

        # 默认排序：方案学期 -> 课程号
        req.sort(key=lambda x: (x.semester, x.course_id))
        ele.sort(key=lambda x: (x.semester, x.course_id))
        return {"必修": req, "选修": ele}


# =========================
# EnrollmentPlan：选课计划 + GPA + 学分进度
# =========================
class EnrollmentPlan:
    def __init__(self, catalog: Catalog, term_credit_limit: float = 30.0, elective_credit_requirement: float = 15.0):
        self.catalog = catalog
        self.term_credit_limit = float(term_credit_limit)
        self.elective_credit_requirement = float(elective_credit_requirement)
        self.items: List[PlanItem] = []

    # ---- 基础 ----
    def has_course(self, course_id: str) -> bool:
        return any(i.course_id == course_id for i in self.items)

    def _get_item(self, course_id: str) -> PlanItem:
        for i in self.items:
            if i.course_id == course_id:
                return i
        raise KeyError("计划中没有这门课。")

    def total_credits(self) -> float:
        return sum(self.catalog.get(i.course_id).credits for i in self.items)

    def elective_credits(self) -> float:
        return sum(
            self.catalog.get(i.course_id).credits
            for i in self.items
            if self.catalog.get(i.course_id).course_type == "选修"
        )

    def required_missing(self) -> List[Course]:
        planned = {i.course_id for i in self.items}
        missing = [c for c in self.catalog.required_courses() if c.course_id not in planned]
        return sorted(missing, key=lambda x: x.course_id)

    # ---- 按实际学期 ----
    def semester_credits(self, actual_semester: str) -> float:
        actual_semester = ensure_actual_semester(actual_semester)
        return sum(
            self.catalog.get(i.course_id).credits
            for i in self.items
            if i.actual_semester == actual_semester
        )

    def courses_in_semester(self, actual_semester: str) -> List[Course]:
        actual_semester = ensure_actual_semester(actual_semester)
        courses = [self.catalog.get(i.course_id) for i in self.items if i.actual_semester == actual_semester]
        courses.sort(key=lambda x: x.course_id)
        return courses
    
    def grouped(self) -> dict[str, list[Course]]:
        """
        给可视化用：按实际学期分组，返回 { "1秋": [Course...], "1春": [...], ... }
        """
        out: dict[str, list[Course]] = {s: [] for s in PLAN_SEMESTERS}
        # 也允许出现不在 PLAN_SEMESTERS 的学期（防御）
        for it in self.items:
            c = self.catalog.get(it.course_id)
            out.setdefault(it.actual_semester, []).append(c)

        # 每学期内按课程号排序，保证稳定
        for sem in out:
            out[sem].sort(key=lambda x: x.course_id)

        return out

    # ---- GPA ----
    def get_gpa(self, course_id: str) -> Optional[float]:
        return self._get_item(course_id).gpa

    def set_gpa(self, course_id: str, gpa: Optional[float]) -> None:
        self._get_item(course_id).gpa = validate_gpa(gpa)

    def semester_gpa(self, actual_semester: str) -> Tuple[Optional[float], int]:
        actual_semester = ensure_actual_semester(actual_semester)
        term_items = [i for i in self.items if i.actual_semester == actual_semester]
        if not term_items:
            return (None, 0)

        missing = sum(1 for i in term_items if i.gpa is None)
        if missing > 0:
            return (None, missing)

        total_w = 0.0
        total_c = 0.0
        for i in term_items:
            c = self.catalog.get(i.course_id)
            total_w += float(i.gpa) * c.credits  # type: ignore[arg-type]
            total_c += c.credits

        if total_c <= 0:
            return (None, 0)

        return (round(total_w / total_c, 3), 0)
        # =========================
    # 额外 GPA 统计：总 / 专业课 / 每年
    # =========================
    def overall_gpa(self) -> Tuple[Optional[float], int]:
        """
        总 GPA：所有已选课程中 gpa 已填写的，按学分加权平均。
        返回：(gpa 或 None, 未填绩点门数)
        - 若有课程但存在未填 -> (None, missing_count)
        - 若没有任何课程 -> (None, 0)
        - 若课程都填完 -> (avg, 0)
        """
        if not self.items:
            return (None, 0)

        missing = sum(1 for it in self.items if it.gpa is None)
        if missing > 0:
            return (None, missing)

        total_w = 0.0
        total_c = 0.0
        for it in self.items:
            c = self.catalog.get(it.course_id)
            total_w += float(it.gpa) * c.credits  # type: ignore[arg-type]
            total_c += c.credits

        if total_c <= 0:
            return (None, 0)
        return (round(total_w / total_c, 3), 0)

    def major_gpa(self, major_categories: Optional[set[str]] = None) -> Tuple[Optional[float], int]:
        """
        专业课 GPA：默认只统计 category in {"专业必修","专业选修"} 的课程。
        只对这些课程要求“全部填完”才返回平均值。
        """
        if major_categories is None:
            major_categories = {"专业必修", "专业选修"}

        major_items = []
        for it in self.items:
            c = self.catalog.get(it.course_id)
            if (c.category or "未分类").strip() in major_categories:
                major_items.append(it)

        if not major_items:
            return (None, 0)

        missing = sum(1 for it in major_items if it.gpa is None)
        if missing > 0:
            return (None, missing)

        total_w = 0.0
        total_c = 0.0
        for it in major_items:
            c = self.catalog.get(it.course_id)
            total_w += float(it.gpa) * c.credits  # type: ignore[arg-type]
            total_c += c.credits

        if total_c <= 0:
            return (None, 0)
        return (round(total_w / total_c, 3), 0)

    def yearly_gpa(self) -> Dict[int, Tuple[Optional[float], int]]:
        """
        每年 GPA：按实际学期（1秋/2春/3夏/4秋）中的“年级数字”聚合。
        返回：
        {
          1: (avg_or_None, missing_count),
          2: (...),
          ...
        }
        规则：该年级若存在课程但有未填绩点 -> avg=None 且给出 missing_count
        """
        buckets: Dict[int, List[PlanItem]] = {}
        for it in self.items:
            sem = it.actual_semester
            # ensure_actual_semester 会在 add/load 时保证
            year = int(sem[:-1])  # '1秋' -> 1
            buckets.setdefault(year, []).append(it)

        out: Dict[int, Tuple[Optional[float], int]] = {}
        for year, items in sorted(buckets.items()):
            if not items:
                out[year] = (None, 0)
                continue

            missing = sum(1 for it in items if it.gpa is None)
            if missing > 0:
                out[year] = (None, missing)
                continue

            total_w = 0.0
            total_c = 0.0
            for it in items:
                c = self.catalog.get(it.course_id)
                total_w += float(it.gpa) * c.credits  # type: ignore[arg-type]
                total_c += c.credits

            if total_c <= 0:
                out[year] = (None, 0)
            else:
                out[year] = (round(total_w / total_c, 3), 0)

        return out

    # ---- 学分进度（核心接口，GUI 就靠它）----
    def credit_progress_by_category(self, requirements: Dict[str, float]) -> Dict[str, Dict[str, float]]:
        """
        progress[cat] = {"required": req, "selected": 已选, "completed": 已修}
        已修定义：该课 gpa != None
        """
        progress: Dict[str, Dict[str, float]] = {}

        for cat, req in requirements.items():
            progress[cat] = {"required": float(req), "selected": 0.0, "completed": 0.0}

        for item in self.items:
            c = self.catalog.get(item.course_id)
            cat = (c.category or "未分类").strip() or "未分类"
            if cat not in progress:
                progress[cat] = {"required": 0.0, "selected": 0.0, "completed": 0.0}

            progress[cat]["selected"] += c.credits
            if item.gpa is not None:
                progress[cat]["completed"] += c.credits

        for cat in progress:
            progress[cat]["required"] = round(progress[cat]["required"], 3)
            progress[cat]["selected"] = round(progress[cat]["selected"], 3)
            progress[cat]["completed"] = round(progress[cat]["completed"], 3)

        return progress

    def credit_progress_rows(self, requirements: Dict[str, float]) -> List[Dict[str, float | str]]:
        """
        GUI 用：返回行列表，包含 remaining
        remaining = required - completed（用已修抵扣要求）
        """
        prog = self.credit_progress_by_category(requirements)
        ordered = list(requirements.keys())
        extra = sorted([k for k in prog.keys() if k not in requirements])

        rows: List[Dict[str, float | str]] = []
        for cat in ordered + extra:
            p = prog[cat]
            required = float(p["required"])
            selected = float(p["selected"])
            completed = float(p["completed"])
            remaining = max(required - completed, 0.0)
            rows.append(
                {
                    "category": cat,
                    "required": round(required, 3),
                    "selected": round(selected, 3),
                    "completed": round(completed, 3),
                    "remaining": round(remaining, 3),
                }
            )
        return rows

    # ---- 规则动作 ----
    def add_course(self, course_id: str, actual_semester: str) -> None:
        actual_semester = ensure_actual_semester(actual_semester)
        c = self.catalog.get(course_id)

        if self.has_course(course_id):
            raise ValueError(f"重复选课：{c.course_id} {c.name}")

        # 只按季节匹配（允许跨年级）
        course_season = extract_season(c.semester)
        target_season = season_of_actual_semester(actual_semester)
        if course_season != target_season:
            raise ValueError(
                f"季节不匹配：目标 {actual_semester}（{target_season}）不能选 {c.course_id} {c.name}（课程季节={course_season}；方案学期={c.semester}）"
            )

        if self.semester_credits(actual_semester) + c.credits > self.term_credit_limit:
            raise ValueError(
                f"{actual_semester} 学分超上限：{self.semester_credits(actual_semester)} + {c.credits} > {self.term_credit_limit}"
            )

        self.items.append(PlanItem(course_id=course_id, actual_semester=actual_semester, gpa=None))

    def remove_course(self, course_id: str) -> None:
        before = len(self.items)
        self.items = [i for i in self.items if i.course_id != course_id]
        if len(self.items) == before:
            raise KeyError("计划中没有这门课。")

    def auto_add_all_required(self) -> None:
        """
        自动加入所有必修：
        - 若课程 semester 是 '2秋' 这种：放到同名实际学期
        - 若课程 semester 是 '秋'（不限定年级）：默认放到 4秋/4春/4夏
        """
        required = sorted(self.catalog.required_courses(), key=lambda x: (extract_season(x.semester), x.course_id))
        for c in required:
            if self.has_course(c.course_id):
                continue

            if ACTUAL_SEM_RE.fullmatch(c.semester):
                target = c.semester
            else:
                s = extract_season(c.semester)
                target = "4秋" if s == "秋" else ("4春" if s == "春" else "4夏")

            if target not in PLAN_SEMESTERS:
                # 防御：不在列表就放最后同季节
                target = "4秋" if target.endswith("秋") else ("4春" if target.endswith("春") else "4夏")

            self.add_course(c.course_id, target)

    def validate(self) -> List[str]:
        errors: List[str] = []
        for c in self.required_missing():
            errors.append(f"缺少必修：{c.course_id} {c.name}")

        if self.elective_credits() < self.elective_credit_requirement:
            errors.append(f"专业选修学分不足：{self.elective_credits()} < {self.elective_credit_requirement}")

        return errors


# =========================
# 默认课程（含你已有课程 + 思政 + 体育）
# =========================
def _default_courses() -> List[Course]:
    return [
        # 大类平台课程 I
        Course("60100006", "画法几何与工程制图", "必修", 3.0, "1秋", "64", category="大类平台"),
        Course("60100009", "工程思维：从创意到创新", "必修", 2.0, "1秋", "32", category="大类平台"),
        Course("60100007", "程序设计A", "必修", 2.0, "1秋", "64", category="大类平台"),
        Course("60100008", "电路与电子技术基础", "必修", 3.0, "1春", "48", category="大类平台"),
        Course("60100019", "电路与电子技术基础实验", "必修", 1.0, "1春", "32", category="大类平台"),

        # 理学大类平台课
        Course("60200029", "一元微积分", "必修", 5.0, "1秋", "80", category="大类平台"),
        Course("60200028", "线性代数", "必修", 3.0, "1秋", "48", category="大类平台"),
        Course("60200015", "多元微积分", "必修", 5.0, "1春", "80", category="大类平台"),
        Course("60200009", "大学物理A（上）", "必修", 4.5, "1春", "72", category="大类平台"),
        Course("60200017", "概率论与数理统计", "必修", 3.0, "2秋", "48", category="大类平台"),
        Course("60200016", "复变函数与积分变换", "必修", 3.0, "2秋", "48", category="大类平台"),
        Course("60200033", "大学物理A（下）", "必修", 4.5, "2秋", "72", category="大类平台"),
        Course("60200012", "大学物理实验A", "必修", 2.0, "2秋", "64", category="大类平台"),

        # 生命科学/人文社科/生态
        Course("60200045", "现代农业概论", "必修", 2.0, "1秋", "32", category="大类平台"),
        Course("60200038", "经济学原理", "必修", 2.0, "2秋", "32", category="大类平台"),
        Course("60200051", "环境评价与管理", "必修", 2.0, "1春", "32", category="大类平台"),

        # 学院平台课
        Course("13308027", "计算机系统导论", "必修", 1.0, "1秋", "32", category="学院平台"),
        Course("16308002", "专业认知", "必修", 0.5, "1秋", "16", category="学院平台"),
        Course("13308028", "离散数学I（图论和集合论）", "必修", 2.0, "1春", "32", category="学院平台"),
        Course("13308029", "程序设计II（面向对象程序设计）", "必修", 2.0, "1春", "64", category="学院平台"),
        Course("23308952", "数据结构", "必修", 3.0, "2秋", "64", category="学院平台"),
        Course("33308059", "计算机组成原理", "必修", 3.0, "2春", "64", category="学院平台"),
        Course("23308956", "数据库原理与实践", "必修", 3.0, "2春", "64", category="学院平台"),
        Course("23308940", "离散数学II（代数结构和数理逻辑）", "必修", 2.0, "2春", "32", category="学院平台"),
        Course("33308907", "操作系统", "必修", 3.0, "3秋", "64", category="学院平台"),
        Course("33308058", "计算机网络", "必修", 3.0, "3秋", "64", category="学院平台"),
        Course("33308947", "人工智能", "必修", 3.0, "3春", "64", category="学院平台"),

        # 专业必修
        Course("16308963", "网络程序设计", "必修", 2.0, "1夏", "2周", category="专业必修"),
        Course("23308934", "计算方法", "必修", 2.0, "2秋", "48", category="专业必修"),
        Course("24308945", "算法设计与分析", "必修", 2.0, "2春", "48", category="专业必修"),
        Course("26308007", "算法综合训练", "必修", 2.0, "2夏", "2周", category="专业必修"),
        Course("26308006", "计算机组成与体系结构课程设计", "必修", 2.0, "2夏", "2周", category="专业必修"),
        Course("33308932", "机器学习", "必修", 3.0, "3秋", "64", category="专业必修"),
        Course("33308905", "编译原理", "必修", 3.0, "3春", "64", category="专业必修"),
        Course("33308015", "软件工程", "必修", 2.0, "3春", "64", category="专业必修"),
        Course("33308935", "计算机体系结构", "必修", 3.0, "3秋", "64", category="专业必修"),
        Course("34308019", "数据挖掘", "必修", 1.0, "3春", "32", category="专业必修"),
        Course("36308946", "嵌入式系统综合应用实践", "必修", 1.0, "3夏", "1周", category="专业必修"),
        Course("36308006", "计算机系统工程综合实践", "必修", 2.0, "3夏", "2周", category="专业必修"),
        Course("46308907", "计算机专业毕业实习", "必修", 3.0, "4春", "3周", category="专业必修"),
        Course("46308008", "计算机专业毕业设计", "必修", 5.0, "4春", "15周", category="专业必修"),

        # 专业选修
        Course("24308006", "Python程序设计", "选修", 2.0, "2春", "32", category="专业选修"),
        Course("24308936", "计算机图形学", "选修", 2.0, "2春", "48", category="专业选修"),
        Course("34308081", "统计机器学习", "选修", 1.5, "2春", "24", category="专业选修"),
        Course("34308012", "多媒体技术与实践", "选修", 2.0, "3秋", "32", category="专业选修"),
        Course("34308901", "C#程序设计", "选修", 2.0, "3秋", "32", category="专业选修"),
        Course("34308931", "互联网技术应用与开发", "选修", 2.0, "3秋", "32", category="专业选修"),
        Course("44308002", "虚拟现实技术", "选修", 2.0, "3秋", "32", category="专业选修"),
        Course("34308018", "计算机网络安全", "选修", 2.0, "3春", "32", category="专业选修"),
        Course("35308006", "数字图像处理与实验", "选修", 2.0, "3春", "32", category="专业选修"),
        Course("34308021", "移动软件开发", "选修", 1.0, "3春", "32", category="专业选修"),
        Course("34308020", "计算机网络工程", "选修", 1.0, "4秋", "32", category="专业选修"),
        Course("46308004", "大数据应用开发综合实践", "选修", 1.0, "4秋", "32", category="专业选修"),
        Course("44308004", "软件测试", "选修", 1.0, "4秋", "16", category="专业选修"),
        Course("34308961", "统计分析及应用", "选修", 2.0, "春", "32", category="专业选修"),
        Course("34308067", "IT项目管理", "选修", 2.0, "秋", "32", category="专业选修"),

        # 思政（18.5 学分）：形势与政策拆分为秋/春，避免 course_id 重复
        Course("52313006", "思想道德与法治", "必修", 3.0, "秋", "48", category="思政"),
        Course("52313012", "中国近现代史纲要", "必修", 2.5, "秋", "40", category="思政"),
        Course("52313019", "习近平新时代中国特色社会主义思想概论", "必修", 3.0, "秋", "48", category="思政"),
        Course("52213001F", "形势与政策（秋）", "必修", 2.0, "秋", "32", category="思政"),
        Course("52313001", "马克思主义基本原理", "必修", 3.0, "春", "48", category="思政"),
        Course("52313018", "毛泽东思想和中国特色社会主义理论体系概论", "必修", 3.0, "春", "48", category="思政"),
        Course("52213001S", "形势与政策（春）", "必修", 2.0, "春", "32", category="思政"),

        # 体育：每学期两种可选
        Course("PE-F-0.5", "体育（0.5学分，可选）", "选修", 0.5, "秋", None, category="体育"),
        Course("PE-F-1.0", "体育（1学分，可选）", "选修", 1.0, "秋", None, category="体育"),
        Course("PE-S-0.5", "体育（0.5学分，可选）", "选修", 0.5, "春", None, category="体育"),
        Course("PE-S-1.0", "体育（1学分，可选）", "选修", 1.0, "春", None, category="体育"),
    ]


# =========================
# 配置文件：读写
# =========================
def load_from_config(path: str = DEFAULT_CONFIG_PATH) -> Tuple[Catalog, EnrollmentPlan]:
    """
    - config 不存在：自动生成默认（含课程目录；计划为空）
    - config 存在：读取课程 + 选课计划（含 GPA）
    """
    if not os.path.exists(path):
        data = {
            "courses": [asdict(c) for c in _default_courses()],
            "plan": {
                "term_credit_limit": 30.0,
                "elective_credit_requirement": 15.0,
                "items": [],
            },
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    raw_courses = data.get("courses", [])
    courses: List[Course] = []
    for rc in raw_courses:
        courses.append(
            Course(
                course_id=str(rc["course_id"]),
                name=str(rc["name"]),
                course_type=str(rc["course_type"]),
                credits=float(rc["credits"]),
                semester=str(rc["semester"]),
                hours=rc.get("hours"),
                category=str(rc.get("category", "未分类")),
            )
        )

    catalog = Catalog(courses)

    plan_data = data.get("plan", {})
    plan = EnrollmentPlan(
        catalog=catalog,
        term_credit_limit=float(plan_data.get("term_credit_limit", 30.0)),
        elective_credit_requirement=float(plan_data.get("elective_credit_requirement", 15.0)),
    )

    for it in plan_data.get("items", []):
        course_id = str(it["course_id"])
        actual_sem = ensure_actual_semester(str(it["actual_semester"]))
        gpa = validate_gpa(it.get("gpa", None))
        _ = catalog.get(course_id)
        plan.items.append(PlanItem(course_id=course_id, actual_semester=actual_sem, gpa=gpa))

    return catalog, plan


def save_to_config(path: str, catalog: Catalog, plan: EnrollmentPlan) -> None:
    data = {
        "courses": [asdict(c) for c in catalog.all()],
        "plan": {
            "term_credit_limit": plan.term_credit_limit,
            "elective_credit_requirement": plan.elective_credit_requirement,
            "items": [asdict(i) for i in plan.items],
        },
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
