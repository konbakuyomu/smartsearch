---
kind: issue
title: "接入 SpecStream 搜索和抓取（PR #86，作者为 SpecStream 创始人）"
type: ff
status: open
created: 2026-11-24
---

# 接入 SpecStream 搜索和抓取（PR #86，作者为 SpecStream 创始人）

PR #86 合入整合分支，先原样保留作者提交，再由后续提交补齐评审时发现的阻断项（配置键、词表、参考页、回退顺序、诊断探针、重定向与 TLS、描述措辞、文档）。

- 改动：`src/smart_search/providers/specstream.py` 等，见 PR #86 的 diff。修补进行中：四个 `SPECSTREAM_*` 键已注册，超时加入写入校验和字段元数据，新文案进了中英词表，配置指南加了 SpecStream 一行；三处回退顺序改到最后并标为实验性，`doctor` 接上同时测搜索和抓取的探针，请求不再跟随重定向并按 `SSL_VERIFY` 校验证书。
- 验证：合并后全量 pytest 有 6 项失败（配置键未注册、词表、参考页、字段计数）；注册配置键并重新生成参考页后全量 1314 passed、17 skipped。
- codestable：已知漂移：SpecStream 还没写进 `codestable/spec/`，修补提交里同步。
