from __future__ import annotations

import re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import tkinter.font as tkfont

from core import (
    Catalog,
    EnrollmentPlan,
    SEASONS,
    DEFAULT_CONFIG_PATH,
    load_from_config,
    save_to_config,
    PROGRAM_CREDIT_REQUIREMENTS,
)

try:
    from viz import plot_plan
except Exception:
    plot_plan = None


# ============================================================
# 学期 UI：强制包含夏季
# ============================================================
_SEASON_ORDER = {"秋": 0, "春": 1, "夏": 2}


def _build_semesters_ui(max_year: int = 4) -> list[str]:
    out = []
    for y in range(1, max_year + 1):
        out.extend([f"{y}秋", f"{y}春", f"{y}夏"])
    return out


SEMESTERS_UI = _build_semesters_ui(4)


# ============================================================
# 排序工具：方案学期排序 + refresh 后恢复
# ============================================================
_PLAN_SEM_RE = re.compile(r"^(\d+)(秋|春|夏)$")


def _plan_sem_key(s: str):
    if s is None:
        return (9999, 9, "")
    t = str(s).strip()
    m = _PLAN_SEM_RE.fullmatch(t)
    if m:
        year = int(m.group(1))
        season = m.group(2)
        return (year, _SEASON_ORDER.get(season, 9), "")
    return (9999, _SEASON_ORDER.get(t, 9), t)


def _coerce_sort_value(col: str, v: str):
    if v is None:
        return ""
    s = str(v).strip()
    if s == "":
        return ""
    if col == "plan_sem":
        return _plan_sem_key(s)
    if col in ("credits", "gpa", "required", "selected", "completed", "remaining"):
        try:
            return float(s)
        except ValueError:
            return s
    return s


def attach_sortable_headings(tv: ttk.Treeview) -> None:
    tv._sort_state = {"col": None, "desc": False}

    def do_sort(col: str, toggle: bool):
        items = list(tv.get_children(""))
        col_index = tv["columns"].index(col)

        data = []
        for idx, iid in enumerate(items):
            values = tv.item(iid, "values")
            val = values[col_index] if col_index < len(values) else ""
            data.append((iid, _coerce_sort_value(col, val), idx))  # idx 保证稳定

        if toggle:
            if tv._sort_state["col"] == col:
                tv._sort_state["desc"] = not tv._sort_state["desc"]
            else:
                tv._sort_state["col"] = col
                tv._sort_state["desc"] = False
        else:
            tv._sort_state["col"] = col

        desc = tv._sort_state["desc"]
        data.sort(key=lambda x: (x[1], x[2]), reverse=desc)
        for new_index, (iid, _val, _idx) in enumerate(data):
            tv.move(iid, "", new_index)

    def sort_by(col: str):
        do_sort(col, toggle=True)

    def restore_sort():
        col = tv._sort_state.get("col")
        if col:
            do_sort(col, toggle=False)

    tv.restore_sort = restore_sort

    for col in tv["columns"]:
        tv.heading(col, command=lambda c=col: sort_by(c))


def make_tree_with_vscroll(parent: ttk.Frame, *, columns: tuple[str, ...], show="headings", height=12) -> ttk.Treeview:
    """
    关键修复：Treeview 必须在 parent 里创建（master=parent），否则容易被 wrap 覆盖导致“空白表格”。
    """
    parent.columnconfigure(0, weight=1)
    parent.rowconfigure(0, weight=1)

    tv = ttk.Treeview(parent, columns=columns, show=show, height=height)
    sb = ttk.Scrollbar(parent, orient="vertical", command=tv.yview)
    tv.configure(yscrollcommand=sb.set)

    tv.grid(row=0, column=0, sticky="nsew")
    sb.grid(row=0, column=1, sticky="ns")
    return tv


# ============================================================
# 左侧：季节浏览
# ============================================================
class SeasonBrowseTab(ttk.Frame):
    def __init__(self, master, *, season: str, catalog: Catalog, plan: EnrollmentPlan, get_target_semester, on_change):
        super().__init__(master, padding=10)
        self.season = season
        self.catalog = catalog
        self.plan = plan
        self.get_target_semester = get_target_semester
        self.on_change = on_change

        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.rowconfigure(3, weight=1)

        ttk.Label(self, text="必修可选（双击添加）").grid(row=0, column=0, sticky="w", pady=(0, 4))

        req_wrap = ttk.Frame(self)
        req_wrap.grid(row=1, column=0, sticky="nsew")
        self.tv_req = make_tree_with_vscroll(req_wrap, columns=("id", "name", "credits", "plan_sem"), height=10)
        self._init_available_tv(self.tv_req)
        attach_sortable_headings(self.tv_req)
        self.tv_req.bind("<Double-1>", lambda _e: self._add_from_tree(self.tv_req))

        ttk.Label(self, text="选修可选（双击添加）").grid(row=2, column=0, sticky="w", pady=(10, 4))

        ele_wrap = ttk.Frame(self)
        ele_wrap.grid(row=3, column=0, sticky="nsew")
        self.tv_ele = make_tree_with_vscroll(ele_wrap, columns=("id", "name", "credits", "plan_sem"), height=10)
        self._init_available_tv(self.tv_ele)
        attach_sortable_headings(self.tv_ele)
        self.tv_ele.bind("<Double-1>", lambda _e: self._add_from_tree(self.tv_ele))

        btnrow = ttk.Frame(self)
        btnrow.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(btnrow, text="添加选中课程 →", command=self._add_selected).pack(side=tk.LEFT)

        ttk.Label(self, text="提示：右侧先选择目标学期（如 2夏），再在左侧双击添加。").grid(row=5, column=0, sticky="w", pady=(10, 0))

    def _init_available_tv(self, tv: ttk.Treeview) -> None:
        tv.heading("id", text="课程编号")
        tv.heading("name", text="课程名称")
        tv.heading("credits", text="学分")
        tv.heading("plan_sem", text="方案学期")
        tv.column("id", width=110, anchor="w")
        tv.column("name", width=360, anchor="w")
        tv.column("credits", width=70, anchor="w")
        tv.column("plan_sem", width=90, anchor="w")

    def _add_selected(self) -> None:
        if self.tv_req.selection():
            self._add_from_tree(self.tv_req)
            return
        if self.tv_ele.selection():
            self._add_from_tree(self.tv_ele)
            return
        messagebox.showinfo("提示", "请先选中一门课程。")

    def refresh(self) -> None:
        req_sort = getattr(self.tv_req, "_sort_state", {}).copy()
        ele_sort = getattr(self.tv_ele, "_sort_state", {}).copy()

        for iid in self.tv_req.get_children():
            self.tv_req.delete(iid)
        for iid in self.tv_ele.get_children():
            self.tv_ele.delete(iid)

        offered = self.catalog.offered_in_by_type(self.season)
        req_list = sorted(offered["必修"], key=lambda c: (_plan_sem_key(c.semester), c.course_id))
        ele_list = sorted(offered["选修"], key=lambda c: (_plan_sem_key(c.semester), c.course_id))

        for c in req_list:
            self.tv_req.insert(
                "", tk.END,
                values=(c.course_id, c.name, f"{c.credits:g}", c.semester),
                tags=("already",) if self.plan.has_course(c.course_id) else ()
            )
        for c in ele_list:
            self.tv_ele.insert(
                "", tk.END,
                values=(c.course_id, c.name, f"{c.credits:g}", c.semester),
                tags=("already",) if self.plan.has_course(c.course_id) else ()
            )

        try:
            self.tv_req.tag_configure("already", foreground="#777777")
            self.tv_ele.tag_configure("already", foreground="#777777")
        except Exception:
            pass

        if req_sort.get("col"):
            self.tv_req._sort_state = req_sort
            self.tv_req.restore_sort()
        if ele_sort.get("col"):
            self.tv_ele._sort_state = ele_sort
            self.tv_ele.restore_sort()

    def _add_from_tree(self, tv: ttk.Treeview) -> None:
        sel = tv.selection()
        if not sel:
            return
        course_id = tv.item(sel[0], "values")[0]
        target_sem = self.get_target_semester()
        if not target_sem:
            messagebox.showerror("无法添加", "请先在右侧选择一个目标学期（如 2夏 / 3秋）。")
            return
        try:
            self.plan.add_course(course_id, target_sem)
        except Exception as e:
            messagebox.showerror("添加失败", str(e))
            return

        self.refresh()
        self.on_change()


# ============================================================
# 右侧：按实际学期（含夏）+ GPA
# ============================================================
class ActualSemesterPlanPanel(ttk.Frame):
    def __init__(self, master, *, semesters: list[str], catalog: Catalog, plan: EnrollmentPlan, on_change):
        super().__init__(master, padding=10)
        self.semesters = semesters
        self.catalog = catalog
        self.plan = plan
        self.on_change = on_change
        self.current_semester = tk.StringVar(value=self.semesters[0])

        self._build_ui()
        self.refresh_all()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.nb = ttk.Notebook(self)
        self.nb.grid(row=0, column=0, sticky="nsew")
        self.tables: dict[str, tuple[ttk.Treeview, tk.StringVar]] = {}

        for sem in self.semesters:
            tab = ttk.Frame(self.nb, padding=10)
            tab.columnconfigure(0, weight=1)
            tab.rowconfigure(0, weight=1)

            wrap = ttk.Frame(tab)
            wrap.grid(row=0, column=0, sticky="nsew")

            tv = make_tree_with_vscroll(
                wrap,
                columns=("id", "name", "type", "credits", "plan_sem", "gpa"),
                height=18
            )
            tv.heading("id", text="课程编号")
            tv.heading("name", text="课程名称")
            tv.heading("type", text="类型")
            tv.heading("credits", text="学分")
            tv.heading("plan_sem", text="方案学期")
            tv.heading("gpa", text="绩点")

            tv.column("id", width=110, anchor="w")
            tv.column("name", width=360, anchor="w")
            tv.column("type", width=70, anchor="w")
            tv.column("credits", width=70, anchor="w")
            tv.column("plan_sem", width=90, anchor="w")
            tv.column("gpa", width=70, anchor="w")

            attach_sortable_headings(tv)
            tv.bind("<Double-1>", lambda _e, s=sem: self._edit_gpa_in(s))
            # 让鼠标点一下表格就获得键盘焦点（否则按退格可能没反应）
            tv.bind("<Button-1>", lambda e, t=tv: (t.focus_set(), None), add=True)

            # BackSpace / Delete 删除选中课程
            tv.bind("<BackSpace>", lambda e, s=sem: self._remove_selected_in(s), add=True)
            tv.bind("<Delete>", lambda e, s=sem: self._remove_selected_in(s), add=True)

            btnrow = ttk.Frame(tab)
            btnrow.grid(row=1, column=0, sticky="ew", pady=(10, 0))
            ttk.Button(btnrow, text="设置/修改绩点", style="Small.TButton", command=lambda s=sem: self._edit_gpa_in(s)).pack(side=tk.LEFT)
            ttk.Button(btnrow, text="清空绩点", style="Small.TButton", command=lambda s=sem: self._clear_gpa_in(s)).pack(side=tk.LEFT, padx=(8, 0))
            ttk.Button(btnrow, text="删除选中课程", style="Small.TButton", command=lambda s=sem: self._remove_selected_in(s)).pack(side=tk.RIGHT)

            summary_var = tk.StringVar(value="")
            ttk.Label(tab, textvariable=summary_var, justify="left").grid(row=2, column=0, sticky="ew", pady=(8, 0))

            self.nb.add(tab, text=sem)
            self.tables[sem] = (tv, summary_var)

        self.nb.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _on_tab_changed(self, _e=None) -> None:
        idx = self.nb.index(self.nb.select())
        self.current_semester.set(self.semesters[idx])

    def get_current_semester(self) -> str:
        return self.current_semester.get()

    def refresh_all(self) -> None:
        for sem in self.semesters:
            self.refresh_one(sem)

    def refresh_one(self, sem: str) -> None:
        tv, summary_var = self.tables[sem]
        sort_state = getattr(tv, "_sort_state", {}).copy()

        for iid in tv.get_children():
            tv.delete(iid)

        courses = self.plan.courses_in_semester(sem)
        for c in courses:
            g = self.plan.get_gpa(c.course_id)
            g_str = "" if g is None else f"{g:g}"
            tv.insert("", tk.END, values=(c.course_id, c.name, c.course_type, f"{c.credits:g}", c.semester, g_str))

        if sort_state.get("col"):
            tv._sort_state = sort_state
            tv.restore_sort()

        tc = self.plan.semester_credits(sem)
        avg, missing = self.plan.semester_gpa(sem)
        if avg is None:
            if missing > 0:
                gpa_line = f"{sem} 学期总绩点：未完成（还差 {missing} 门未填）"
            else:
                gpa_line = f"{sem} 学期总绩点：暂无（本学期未选课）"
        else:
            gpa_line = f"{sem} 学期总绩点（学分加权）：{avg:.3f}"

        summary_var.set(f"{sem} 已选学分：{tc:g} / 上限 {self.plan.term_credit_limit:g}\n{gpa_line}")

    def _get_selected_course_id(self, sem: str) -> str | None:
        tv, _ = self.tables[sem]
        sel = tv.selection()
        if not sel:
            return None
        return tv.item(sel[0], "values")[0]

    def _edit_gpa_in(self, sem: str) -> None:
        course_id = self._get_selected_course_id(sem)
        if not course_id:
            messagebox.showinfo("提示", "请先选中一门课程，再设置绩点。")
            return

        c = self.catalog.get(course_id)
        current = self.plan.get_gpa(course_id)

        s = simpledialog.askstring(
            "设置绩点",
            f"课程：{c.course_id} {c.name}\n请输入绩点（0~4.0），留空表示未出分：",
            initialvalue="" if current is None else str(current),
            parent=self
        )
        if s is None:
            return

        s = s.strip()
        try:
            if s == "":
                self.plan.set_gpa(course_id, None)
            else:
                self.plan.set_gpa(course_id, float(s))
        except Exception as e:
            messagebox.showerror("设置失败", str(e))
            return

        self.refresh_one(sem)
        self.on_change()

    def _clear_gpa_in(self, sem: str) -> None:
        course_id = self._get_selected_course_id(sem)
        if not course_id:
            return
        c = self.catalog.get(course_id)

        if not messagebox.askyesno("确认", f"确定清空绩点：{c.course_id} {c.name}？"):
            return
        try:
            self.plan.set_gpa(course_id, None)
        except Exception as e:
            messagebox.showerror("清空失败", str(e))
            return

        self.refresh_one(sem)
        self.on_change()

    def _remove_selected_in(self, sem: str) -> None:
        course_id = self._get_selected_course_id(sem)
        if not course_id:
            return
        c = self.catalog.get(course_id)

        if not messagebox.askyesno("确认删除", f"确定从【{sem}】删除：{c.course_id} {c.name}？"):
            return
        try:
            self.plan.remove_course(course_id)
        except Exception as e:
            messagebox.showerror("删除失败", str(e))
            return

        self.refresh_one(sem)
        self.on_change()


# ============================================================
# 主窗口
# ============================================================
class CourseSelectionApp(tk.Tk):
    def __init__(self, config_path: str = DEFAULT_CONFIG_PATH):
        super().__init__()
        self.title("选课与绩点记录（含夏季学期 + 学分进度总表）")
        self.geometry("1650x930")

        self.config_path = config_path
        self.catalog, self.plan = load_from_config(self.config_path)

        self._init_styles()
        self._build_ui()
        self._refresh_all()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _init_styles(self) -> None:
        style = ttk.Style(self)

        # Tab 字体：复制一份，不改 TkDefaultFont（避免把按钮/其它控件也弄大）
        base = tkfont.nametofont("TkDefaultFont")
        tab_font = base.copy()
        tab_font.configure(size=max(base.cget("size"), 11), weight="bold")

        style.configure("TNotebook.Tab", padding=(18, 8), font=tab_font)
        style.configure("Small.TButton", padding=(10, 4))

    def _build_ui(self) -> None:
        for w in self.winfo_children():
            w.destroy()

        root = ttk.Frame(self, padding=10)
        root.pack(fill=tk.BOTH, expand=True)
        root.columnconfigure(0, weight=1)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(1, weight=1)

        top = ttk.Frame(root)
        top.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))

        ttk.Button(top, text="打开配置…", style="Small.TButton", command=self._open_config).pack(side=tk.LEFT)
        ttk.Button(top, text="保存", style="Small.TButton", command=self._save_config).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(top, text="另存为…", style="Small.TButton", command=self._save_as).pack(side=tk.LEFT, padx=(8, 0))

        ttk.Button(top, text="自动加入全部必修", style="Small.TButton", command=self._auto_required).pack(side=tk.LEFT, padx=(24, 0))
        ttk.Button(top, text="校验规则", style="Small.TButton", command=self._validate).pack(side=tk.LEFT, padx=(8, 0))

        if plot_plan is not None:
            ttk.Button(top, text="可视化", style="Small.TButton", command=self._visualize).pack(side=tk.LEFT, padx=(8, 0))

        mid = ttk.Frame(root)
        mid.grid(row=1, column=0, columnspan=2, sticky="nsew")
        mid.columnconfigure(0, weight=1)
        mid.columnconfigure(1, weight=1)
        mid.rowconfigure(0, weight=1)

        left = ttk.Labelframe(mid, text="可选课程（按季节；默认按方案学期排序；选课后保持排序）", padding=10)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)

        self.nb_season = ttk.Notebook(left)
        self.nb_season.grid(row=0, column=0, sticky="nsew")

        right = ttk.Labelframe(mid, text="选课计划与绩点（按 1秋/1春/1夏/… 分学期）", padding=10)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)

        self.plan_panel = ActualSemesterPlanPanel(
            right,
            semesters=SEMESTERS_UI,
            catalog=self.catalog,
            plan=self.plan,
            on_change=self._refresh_all
        )
        self.plan_panel.grid(row=0, column=0, sticky="nsew")

        self.season_tabs = {}
        for season in SEASONS:
            tab = SeasonBrowseTab(
                self.nb_season,
                season=season,
                catalog=self.catalog,
                plan=self.plan,
                get_target_semester=self.plan_panel.get_current_semester,
                on_change=self._refresh_all
            )
            self.nb_season.add(tab, text=season)
            self.season_tabs[season] = tab

        bottom = ttk.Labelframe(root, text="培养计划学分进度（总学分 / 已选 / 已修=已填绩点 / 剩余）", padding=10)
        bottom.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(10, 0))
        bottom.columnconfigure(0, weight=1)
        bottom.rowconfigure(0, weight=1)

        prog_wrap = ttk.Frame(bottom)
        prog_wrap.grid(row=0, column=0, sticky="nsew")

        self.progress_tv = make_tree_with_vscroll(
            prog_wrap,
            columns=("category", "required", "selected", "completed", "remaining"),
            height=7
        )
        self.progress_tv.heading("category", text="模块")
        self.progress_tv.heading("required", text="培养计划总学分")
        self.progress_tv.heading("selected", text="已选学分")
        self.progress_tv.heading("completed", text="已修学分")
        self.progress_tv.heading("remaining", text="剩余学分")
        self.progress_tv.column("category", width=220, anchor="w")
        self.progress_tv.column("required", width=140, anchor="e")
        self.progress_tv.column("selected", width=120, anchor="e")
        self.progress_tv.column("completed", width=120, anchor="e")
        self.progress_tv.column("remaining", width=120, anchor="e")
        attach_sortable_headings(self.progress_tv)

        self.summary_var = tk.StringVar(value="")
        ttk.Label(root, textvariable=self.summary_var, justify="left").grid(row=3, column=0, columnspan=2, sticky="ew", pady=(10, 0))

    # -------------------------
    # 刷新
    # -------------------------
    def _refresh_all(self) -> None:
        for tab in self.season_tabs.values():
            tab.refresh()
        self.plan_panel.refresh_all()
        self._refresh_progress_table()
        self._refresh_summary()

    def _refresh_progress_table(self) -> None:
        for iid in self.progress_tv.get_children():
            self.progress_tv.delete(iid)

        if hasattr(self.plan, "credit_progress_rows"):
            rows = self.plan.credit_progress_rows(PROGRAM_CREDIT_REQUIREMENTS)
            for r in rows:
                self.progress_tv.insert(
                    "", tk.END,
                    values=(
                        r["category"],
                        f"{float(r['required']):g}",
                        f"{float(r['selected']):g}",
                        f"{float(r['completed']):g}",
                        f"{float(r['remaining']):g}",
                    )
                )
            return

        # 兜底
        self.progress_tv.insert("", tk.END, values=("（core.py 未提供进度接口）", "", "", "", ""))

    def _refresh_summary(self) -> None:
        total = self.plan.total_credits()
        elective = self.plan.elective_credits()
        missing_req = len(self.plan.required_missing())

        # 学期 GPA 概览
        gpa_parts = []
        for sem in SEMESTERS_UI:
            avg, miss = self.plan.semester_gpa(sem)
            if avg is not None:
                gpa_parts.append(f"{sem}:{avg:.3f}")
            else:
                if self.plan.semester_credits(sem) > 0 and miss > 0:
                    gpa_parts.append(f"{sem}:缺{miss}")
        gpa_str = "  ".join(gpa_parts) if gpa_parts else "（暂无或未填完）"

        # 总 GPA
        overall_avg, overall_missing = self.plan.overall_gpa()
        if overall_avg is None:
            overall_str = f"未完成（缺 {overall_missing} 门）" if overall_missing > 0 else "暂无"
        else:
            overall_str = f"{overall_avg:.3f}"

        # 专业课 GPA
        major_avg, major_missing = self.plan.major_gpa()
        if major_avg is None:
            major_str = f"未完成（缺 {major_missing} 门）" if major_missing > 0 else "暂无"
        else:
            major_str = f"{major_avg:.3f}"

        # 每年 GPA
        yearly = self.plan.yearly_gpa()
        yearly_parts = []
        for y in sorted(yearly.keys()):
            avg, miss = yearly[y]
            if avg is None:
                s = f"{y}年:未完成(缺{miss})" if miss > 0 else f"{y}年:暂无"
            else:
                s = f"{y}年:{avg:.3f}"
            yearly_parts.append(s)
        yearly_str = "  ".join(yearly_parts) if yearly_parts else "（暂无）"

        self.summary_var.set(
            f"当前配置文件：{self.config_path}\n"
            f"课程学分合计（已选）：{total:g}    专业选修学分：{elective:g} / {self.plan.elective_credit_requirement:g}    缺少必修：{missing_req} 门\n"
            f"总 GPA：{overall_str}    专业课 GPA：{major_str}    每年 GPA：{yearly_str}\n"
            f"学期总绩点（完成后显示；未完成显示缺几门）：{gpa_str}\n"
            f"每学期学分上限：{self.plan.term_credit_limit:g}"
        )


    # -------------------------
    # config 读写
    # -------------------------
    def _open_config(self) -> None:
        path = filedialog.askopenfilename(
            title="打开配置文件",
            filetypes=[("JSON files", "*.json")],
            initialfile=DEFAULT_CONFIG_PATH,
        )
        if not path:
            return
        try:
            catalog, plan = load_from_config(path)
        except Exception as e:
            messagebox.showerror("打开失败", str(e))
            return
        self.config_path = path
        self.catalog, self.plan = catalog, plan
        self._build_ui()
        self._refresh_all()

    def _save_config(self) -> None:
        try:
            save_to_config(self.config_path, self.catalog, self.plan)
        except Exception as e:
            messagebox.showerror("保存失败", str(e))
            return
        messagebox.showinfo("已保存", f"已保存到：{self.config_path}")

    def _save_as(self) -> None:
        path = filedialog.asksaveasfilename(
            title="另存为配置文件",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            initialfile="config.json",
        )
        if not path:
            return
        try:
            save_to_config(path, self.catalog, self.plan)
        except Exception as e:
            messagebox.showerror("保存失败", str(e))
            return
        self.config_path = path
        messagebox.showinfo("已保存", f"已保存到：{self.config_path}")
        self._refresh_summary()

    def _on_close(self) -> None:
        if messagebox.askyesno("退出", "退出前是否保存当前配置？"):
            try:
                save_to_config(self.config_path, self.catalog, self.plan)
            except Exception as e:
                messagebox.showerror("保存失败", str(e))
                return
        self.destroy()

    # -------------------------
    # 规则动作
    # -------------------------
    def _auto_required(self) -> None:
        try:
            self.plan.auto_add_all_required()
        except Exception as e:
            messagebox.showerror("自动加入必修失败", str(e))
            return
        self._refresh_all()

    def _validate(self) -> None:
        errs = self.plan.validate()
        if not errs:
            messagebox.showinfo("校验通过", "当前计划满足已配置规则：必修已全、选修学分达标。")
        else:
            messagebox.showwarning("校验未通过", "\n".join(f"- {x}" for x in errs))

    def _visualize(self) -> None:
        if plot_plan is None:
            messagebox.showerror("不可用", "未找到 viz.py 或 plot_plan(plan)。")
            return
        try:
            plot_plan(self.plan)
        except Exception as e:
            messagebox.showerror("可视化失败", str(e))


if __name__ == "__main__":
    app = CourseSelectionApp(DEFAULT_CONFIG_PATH)
    app.mainloop()
