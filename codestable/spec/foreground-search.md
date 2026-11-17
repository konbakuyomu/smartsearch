# 前台公开文档查询

本地 Web UI（CLI 的 ui 命令）通过 `src/smart_search/ui_api.py` 的 run_query 调用共享搜索服务，结果仍在页面现有的 JSON 视图展示。默认使用自动选路，行为与 CLI 普通 search 一致。

## 单次 Parallel 选择

- 页面提供单次服务商选择；Parallel 用于公开软件文档查询。用户每次点击真实搜索都必须确认输入可公开发送，API 要求 public_query_confirmed 为布尔 true；离线 route 不检索。
- Parallel 在 `src/smart_search/service.py` 的服务商注册表标记 explicit_only、foreground_only、route_enabled=false，不加入能力回退链或最低配置。普通 search、research、route、doctor 和探针不会因这个注册自动调用它，providers 过滤或偏好也不能启用它。
- `src/smart_search/jev_search.py` 仅在单轮、无研究计划的前台选择中提供这一渠道；沿用共享执行、时限、健康状态、证据和来源返回。显式选择不调用 Jev，不回退到其他服务商。禁用名单和冷却状态仍生效，执行器再次检查渠道可用性与原始查询。
- `src/smart_search/providers/parallel.py` 每次建立独立匿名 Unified MCP 会话，仅调用 web_search。检索参数只有固定的公开文档检索目标及用户输入的单条查询；不发送密钥、模型上下文、历史、环境配置或此前的检索会话标识。HTTP 请求携带 Smart Search 的 User-Agent，使用原有 SSL 设置，不跟随重定向。
- 结构化搜索结果或 JSON 文本结果映射为来源 URL、题名、摘录与日期。原始 HTTP(S) URL 进入普通 sources 和 content；摘录标为未读取完整页面。空结果不算健康失败；协议/工具错误、网络错误与超时沿用共享错误返回，不以成功掩盖。

## 验证入口

`tests/test_parallel_provider.py` 在 HTTP 边界使用 MockTransport，覆盖确认、查询范围、默认入口、自动渠道排除、错误、空结果与总时限。既有 UI、普通搜索和服务商测试继续覆盖默认行为。本页描述当前行为，不将真实检索结果当作事实核验。
