# 未提交代码审查报告

- 审查日期：2026-08-27
- 改动文件：`merger.py`、`tests/test_kuacang_map.py`、`tests/test_mail_merge_into_master.py`
- 变更规模：3 文件，+250 / -36
- 测试结果：受影响的 2 个测试文件 **全部通过（42 passed）**

---

## 一、改动总览

1. **`build_pivot_by_delivery`（Sheet4/Sheet5 透视表）列序调整**
   - 表头与数据写入顺序由 `...工厂, B_ADDRESS1, 备注, 1, 2` 改为 `...工厂, 备注, B_ADDRESS1, 1, 2`（B_ADDRESS1 与 备注 互换）。
   - 已与下游 `merge_mail_into_master` 核对：该函数对 备注/B_ADDRESS1 采用**按表头名查找**（`_summary_col`），因此上游列序互换不会破坏邮件合并取值。✅ 一致且安全。
   - `tests/test_kuacang_map.py` 断言已同步更新（col12↔col13），`tests/test_mail_merge_into_master.py` 仅同步了 header 常量。✅

2. **新增「未发运 sheet 重排序 + SUBTOTAL」逻辑（约 175 行）**
   - `_normalize_address_for_sort(address)`：地址归一化（排序/分组用）。
   - `_restructure_weifayun_sheet(ws, factory_fallback_fill, std_border, red_font)`：对未发运 sheet 重排。
     - 901 行（工厂列=="901"）：保持原始顺序，按连续 `(状态, 地址)` 分组插 SUBTOTAL。
     - 非 901 行：按地址排序，按地址分组插 SUBTOTAL。
     - 统一细边框 / 左对齐 / 工厂色 / 「不可提」红色字体。
   - `_write_wfy_subtotal(...)`：写 L/M/N（数量/重量/业务量）的 `=SUBTOTAL(9,...)` 公式行 + 红色字体。

---

## 二、发现的问题

### 🔴 HIGH-1：核心函数 `_restructure_weifayun_sheet` 无任何单元测试覆盖
- 这是本次改动里最复杂、最易错的逻辑（排序、连续分组、SUBTOTAL 公式范围、样式注入），但**三个测试文件均未覆盖它**。
- 当前合入等于把 175 行未验证逻辑直接上线，且该函数改动的是**用户总表的最终产物**。
- **建议**：补一个测试，构造一个含 901/非901 混合、含「不可提」、含同省不同写法的 ws，断言：
  1. 901 行相对顺序不变；
  2. 非 901 行按地址升序；
  3. 每组末尾有 `=SUBTOTAL(9,Lx:Ly)` 且 L/M/N 范围正确；
  4. 「不可提」行第 7 列字体为红色加粗；
  5. 工厂列（col15）填充了回退色。

### 🔴 HIGH-2：硬编码列索引直接作用于用户上传的「总表」
- 函数内部写死：col7=状态、col11=地址、col12/13/14=数量/重量/业务量、col15=工厂。
- 该 sheet 来自**用户上传的 总表**，列序若与假定不同会**静默错位**（SUBTOTAL 汇总错列、分组基于错列）。
- 对比同文件 `merge_mail_into_master` 对 备注/B_ADDRESS1 已用 `_summary_col` **按表头名解析**，此处风格不一致。
- **建议**：函数入口按表头名解析关键列位置（至少 状态/地址/数量/重量/业务量/工厂），或加显式断言/文档声明「假定未发运 sheet 为 XX 列布局」。

### 🟡 MEDIUM-1：`_normalize_address_for_sort` 适用范围被高估
- 正则 `r'^(湖南省)([^市]+县)'` **仅处理「湖南省 + X县」**一种情形。
- 注释/函数名暗示通用「格式不一致修复」，但实际只对湖南有效；其他省份同类「省+县缺市」写法不会被归一化，导致非 901 行**分组合并不全**。
- **建议**：扩展为通用省→市推断，或把函数名/注释限定为「仅处理湖南」。

### 🟡 MEDIUM-2：import 位置与重复导入
- `import re as _re` 放在文件中部（L1490）模块级，且 `from copy import copy as _copy`、openpyxl 样式类在函数内重复 import。
- **建议**：统一移到文件顶部 import 区。

### 🟢 LOW-1：空行跳过条件可能误删极端合法行
- `all(ws.cell(r,c).value is None for c in (3,4,5,6,10,12,15))` 判定空行；若某合法数据行这 7 列恰好全空会被静默丢弃（业务上极低概率）。

### 🟢 LOW-2：字号被统一覆盖
- `_write_data_row` 把所有单元格字体重置为 `Font(size=11)`，会覆盖原始字号（可能影响行高显示），纯展示无功能影响。

### ℹ️ 静态扫描说明
- 代码审查工具在 `merger.py` 标出的 30+ 「潜在空指针」均为对 Python 的**误报**（变量已用 `if x:` 守卫），无需处理。
- 全项目唯一「严重」项为 `database.py:185` 硬编码敏感信息，**不在本次 diff**，属历史问题，建议另立 issue 处理。

---

## 三、结论与建议

**整体可合入**，但强烈建议合入前/后优先补两件事：

1. **补 `_restructure_weifayun_sheet` 的单元测试**（HIGH-1）—— 这是上线前最大的不确定性。
2. **关键列位置改为按表头解析或加断言**（HIGH-2）—— 防止用户总表列序变化导致静默错位。

`build_pivot_by_delivery` 的列序互换已验证与下游一致，测试已同步，无需担心。

其他为可读性/稳健性优化项，可随后续重构处理。
