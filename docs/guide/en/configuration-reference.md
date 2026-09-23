[Guide](../README.md) · [简体中文](../zh-CN/configuration-reference.md)

# All configuration keys

Generated from current configuration metadata. All saved keys appear below. See the [configuration guide](configuration.md) for key registration, precedence, runtime environment variables, and the minimum capability profile. Supply your own credentials; unconfigured optional providers are not enabled automatically.

## Start here

| Key | Purpose and conditions | Type / values | Default |
| --- | --- | --- | --- |
| `XAI_API_KEY` | Fill this to use xAI for main search. Either this or the OpenAI-compatible block below is enough. | `secret` | Not set |
| `XAI_API_URL` | Leave it alone unless you go through a proxy or relay. | `url` | `https://api.x.ai/v1` |
| `XAI_MODEL` | Leave empty for the default model. | `text` | `grok-4-fast` |
| `XAI_TOOLS` | Comma separated. web_search and x_search are the supported values. | `web_search, x_search` | `web_search,x_search` |
| `OPENAI_COMPATIBLE_API_URL` | Any OpenAI-protocol service works. Counts as configured only together with the key below. | `url` | Not set |
| `OPENAI_COMPATIBLE_API_KEY` | The link below is OpenAI's own. Using a relay or another provider? Get the key from them instead. | `secret` | Not set |
| `OPENAI_COMPATIBLE_MODEL` | Whatever your provider documents, e.g. gpt-4o or deepseek-chat. | `text` | Not set |
| `OPENAI_COMPATIBLE_FALLBACK_MODELS` | Comma separated. Tried in order when the main model is unavailable. | `csv` | Not set |
| `OPENAI_COMPATIBLE_API_MODE` | Most services want chat-completions. | `chat-completions, responses` | `chat-completions` |
| `OPENAI_COMPATIBLE_STREAM` | Some services only think for long under streaming. | `bool` | `false` |
| `XAI_ENABLED` | Disabling keeps the configuration and stops requests. Takes effect after saving changes. | `bool` | `true` |
| `OPENAI_COMPATIBLE_ENABLED` | Disabling keeps the configuration and stops requests. Takes effect after saving changes. | `bool` | `true` |

## Providers

| Key | Purpose and conditions | Type / values | Default |
| --- | --- | --- | --- |
| `EXA_API_KEY` | One of the two options for docs search. | `secret` | Not set |
| `EXA_BASE_URL` | Base URL for Exa. Keep the official default unless using a relay; omit /search. | `url` | `https://api.exa.ai` |
| `EXA_TIMEOUT_SECONDS` | Maximum seconds to wait for one response from this service. A timeout returns an error or uses the configured fallback; normally leave the default. | `float` | `30` |
| `CONTEXT7_API_KEY` | Looks up open-source library docs. The other docs-search option. | `secret` | Not set |
| `CONTEXT7_BASE_URL` | Context7 base URL. Library-search and documentation paths are added automatically. | `url` | `https://context7.com` |
| `CONTEXT7_TIMEOUT_SECONDS` | Maximum seconds to wait for one response from this service. A timeout returns an error or uses the configured fallback; normally leave the default. | `float` | `30` |
| `ZHIPU_API_KEY` | Good at recent Chinese-language content. Optional; things run without it. | `secret` | Not set |
| `ZHIPU_API_URL` | Base URL for Zhipu web search. Keep /api; the search endpoint is added automatically. | `url` | `https://open.bigmodel.cn/api` |
| `ZHIPU_SEARCH_ENGINE` | search_std, search_pro, search_pro_sogou, search_pro_quark, or a custom one. | `text` | `search_std` |
| `ZHIPU_TIMEOUT_SECONDS` | Maximum seconds to wait for one response from this service. A timeout returns an error or uses the configured fallback; normally leave the default. | `float` | `30` |
| `ZHIPU_MCP_API_KEY` | One key serves both search and page fetching; the reader side satisfies the minimum profile. | `secret` | Not set |
| `ZHIPU_MCP_SEARCH_API_URL` | Full MCP endpoint for this Zhipu Coding Plan service. Keep the trailing /mcp; do not enter the website home page. | `url` | `https://open.bigmodel.cn/api/mcp/web_search_prime/mcp` |
| `ZHIPU_MCP_READER_API_URL` | Full MCP endpoint for this Zhipu Coding Plan service. Keep the trailing /mcp; do not enter the website home page. | `url` | `https://open.bigmodel.cn/api/mcp/web_reader/mcp` |
| `ZHIPU_MCP_ZREAD_API_URL` | Full MCP endpoint for this Zhipu Coding Plan service. Keep the trailing /mcp; do not enter the website home page. | `url` | `https://open.bigmodel.cn/api/mcp/zread/mcp` |
| `ZHIPU_MCP_TIMEOUT_SECONDS` | Maximum seconds to wait for one response from this service. A timeout returns an error or uses the configured fallback; normally leave the default. | `float` | `30` |
| `JINA_API_KEY` | Turns a page into clean text. Anonymous use does not satisfy the minimum profile. | `secret` | Not set |
| `JINA_READER_API_URL` | Jina Reader service URL. The target page URL is appended automatically. | `url` | `https://r.jina.ai` |
| `JINA_RESPOND_WITH` | Optional, e.g. readerlm-v2. | `text` | Not set |
| `JINA_TIMEOUT_SECONDS` | Maximum seconds to wait for one response from this service. A timeout returns an error or uses the configured fallback; normally leave the default. | `float` | `30` |
| `TAVILY_API_KEY` | Does both search and fetching, so one key covers two capabilities. | `secret` | Not set |
| `TAVILY_API_URL` | Tavily base URL. Keep the default for the official service; change only for a relay. | `url` | `https://api.tavily.com` |
| `TAVILY_ENABLED` | Disabling keeps the configuration and stops requests. Takes effect after saving changes. | `bool` | `true` |
| `TAVILY_TIMEOUT_SECONDS` | Maximum seconds to wait for one response from this service. A timeout returns an error or uses the configured fallback; normally leave the default. | `float` | `30` |
| `FIRECRAWL_API_KEY` | Optional search and fetch provider. The current check only confirms a key is present, not credential or API availability. | `secret` | Not set |
| `FIRECRAWL_API_URL` | Firecrawl base URL including /v2. Keep the default for the official service. | `url` | `https://api.firecrawl.dev/v2` |
| `TINYFISH_API_KEY` | One key enables search and page fetching. Testing makes one real request for each capability. | `secret` | Not set |
| `TINYFISH_SEARCH_API_URL` | TinyFish search service URL, separate from its page-fetching service. Usually unchanged. | `url` | `https://api.search.tinyfish.ai` |
| `TINYFISH_FETCH_API_URL` | TinyFish page-fetching service URL, separate from search. Usually unchanged. | `url` | `https://api.fetch.tinyfish.ai` |
| `TINYFISH_TIMEOUT_SECONDS` | Maximum seconds to wait for one response from this service. A timeout returns an error or uses the configured fallback; normally leave the default. | `float` | `150` |
| `ANYSEARCH_API_KEY` | Vertical-domain search. Experimental. | `secret` | Not set |
| `ANYSEARCH_API_URL` | Full AnySearch MCP endpoint including /mcp, not the website home page. | `url` | `https://api.anysearch.com/mcp` |
| `ANYSEARCH_TIMEOUT_SECONDS` | Maximum seconds to wait for one response from this service. A timeout returns an error or uses the configured fallback; normally leave the default. | `float` | `30` |
| `SCIVERSE_API_TOKEN` | Academic paper search. Experimental, and only used when asked for explicitly. | `secret` | Not set |
| `SCIVERSE_API_URL` | Sciverse paper-search service URL. Keep the default for the official service. | `url` | `https://api.sciverse.space` |
| `SCIVERSE_TIMEOUT_SECONDS` | Maximum seconds to wait for one response from this service. A timeout returns an error or uses the configured fallback; normally leave the default. | `float` | `30` |
| `CONTEXT7_ENABLED` | Disabling keeps the configuration and stops requests. Takes effect after saving changes. | `bool` | `true` |
| `EXA_ENABLED` | Disabling keeps the configuration and stops requests. Takes effect after saving changes. | `bool` | `true` |
| `ZHIPU_ENABLED` | Disabling keeps the configuration and stops requests. Takes effect after saving changes. | `bool` | `true` |
| `ZHIPU_MCP_ENABLED` | Disabling keeps the configuration and stops requests. Takes effect after saving changes. | `bool` | `true` |
| `ZHIPU_MCP_READER_ENABLED` | Disabling keeps the configuration and stops requests. Takes effect after saving changes. | `bool` | `true` |
| `FIRECRAWL_ENABLED` | Disabling keeps the configuration and stops requests. Takes effect after saving changes. | `bool` | `true` |
| `TINYFISH_ENABLED` | Disabling keeps the configuration and stops requests. Takes effect after saving changes. | `bool` | `true` |
| `JINA_ENABLED` | Disabling keeps the configuration and stops requests. Takes effect after saving changes. | `bool` | `true` |
| `ANYSEARCH_ENABLED` | Disabling keeps the configuration and stops requests. Takes effect after saving changes. | `bool` | `true` |
| `SCIVERSE_ENABLED` | Disabling keeps the configuration and stops requests. Takes effect after saving changes. | `bool` | `true` |

## Intent routing

| Key | Purpose and conditions | Type / values | Default |
| --- | --- | --- | --- |
| `SMART_SEARCH_INTENT_ROUTER` | jev selects channels and evaluates evidence with its own key; hybrid combines rules and models; rules uses rules only; off disables routing. | `hybrid, jev, off, rules` | `hybrid` |
| `TYPESAFE_API_KEY` | Separate credentials for optional semantic routing; adding a key does not switch modes. | `secret` | Not set |
| `TYPESAFE_API_URL` | TypeSafe base URL for JEV mode only. Defaults to https://api.typesafe.ai/v1; /systemone is added automatically. This is not a search-provider URL. | `url` | `https://api.typesafe.ai/v1` |
| `TYPESAFE_MODEL` | TypeSafe model identifier for judging channels and evidence, separate from the main search model. Usually leave the default. | `text` | `jev-latest` |
| `SMART_SEARCH_JEV_TIMEOUT_SECONDS` | Maximum seconds to wait for one response from this service. A timeout returns an error or uses the configured fallback; normally leave the default. | `float` | `15` |
| `SMART_SEARCH_JEV_MAX_ROUNDS` | Maximum retrieval and evidence-review rounds. More rounds can increase time and cost. | `int` | `3` |
| `SMART_SEARCH_JEV_MAX_CHANNELS` | Maximum retrieval channels per round. Larger values may generate more requests. | `int` | `3` |
| `SMART_SEARCH_JEV_RESULTS_PER_CHANNEL` | Requested results per retrieval channel. Usually leave the default. | `int` | `5` |
| `SMART_SEARCH_JEV_ROUTE_THRESHOLD` | From 0 to 1. A channel must meet this suitability score to be selected; higher values select fewer channels. | `float` | `0.5` |
| `SMART_SEARCH_JEV_SUFFICIENCY_THRESHOLD` | From 0 to 1. Stop retrieving when evidence reaches this sufficiency score; higher values demand more evidence. | `float` | `0.75` |
| `SMART_SEARCH_JEV_FILTER_RESULTS` | Adds judgment calls; overall cost savings are not guaranteed. | `bool` | `false` |
| `SMART_SEARCH_JEV_FILTER_THRESHOLD` | From 0 to 1, used only when evidence filtering is enabled. Results below this relevance score are filtered. | `float` | `0.1` |
| `SMART_SEARCH_JEV_SYNTHESIZE` | false returns evidence; auto decides whether to summarize; true always summarizes. Synthesis only uses the dedicated model. | `false, auto, true` | `false` |
| `SMART_SEARCH_JEV_SYNTHESIS_API_URL` | Optional separate OpenAI-compatible endpoint. Also provide its key and model. | `url` | Not set |
| `SMART_SEARCH_JEV_SYNTHESIS_API_KEY` | Used only for JEV final synthesis, not retrieval or Jev judgments. | `secret` | Not set |
| `SMART_SEARCH_JEV_SYNTHESIS_MODEL` | Dedicated synthesis model; URL, key and model must be set together. | `text` | Not set |
| `SMART_SEARCH_JEV_SYNTHESIS_API_MODE` | Choose chat-completions or responses for the dedicated synthesis endpoint; it must match the service API. | `chat-completions, responses` | `chat-completions` |
| `INTENT_EMBEDDING_API_URL` | Optional full embedding endpoint including /v1/embeddings. It identifies required capabilities, not search answers. Enabled in hybrid mode when URL, key and model are all set. | `url` | Not set |
| `INTENT_EMBEDDING_API_KEY` | Key issued by the embedding service. It must match the endpoint and model; leave empty to disable embedding-based routing. | `secret` | Not set |
| `INTENT_EMBEDDING_MODEL` | Exact embedding model identifier, for example BAAI/bge-m3. This is not a chat model; use an identifier supported by the endpoint. | `text` | Not set |
| `INTENT_EMBEDDING_THRESHOLD` | Between 0 and 1. | `float` | `0.74` |
| `INTENT_EMBEDDING_MARGIN` | Between 0 and 1. | `float` | `0.05` |
| `INTENT_CLASSIFIER_API_URL` | Optional full chat endpoint including /v1/chat/completions for query classification. Enabled in hybrid mode when URL, key and model are all set; rules still work when omitted. | `url` | Not set |
| `INTENT_CLASSIFIER_API_KEY` | Key for the classifier endpoint. The main search key is not automatically reused. | `secret` | Not set |
| `INTENT_CLASSIFIER_MODEL` | Chat model identifier for classification. It must support JSON output at this endpoint and is configured separately from the main search model. | `text` | Not set |
| `INTENT_ROUTER_TIMEOUT_SECONDS` | Maximum seconds to wait for one response from this service. A timeout returns an error or uses the configured fallback; normally leave the default. | `float` | `8` |
| `SMART_SEARCH_RESEARCH_PREFERRED_PROVIDERS` | Comma-separated provider ids to prefer during deep research. | `csv` | Not set |
| `SMART_SEARCH_RESEARCH_DISABLED_PROVIDERS` | Comma-separated provider ids to keep out of deep research entirely. | `csv` | Not set |

## Timeouts and fallback

| Key | Purpose and conditions | Type / values | Default |
| --- | --- | --- | --- |
| `SMART_SEARCH_VALIDATION_LEVEL` | strict checks harder and runs slower. | `balanced, fast, strict` | `balanced` |
| `SMART_SEARCH_FALLBACK_MODE` | auto moves on to the next provider when one fails. | `auto, off` | `auto` |
| `SMART_SEARCH_MINIMUM_PROFILE` | standard refuses to run when any of the three required capabilities is missing. | `off, standard` | `standard` |
| `SMART_SEARCH_TIMEOUT_SECONDS` | Ceiling for one whole search. Raise it when a reasoning model is slow. | `float` | `300` |
| `SMART_SEARCH_PROVIDER_COOLDOWN_SECONDS` | How long a failing provider is skipped. 0 disables cooldown. | `float` | `900` |
| `SMART_SEARCH_PROVIDER_FAILURE_THRESHOLD` | Consecutive soft failures before cooldown. Auth errors cool down on the first one regardless. | `int` | `2` |
| `SMART_SEARCH_RETRY_MAX_ATTEMPTS` | Maximum attempts per request, including the first attempt. Larger values can prolong failures. | `int` | `3` |
| `SMART_SEARCH_RETRY_MULTIPLIER` | Backoff multiplier for retry delays. Keep the default to avoid retrying too aggressively. | `float` | `1` |
| `SMART_SEARCH_RETRY_MAX_WAIT` | Maximum delay between retries in seconds, not the total search time limit. | `int` | `10` |

## Logging and debugging

| Key | Purpose and conditions | Type / values | Default |
| --- | --- | --- | --- |
| `SMART_SEARCH_LANGUAGE` | Language for the independent CLI. Choose the App language separately in its settings. | `auto, zh, en` | `auto` |
| `SMART_SEARCH_DEBUG` | Enable extra troubleshooting output. Use when diagnosing a problem; this does not validate API keys. | `bool` | `false` |
| `SMART_SEARCH_LOG_LEVEL` | Log verbosity: DEBUG, INFO, WARNING or ERROR. INFO is suitable for normal use. | `text` | `INFO` |
| `SMART_SEARCH_LOG_DIR` | Directory used when file logging is enabled. Absolute paths are allowed; relative paths use the configuration file directory. | `text` | `logs` |
| `SMART_SEARCH_LOG_TO_FILE` | Write runtime logs to the log directory. Disable to avoid writing log files. | `bool` | `false` |
| `SMART_SEARCH_OUTPUT_CLEANUP` | Clean unnecessary markers from output text. This does not delete configuration, log or result files. | `bool` | `true` |
| `SSL_VERIFY` | Turning this off should only ever be a temporary debugging step. | `bool` | `true` |
