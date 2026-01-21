# Course-Selection-and-GPA-Calculator
# 选课与绩点记录系统

本项目是一个本地桌面端 GUI 程序，用于基于培养方案进行选课、记录绩点，并自动统计学分进度与 GPA（学期/总/专业课/每年），支持可视化展示。

---

## 功能概览

- **课程库与培养方案**
  - 课程信息包含：课程编号、名称、必修/选修、学分、方案学期（如 `2秋`）、学时、模块分类（`category`）。
  - 支持思政课程与体育课程（体育含 0.5/1.0 学分可选项）。

- **按学期选课（含夏季）**
  - 右侧按学期 Tab：`1秋/1春/1夏 ... 4秋/4春/4夏`。
  - 支持跨年级选课：按“秋/春/夏”季节匹配即可（但仍保留方案学期显示）。

- **绩点记录与 GPA 统计**
  - 每门课可录入 GPA（0.0 ~ 4.0，允许留空）。
  - 自动计算：
    - **每学期 GPA**（学分加权；若缺绩点显示缺几门）
    - **总 GPA**
    - **专业课 GPA**（默认统计 `专业必修 + 专业选修`）
    - **每学年 GPA**（按实际学期年级 1/2/3/4 汇总）

- **培养计划学分进度表**
  - 显示各模块：培养计划总学分 / 已选学分 / 已修学分 / 剩余学分
  - “已修学分”默认口径：**绩点已填写**的课程学分

- **排序与快捷操作**
  - 点击表头：按该列排序（升/降序切换）
  - 右侧选课表：选中课程后按 **Backspace/Delete** 可删除

- **可视化**
  - 提供图表（含中文字体设置）：
    - 每学期 GPA 柱状图
    - 每学年 GPA 柱状图
  - 如系统未正确显示中文，请参考“常见问题”。

---

## 运行环境

- Python 3.10+（推荐 3.11）
- 标准库：`tkinter`（Windows/macOS 通常自带；部分 Linux 需安装 Tk）
- 可视化模块若使用 Matplotlib：需要安装 `matplotlib`

安装 Matplotlib（若未安装）：

```bash
pip install matplotlib


---

## 快速开始

1. 进入项目目录
2. 运行：

```bash
python main.py
```

首次运行若当前目录不存在 `config.json`，程序会自动生成默认 `config.json`。

---

## 使用说明

### 1）打开/保存配置

* **打开配置**：选择已有 `config.json`，加载课程库与选课记录
* **保存**：将当前选课与绩点写回当前配置文件
* **另存为**：保存为新的 JSON 文件（适用于不同学院/不同方案）

> 提示：`config.json` 的生成/读取位置与“你运行程序的工作目录”有关。建议始终在项目目录下运行。

### 2）左侧课程库浏览

* 按季节 Tab 浏览：秋 / 春 / 夏
* 每页通常按必修/选修区分
* 选中一门课后，可添加到右侧当前学期（具体交互以界面按钮/双击为准）

### 3）右侧按学期选课（含夏季）

* 在右侧选择目标学期 Tab（例如 `2春` 或 `1夏`）
* 从左侧选择课程并添加
* **跨年级选课**：只要季节匹配即可

  * 例如方案学期 `2秋` 的课程可以加入 `1秋`（你实际修读的秋季学期）

### 4）删除课程

* 右侧已选课程表中选中一行：

  * 点击“删除”按钮，或
  * 按 **Backspace/Delete**



### 5）录入绩点（GPA）

* 在右侧学期表中对课程录入 GPA（0~4.0）
* GPA 未填时：

  * 学期 GPA / 总 GPA / 专业课 GPA / 每年 GPA 会显示“未完成（缺 N 门）”

### 6）查看统计信息

* **底部摘要栏**：显示已选学分、选修学分完成情况、缺少必修、各类 GPA
* **培养计划学分进度表**：按模块展示 required/selected/completed/remaining

---

## 配置文件说明（config.json）

### 顶层结构

```json
{
  "courses": [ ... ],
  "plan": {
    "term_credit_limit": 30.0,
    "elective_credit_requirement": 15.0,
    "items": [ ... ]
  }
}
```

### courses（课程库）

每门课示例：

```json
{
  "course_id": "33308907",
  "name": "操作系统",
  "course_type": "必修",
  "credits": 3,
  "semester": "3秋",
  "hours": "64",
  "category": "学院平台"
}
```

字段说明：

* `semester`：方案学期（`1秋/2春/1夏` 或 `秋/春/夏`）
* `category`：用于学分进度统计、专业课 GPA 统计（很重要）

### plan.items（选课记录 + 绩点）

```json
{
  "course_id": "33308907",
  "actual_semester": "3秋",
  "gpa": 3.7
}
```

* `actual_semester` 必须是 `N秋/N春/N夏`
* `gpa` 可为 `null`（未填）

---

## 可视化说明

点击“可视化”后会生成图表窗口（Matplotlib）：

* 每学期 GPA 柱状图
* 每学年 GPA 柱状图

若中文显示为方块/乱码，请看下节“常见问题”。

---

## 常见问题（FAQ）

### 1）可视化中文显示为方块/乱码

原因：Matplotlib 未找到系统中文字体。

解决：

* Windows 推荐安装/使用 **Microsoft YaHei** 或 **SimHei**
* 程序内已尝试自动选择常见字体；若仍不行，可在 `viz.py` 中强制指定字体，例如：

```python
import matplotlib as mpl
mpl.rcParams["font.family"] = "Microsoft YaHei"
mpl.rcParams["axes.unicode_minus"] = False
```

### 2）学分进度表出现“未分类”学分很大

原因：`config.json` 里的课程条目缺少 `category` 或为空。

解决：

* 确保 `courses` 中每门课都有 `category`
* 重新加载/保存一次配置（若程序包含迁移补全逻辑，会自动写回）

### 3）按 Backspace 无法删除

原因：右侧表格未获得焦点。

解决：

* 先用鼠标点击右侧表格中的课程行，再按 Backspace/Delete。

### 4）运行时报错找不到 tkinter

原因：系统 Python 未包含 Tk 支持（多见于部分 Linux 环境）。

解决：

* 安装 Tk 依赖（Ubuntu 例）：

```bash
sudo apt-get install python3-tk
```

---

## 项目文件说明

* `main.py`：程序入口（启动 GUI）
* `gui.py`：界面与交互逻辑
* `core.py`：数据结构、规则、统计、config 读写
* `viz.py`：可视化（若存在）
* `config.json`：课程库 + 选课与绩点数据

---

## 数据备份建议

`config.json` 是你的全部数据（课程 + 选课 + GPA）。建议定期备份：

* `config.json` → `config.backup.YYYYMMDD.json`

---

## 许可

如无特殊声明，默认仅供学习/个人使用。

