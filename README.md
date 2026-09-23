# F1 Daily Brief

《F1与全球赛车编辑晨报》的长期 Markdown 归档仓库。

## 目录约定

每日晨报保存为：

```text
daily/YYYY/MM/YYYY-MM-DD.md
```

示例：

```text
daily/2026/09/2026-09-24.md
```

## Front Matter

每篇晨报使用以下 YAML Front Matter：

```yaml
---
title: "F1与全球赛车编辑晨报｜YYYY-MM-DD"
date: YYYY-MM-DD
timezone: Asia/Shanghai
window_start: "YYYY-MM-DD 07:00"
window_end: "YYYY-MM-DD 07:00"
type: daily-brief
---
```

## 内容规范

- Markdown 文件必须可脱离 ChatGPT 独立阅读。
- 新闻来源使用标准 Markdown 超链接，不保留 ChatGPT 专用引用标记。
- 中文译名首次出现时附英文原名。
- 合并重复转载，优先保留原始报道、官方文件和可靠补充来源。
- 对信息标注性质与可信度：官方确认、多家媒体确认、单一媒体独家、媒体分析、人物观点、旧采访再包装、未经证实传闻。
- 不以旧闻或低价值转载填充篇幅。
- F2、F3、F1学院若无实质性更新，应明确写明“今日无重大更新”。

## Commit 约定

每日新增晨报：

```text
daily: add YYYY-MM-DD morning brief
```

如当天文件已存在，应更新原文件而非创建重复归档。
