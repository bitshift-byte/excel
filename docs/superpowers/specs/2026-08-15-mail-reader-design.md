# 邮件读取器设计文档

- 日期：2026-08-15
- 状态：已确认，待实现

## 目标

定时从 126 邮箱读取邮件，按「日期 + 主题关键词」筛选，捞出 Excel 附件，自动跑现有系统的「合并 + 省份筛选」流程，产出结果 Excel 并归档。

## 非目标

- 不做邮件正文/HTML 解析
- 不做发件人筛选（仅主题关键词 + 日期）
- 不做多账号管理（单账号）
- 不改动现有网页功能的行为

## 架构

方案 A：独立邮件脚本 + 复用合并核心。

```
app.py              # 现有，微调：/api/process 改为调用 merger.py（消除重复逻辑，行为不变）
merger.py           # 新增：从 app.py 抽出的合并核心（纯函数）
mail_reader.py      # 新增：邮件读取 + 定时轮询 + 调用 merger
mail_config.json    # 新增：邮箱授权码、关键词、省份、日期范围、轮询间隔
processed_uids.json # 运行时生成：已处理邮件 UID（去重）
```

依赖：邮件读取全用标准库（`imaplib`/`email`/`json`/`time`/`datetime`），**零新增依赖**。合并核心复用现有 `openpyxl`/`xlrd`。

## 组件

### 1. merger.py（合并核心，纯函数）

从 `app.py` 的 `/api/process` 抽出主合并流程，暴露：

```python
def merge_files(files, selected_sheets, provinces, rule_id, output_dir) -> dict
    # 返回 {output_path, stats, filtered_rows}
```

复用并迁移以下现有纯函数：
- `read_all_sheets`、`_parse_sheet_rows`、`_detect_file_type`、`_read_text_table`
- `match_columns_to_rule`、`apply_value_mappings`
- `build_pivot_by_delivery`、`build_pivot_by_factory_delivery`
- `match_row_province`、`match_province`、`build_region_keywords`
- `serialize_cell`、`_to_number`、`_format_date_text`、`_try_parse_date`

`app.py` 的 `/api/process` 改为调用 `merger.merge_files`，保证现有网页功能行为不变。

### 2. mail_reader.py（邮件读取器）

- 连接 `imap.126.com`（SSL 993），用「客户端授权码」登录（非网页密码）
- 日期筛选：IMAP `SINCE <日期>`（日期默认今天）
- 关键词筛选：客户端本地过滤，`subject_keywords` 任一关键词出现在主题即命中（OR 关系，包含匹配）。原因：IMAP SUBJECT 搜索对中文关键词支持不稳定，本地过滤更可靠
- 下载 `xlsx/xls/csv/tsv` 附件到临时目录
- 调 `merger.merge_files()`（省份从配置读，空数组 = 全量合并）
- 结果 Excel 写入 `output/`，文件名带日期
- 处理成功后把邮件 UID 写入 `processed_uids.json`（去重）
- 定时循环：`while True` + `time.sleep`（默认 3600 秒）

### 3. mail_config.json（配置）

```json
{
  "imap_host": "imap.126.com",
  "email": "账号@126.com",
  "auth_code": "客户端授权码",
  "subject_keywords": ["总表", "月报"],
  "provinces": [],
  "days_back": 1,
  "poll_interval_seconds": 3600,
  "output_dir": "output"
}
```

## 数据流

```
定时循环（默认 1 小时）
  → IMAP 搜「SINCE 今天 + 主题含关键词」邮件（不管已读未读）
  → 过滤掉 processed_uids.json 里已处理过的 UID
  → 下载 Excel 附件到临时目录
  → merger.merge_files（全量合并 + 省份筛选）
  → 结果 Excel 写入 output/
  → 记录 UID 到 processed_uids.json + 清理临时文件
  → 等待下一轮
```

## 去重机制

- 因「不管已读未读」，不能靠已读标记去重。
- 用本地 `processed_uids.json` 记录已处理邮件的 IMAP UID。
- 每轮搜索后先排除已记录的 UID，避免重复处理。
- 跨天：`days_back: 1` 每天 0 点后「今天」自动变为新一天，旧邮件不再匹配。

## 错误处理

- 邮箱连接失败 / 授权码错误：打日志 + 重试，不退出
- 附件非 Excel 或损坏：跳过该附件，记录日志
- 合并无有效数据：记录日志，仍记录 UID（避免每轮重复失败）
- 单封邮件异常：不影响其他邮件处理

## 测试

- `merger.py`：抽取后跑一次真实合并，与现有 `/api/process` 输出对比，行为一致
- `mail_reader.py`：IMAP 部分用 mock 测（不连真实邮箱）

## 默认值

| 项 | 默认 |
|---|---|
| 轮询间隔 | 3600 秒（1 小时） |
| 日期范围 | `days_back: 1`（今天） |
| 省份 | 空数组（全量合并） |
| 去重 | 本地 UID 记录 |
