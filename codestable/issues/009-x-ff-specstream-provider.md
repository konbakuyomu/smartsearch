---
kind: issue
title: "接入 SpecStream 搜索和抓取（PR #86，作者为 SpecStream 创始人）"
type: ff
status: closed
created: 2026-11-24
---

# 接入 SpecStream 搜索和抓取（PR #86，作者为 SpecStream 创始人）

PR #86 新增 SpecStream 服务商：一个 `SPECSTREAM_API_KEY` 同时提供网页搜索（`POST /v1/web-search`）和网页抓取（`POST /v1/extract`），接进 Jev 渠道、本地兜底、`fetch`、诊断探针和字段元数据。作者的提交原样保留，评审发现的阻断项由后续修补提交补齐：四个配置键没注册，App 和网页配置页保存时被拒；新文案不在中英词表，参考页过期；PR 声明它排在两条兜底链最后，实际却有三处排在 TinyFish 之前；`doctor` 列了探针却从不调用；请求带着 Bearer Key 跟随重定向，也不看 `SSL_VERIFY`；给 Jev 的简介说搜索结果是"已核验的来源摘录"。维护者还没有 Key 做真实验证，所以标为实验性。选路规则：配了 Key 后，Jev 按中立简介和其他渠道一起打分，可能第一个选中它；本地规则兜底和 `fetch` 把它排在同能力最后。

- 改动：`src/smart_search/config.py` 注册四个 `SPECSTREAM_*` 键，超时在写入时校验，`config list` 显示这四项（Key 打码）；`src/smart_search/ui_metadata.py` 补超时字段，帮助文字写明实验性；`src/smart_search/providers/specstream.py` 不再跟随重定向（3xx 报 provider_error 并给出目标），`verify` 经构造参数传入；`src/smart_search/service.py` 在 `PROVIDER_PROFILES`、`fetch` 默认兜底列表和能力状态三处把它挪到最后并标 `experimental`，探针同时测搜索和抓取，`doctor` 调用探针并计入检索就绪；`src/smart_search/cli.py` 补 doctor 表格、显示名、`setup --advanced` 提示和回归清单；`src/smart_search/provider_descriptions.py` 改成中立的"擅长／不适合"写法；中英词表（含 macOS 副本）、README、配置和研究指南、`docs/jev-routing.md`、Skill 参考（公开和打包两份）同步，参考页重新生成；`tests/test_specstream_provider.py` 补失败路径、重定向与 TLS、顺序、探针和 Jev 派发的测试，`tests/test_provider_enablement.py` 加入 SpecStream。
- 验证：合入后全量 pytest 有 6 项失败；修补后全量 1355 passed、17 skipped，新增测试中有 17 项在 4b32e1d 上失败；`node npm/scripts/check-skill-parity.js` 通过；`scripts/generate_references.py` 重新生成后参考页与代码一致。没有 SpecStream Key，未做真实联网验证。
- codestable：已同步 `spec/index.md`（能力与选路表的网页搜索、网页抓取两行加上 SpecStream（实验性），兜底链示例改为排到 SpecStream）。
