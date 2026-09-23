[手册目录](../README.md) · [English](../en/cli-reference.md)

# 完整命令参考

由当前命令解析器生成。用法示例和退出码见 [CLI 使用指南](cli.md)。`--lang` 可放在命令前或子命令后；`--` 后面的文字按原始参数处理。

## `smart-search`

```text
用法：smart-search [-h] [--lang {auto,zh,en}] [-v]
                {agent-guide,search,s,route,rt,route-calibrate,route-cal,rcal,fetch,f,map,m,exa-search,exa,x,exa-similar,xs,zhipu-search,z,zp,zhipu-mcp-search,zmcp-search,zhipu-mcp-reader,zmcp-reader,zhipu-mcp-search-doc,zmcp-doc,zhipu-mcp-repo-structure,zmcp-tree,zhipu-mcp-read-file,zmcp-file,anysearch-domains,as-domains,anysearch-search,as-search,as,anysearch-extract,as-extract,anysearch-batch,as-batch,sciverse-catalog,sv-catalog,sciverse-search,sv-search,sv,sciverse-semantic,sv-semantic,sciverse-read,sv-read,sciverse-relations,sv-relations,context7-library,c7,ctx7,context7-docs,c7d,c7docs,ctx7-docs,deep,dr,research,rs,smoke,sm,doctor,d,diagnose,diag,model,mdl,skills,skill,providers,prov,ui,web,setup,init,config,cfg,regression,reg} ...

供 AI 联网研究使用的 Smart Search 命令行工具。

位置参数:
  {agent-guide,search,s,route,rt,route-calibrate,route-cal,rcal,fetch,f,map,m,exa-search,exa,x,exa-similar,xs,zhipu-search,z,zp,zhipu-mcp-search,zmcp-search,zhipu-mcp-reader,zmcp-reader,zhipu-mcp-search-doc,zmcp-doc,zhipu-mcp-repo-structure,zmcp-tree,zhipu-mcp-read-file,zmcp-file,anysearch-domains,as-domains,anysearch-search,as-search,as,anysearch-extract,as-extract,anysearch-batch,as-batch,sciverse-catalog,sv-catalog,sciverse-search,sv-search,sv,sciverse-semantic,sv-semantic,sciverse-read,sv-read,sciverse-relations,sv-relations,context7-library,c7,ctx7,context7-docs,c7d,c7docs,ctx7-docs,deep,dr,research,rs,smoke,sm,doctor,d,diagnose,diag,model,mdl,skills,skill,providers,prov,ui,web,setup,init,config,cfg,regression,reg}
    agent-guide         读取当前 CLI 提供给 Agent 的使用说明。
    search (s)          运行 OpenAI 兼容接口联网搜索。
    route (rt)          解释意图路由，不运行服务商。
    route-calibrate (route-cal, rcal)
                        评估向量意图路由模型并推荐阈值和间距。
    fetch (f)           将 URL 抓取为 Markdown。
    map (m)             生成网站结构图。
    exa-search (exa, x)
                        通过 Exa 优先发现来源。
    exa-similar (xs)    用 Exa 查找与 URL 相似的页面。
    zhipu-search (z, zp)
                        通过智谱 Web Search 优先发现来源。
    zhipu-mcp-search (zmcp-search)
                        运行智谱 Coding Plan Remote MCP web_search_prime。
    zhipu-mcp-reader (zmcp-reader)
                        运行智谱 Coding Plan Remote MCP webReader。
    zhipu-mcp-search-doc (zmcp-doc)
                        通过智谱 Coding Plan zread MCP 搜索仓库文档。
    zhipu-mcp-repo-structure (zmcp-tree)
                        通过智谱 Coding Plan zread MCP 读取仓库结构。
    zhipu-mcp-read-file (zmcp-file)
                        通过智谱 Coding Plan zread MCP 读取仓库文件。
    anysearch-domains (as-domains)
                        列出 AnySearch 垂直搜索领域。
    anysearch-search (as-search, as)
                        运行实验性 AnySearch 垂直或通用搜索。
    anysearch-extract (as-extract)
                        通过 AnySearch 实验接口抽取 URL。
    anysearch-batch (as-batch)
                        并行执行最多 5 条 AnySearch 查询。
    sciverse-catalog (sv-catalog)
                        列出 Sciverse 学术元数据字段（当前 API 仅支持 papers）。
    sciverse-search (sv-search, sv)
                        显式运行实验性 Sciverse 结构化学术检索。
    sciverse-semantic (sv-semantic)
                        显式运行实验性 Sciverse 语义论文检索。
    sciverse-read (sv-read)
                        按 doc_id 读取 Sciverse 文档片段。
    sciverse-relations (sv-relations)
                        按 unique_id 列出 Sciverse 论文关系；CITATIONS
                        是引用目标论文的论文，REFERENCES 是目标论文引用的论文。
    context7-library (c7, ctx7)
                        查找 Context7 库候选。
    context7-docs (c7d, c7docs, ctx7-docs)
                        读取库的 Context7 文档。
    deep (dr)           生成离线深度研究计划，不调用服务商。
    research (rs)       执行在线深度研究，按服务商专长路由，并只根据证据综合回答。
    smoke (sm)          运行服务商路由与回退冒烟检查。
    doctor (d)          显示脱敏配置与连接检查。
    diagnose (diag)     针对某个服务商进行定向排障。
    model (mdl)         查看显式配置的服务商模型；通过 config set XAI_MODEL 或
                        OPENAI_COMPATIBLE_MODEL 修改。
    skills (skill)      检查或更新已安装的 smart-search-cli 技能。
    providers (prov)    查看或清除可选服务商持久保存的失败冷却。
    ui (web)            打开临时本地页面，查看配置并测试服务商 Key。
    setup (init)        交互式保存本机服务商配置。
    config (cfg)        读取或编辑本机 Smart Search 配置文件。
    regression (reg)    运行离线 CLI 回归测试。

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  -v, --v, --version    显示程序版本并退出
```

## `smart-search agent-guide`

```text
用法：smart-search agent-guide [-h] [--lang {auto,zh,en}] [section]

位置参数:
  section

选项:
  -h, --help           显示此帮助并退出
  --lang {auto,zh,en}  本次调用的界面语言，不改变已保存的偏好。
```

## `smart-search search`

别名：`s`

```text
用法：smart-search search [-h] [--lang {auto,zh,en}] [--platform PLATFORM]
                       [--model MODEL] [--extra-sources EXTRA_SOURCES]
                       [--validation {fast,balanced,strict}]
                       [--fallback {auto,off}] [--providers PROVIDERS]
                       [--stream | --no-stream] [--timeout SECONDS]
                       [--format {json,markdown,content}] [--output OUTPUT]
                       query

位置参数:
  query

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  --platform PLATFORM
  --model MODEL
  --extra-sources EXTRA_SOURCES
  --validation {fast,balanced,strict}
  --fallback {auto,off}
  --providers PROVIDERS
  --stream              为 OpenAI 兼容主搜索使用 stream=true。
  --no-stream           强制 OpenAI 兼容主搜索使用 stream=false。
  --timeout SECONDS     搜索总时间预算，单位秒；覆盖 SMART_SEARCH_TIMEOUT_SECONDS。
  --format {json,markdown,content}
  --output OUTPUT       将渲染后的输出写入文件。
```

解析器默认值：`--platform` = ``; `--model` = ``; `--extra-sources` = `0`; `--validation` = ``; `--fallback` = ``; `--providers` = `auto`; `--no-stream` = `True`; `--format` = `json`; `--output` = ``.

## `smart-search route`

别名：`rt`

```text
用法：smart-search route [-h] [--lang {auto,zh,en}]
                      [--validation {fast,balanced,strict}] [--remote]
                      [--router-mode {hybrid,rules,off,jev}]
                      [--format {json,markdown,content}] [--output OUTPUT]
                      query

位置参数:
  query

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  --validation {fast,balanced,strict}
  --remote              显式允许远程路由判断，可能产生 API 费用，不执行检索。
  --router-mode {hybrid,rules,off,jev}
                        仅为本次诊断覆盖 SMART_SEARCH_INTENT_ROUTER。
  --format {json,markdown,content}
  --output OUTPUT       将渲染后的输出写入文件。
```

解析器默认值：`--validation` = ``; `--remote` = `False`; `--router-mode` = ``; `--format` = `json`; `--output` = ``.

## `smart-search route-calibrate`

别名：`route-cal`, `rcal`

```text
用法：smart-search route-calibrate [-h] [--lang {auto,zh,en}] [--models MODELS]
                                [--format {json,markdown,content}]
                                [--output OUTPUT]

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  --models MODELS       向量模型名称，用逗号分隔。默认使用已知候选和已配置的模型。
  --format {json,markdown,content}
  --output OUTPUT       将渲染后的输出写入文件。
```

解析器默认值：`--models` = ``; `--format` = `json`; `--output` = ``.

## `smart-search fetch`

别名：`f`

```text
用法：smart-search fetch [-h] [--lang {auto,zh,en}]
                      [--format {json,markdown,content}] [--output OUTPUT]
                      url

位置参数:
  url

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  --format {json,markdown,content}
  --output OUTPUT       将渲染后的输出写入文件。
```

解析器默认值：`--format` = `json`; `--output` = ``.

## `smart-search map`

别名：`m`

```text
用法：smart-search map [-h] [--lang {auto,zh,en}] [--instructions INSTRUCTIONS]
                    [--max-depth MAX_DEPTH] [--max-breadth MAX_BREADTH]
                    [--limit LIMIT] [--timeout TIMEOUT]
                    [--format {json,markdown,content}] [--output OUTPUT]
                    url

位置参数:
  url

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  --instructions INSTRUCTIONS
  --max-depth MAX_DEPTH
  --max-breadth MAX_BREADTH
  --limit LIMIT
  --timeout TIMEOUT
  --format {json,markdown,content}
  --output OUTPUT       将渲染后的输出写入文件。
```

解析器默认值：`--instructions` = ``; `--max-depth` = `1`; `--max-breadth` = `20`; `--limit` = `50`; `--timeout` = `150`; `--format` = `json`; `--output` = ``.

## `smart-search exa-search`

别名：`exa`, `x`

```text
用法：smart-search exa-search [-h] [--lang {auto,zh,en}]
                           [--num-results NUM_RESULTS]
                           [--search-type {neural,keyword,auto}]
                           [--include-text] [--include-highlights]
                           [--start-published-date START_PUBLISHED_DATE]
                           [--include-domains INCLUDE_DOMAINS [INCLUDE_DOMAINS ...]]
                           [--exclude-domains EXCLUDE_DOMAINS [EXCLUDE_DOMAINS ...]]
                           [--category CATEGORY]
                           [--format {json,markdown,content}]
                           [--output OUTPUT]
                           query

位置参数:
  query

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  --num-results NUM_RESULTS
  --search-type {neural,keyword,auto}
  --include-text
  --include-highlights
  --start-published-date START_PUBLISHED_DATE
  --include-domains INCLUDE_DOMAINS [INCLUDE_DOMAINS ...]
  --exclude-domains EXCLUDE_DOMAINS [EXCLUDE_DOMAINS ...]
  --category CATEGORY
  --format {json,markdown,content}
  --output OUTPUT       将渲染后的输出写入文件。
```

解析器默认值：`--num-results` = `5`; `--search-type` = `neural`; `--include-text` = `False`; `--include-highlights` = `False`; `--start-published-date` = ``; `--include-domains` = ``; `--exclude-domains` = ``; `--category` = ``; `--format` = `json`; `--output` = ``.

## `smart-search exa-similar`

别名：`xs`

```text
用法：smart-search exa-similar [-h] [--lang {auto,zh,en}]
                            [--num-results NUM_RESULTS]
                            [--format {json,markdown,content}]
                            [--output OUTPUT]
                            url

位置参数:
  url

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  --num-results NUM_RESULTS
  --format {json,markdown,content}
  --output OUTPUT       将渲染后的输出写入文件。
```

解析器默认值：`--num-results` = `5`; `--format` = `json`; `--output` = ``.

## `smart-search zhipu-search`

别名：`z`, `zp`

```text
用法：smart-search zhipu-search [-h] [--lang {auto,zh,en}] [--count COUNT]
                             [--search-engine SEARCH_ENGINE]
                             [--search-recency-filter SEARCH_RECENCY_FILTER]
                             [--search-domain-filter SEARCH_DOMAIN_FILTER]
                             [--content-size {medium,high}]
                             [--format {json,markdown,content}]
                             [--output OUTPUT]
                             query

位置参数:
  query

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  --count COUNT
  --search-engine SEARCH_ENGINE
  --search-recency-filter SEARCH_RECENCY_FILTER
  --search-domain-filter SEARCH_DOMAIN_FILTER
  --content-size {medium,high}
  --format {json,markdown,content}
  --output OUTPUT       将渲染后的输出写入文件。
```

解析器默认值：`--count` = `10`; `--search-engine` = ``; `--search-recency-filter` = `noLimit`; `--search-domain-filter` = ``; `--content-size` = `medium`; `--format` = `json`; `--output` = ``.

## `smart-search zhipu-mcp-search`

别名：`zmcp-search`

```text
用法：smart-search zhipu-mcp-search [-h] [--lang {auto,zh,en}] [--count COUNT]
                                 [--format {json,markdown,content}]
                                 [--output OUTPUT]
                                 query

位置参数:
  query

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  --count COUNT
  --format {json,markdown,content}
  --output OUTPUT       将渲染后的输出写入文件。
```

解析器默认值：`--count` = `5`; `--format` = `json`; `--output` = ``.

## `smart-search zhipu-mcp-reader`

别名：`zmcp-reader`

```text
用法：smart-search zhipu-mcp-reader [-h] [--lang {auto,zh,en}]
                                 [--format {json,markdown,content}]
                                 [--output OUTPUT]
                                 url

位置参数:
  url

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  --format {json,markdown,content}
  --output OUTPUT       将渲染后的输出写入文件。
```

解析器默认值：`--format` = `json`; `--output` = ``.

## `smart-search zhipu-mcp-search-doc`

别名：`zmcp-doc`

```text
用法：smart-search zhipu-mcp-search-doc [-h] [--lang {auto,zh,en}]
                                     [--max-results MAX_RESULTS]
                                     [--format {json,markdown,content}]
                                     [--output OUTPUT]
                                     repo query

位置参数:
  repo
  query

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  --max-results MAX_RESULTS
  --format {json,markdown,content}
  --output OUTPUT       将渲染后的输出写入文件。
```

解析器默认值：`--max-results` = `5`; `--format` = `json`; `--output` = ``.

## `smart-search zhipu-mcp-repo-structure`

别名：`zmcp-tree`

```text
用法：smart-search zhipu-mcp-repo-structure [-h] [--lang {auto,zh,en}]
                                         [--ref REF]
                                         [--format {json,markdown,content}]
                                         [--output OUTPUT]
                                         repo

位置参数:
  repo

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  --ref REF
  --format {json,markdown,content}
  --output OUTPUT       将渲染后的输出写入文件。
```

解析器默认值：`--ref` = ``; `--format` = `json`; `--output` = ``.

## `smart-search zhipu-mcp-read-file`

别名：`zmcp-file`

```text
用法：smart-search zhipu-mcp-read-file [-h] [--lang {auto,zh,en}] [--ref REF]
                                    [--format {json,markdown,content}]
                                    [--output OUTPUT]
                                    repo path

位置参数:
  repo
  path

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  --ref REF
  --format {json,markdown,content}
  --output OUTPUT       将渲染后的输出写入文件。
```

解析器默认值：`--ref` = ``; `--format` = `json`; `--output` = ``.

## `smart-search anysearch-domains`

别名：`as-domains`

```text
用法：smart-search anysearch-domains [-h] [--lang {auto,zh,en}]
                                  [--format {json,markdown,content}]
                                  [--output OUTPUT]
                                  [domain]

位置参数:
  domain

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  --format {json,markdown,content}
  --output OUTPUT       将渲染后的输出写入文件。
```

解析器默认值：`--format` = `json`; `--output` = ``.

## `smart-search anysearch-search`

别名：`as-search`, `as`

```text
用法：smart-search anysearch-search [-h] [--lang {auto,zh,en}] [--domain DOMAIN]
                                 [--sub-domain SUB_DOMAIN]
                                 [--sub-domain-params SUB_DOMAIN_PARAMS]
                                 [--param PARAM] [--max-results MAX_RESULTS]
                                 [--format {json,markdown,content}]
                                 [--output OUTPUT]
                                 query

位置参数:
  query

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  --domain DOMAIN
  --sub-domain SUB_DOMAIN
  --sub-domain-params SUB_DOMAIN_PARAMS
                        转发给 AnySearch sub_domain_params 的 JSON 对象。
  --param PARAM         可重复的 key=value 参数，会覆盖 JSON sub_domain_params 中的同名键。
  --max-results MAX_RESULTS
  --format {json,markdown,content}
  --output OUTPUT       将渲染后的输出写入文件。
```

解析器默认值：`--domain` = ``; `--sub-domain` = ``; `--sub-domain-params` = ``; `--param` = `[]`; `--max-results` = `5`; `--format` = `json`; `--output` = ``.

## `smart-search anysearch-extract`

别名：`as-extract`

```text
用法：smart-search anysearch-extract [-h] [--lang {auto,zh,en}]
                                  [--max-length MAX_LENGTH]
                                  [--format {json,markdown,content}]
                                  [--output OUTPUT]
                                  url

位置参数:
  url

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  --max-length MAX_LENGTH
  --format {json,markdown,content}
  --output OUTPUT       将渲染后的输出写入文件。
```

解析器默认值：`--max-length` = `20000`; `--format` = `json`; `--output` = ``.

## `smart-search anysearch-batch`

别名：`as-batch`

```text
用法：smart-search anysearch-batch [-h] [--lang {auto,zh,en}]
                                [--max-results MAX_RESULTS]
                                [--format {json,markdown,content}]
                                [--output OUTPUT]
                                queries [queries ...]

位置参数:
  queries

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  --max-results MAX_RESULTS
  --format {json,markdown,content}
  --output OUTPUT       将渲染后的输出写入文件。
```

解析器默认值：`--max-results` = `3`; `--format` = `json`; `--output` = ``.

## `smart-search sciverse-catalog`

别名：`sv-catalog`

```text
用法：smart-search sciverse-catalog [-h] [--lang {auto,zh,en}]
                                 [--collection {papers,authors,sources}]
                                 [--include-sample-values]
                                 [--include-field-stats]
                                 [--format {json,markdown,content}]
                                 [--output OUTPUT]

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  --collection {papers,authors,sources}
                        旧版选择器；当前 API 对 authors 和 sources 返回 parameter_error。
  --include-sample-values
  --include-field-stats
  --format {json,markdown,content}
  --output OUTPUT       将渲染后的输出写入文件。
```

解析器默认值：`--collection` = `papers`; `--include-sample-values` = `False`; `--include-field-stats` = `False`; `--format` = `json`; `--output` = ``.

## `smart-search sciverse-search`

别名：`sv-search`, `sv`

```text
用法：smart-search sciverse-search [-h] [--lang {auto,zh,en}]
                                [--collection {papers,authors,sources}]
                                [--title-contains TITLE_CONTAINS]
                                [--abstract-contains ABSTRACT_CONTAINS]
                                [--authors AUTHORS] [--journals JOURNALS]
                                [--subjects SUBJECTS] [--year-from YEAR_FROM]
                                [--year-to YEAR_TO]
                                [--filters-advanced FILTERS_ADVANCED]
                                [--sort-advanced SORT_ADVANCED]
                                [--sort-by-year {desc,asc,none}]
                                [--freshness-boost {NONE,MILD,STRONG}]
                                [--page PAGE] [--page-size PAGE_SIZE]
                                [--format {json,markdown,content}]
                                [--output OUTPUT]
                                [query]

位置参数:
  query

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  --collection {papers,authors,sources}
                        旧版选择器；当前 API 对 authors 和 sources 返回 parameter_error。
  --title-contains TITLE_CONTAINS
  --abstract-contains ABSTRACT_CONTAINS
  --authors AUTHORS     作者名，用逗号分隔。
  --journals JOURNALS   期刊或来源名，用逗号分隔。
  --subjects SUBJECTS   学科标签，用逗号分隔。
  --year-from YEAR_FROM
  --year-to YEAR_TO
  --filters-advanced FILTERS_ADVANCED
                        当前 Sciverse FieldFilterItem 值的 JSON 数组。
  --sort-advanced SORT_ADVANCED
                        当前 Sciverse SortFieldItem 值的 JSON 数组。
  --sort-by-year {desc,asc,none}
  --freshness-boost {NONE,MILD,STRONG}
  --page PAGE
  --page-size PAGE_SIZE
  --format {json,markdown,content}
  --output OUTPUT       将渲染后的输出写入文件。
```

解析器默认值：`--collection` = `papers`; `--title-contains` = ``; `--abstract-contains` = ``; `--authors` = ``; `--journals` = ``; `--subjects` = ``; `--filters-advanced` = ``; `--sort-advanced` = ``; `--sort-by-year` = `none`; `--freshness-boost` = `NONE`; `--page` = `1`; `--page-size` = `10`; `--format` = `json`; `--output` = ``.

## `smart-search sciverse-semantic`

别名：`sv-semantic`

```text
用法：smart-search sciverse-semantic [-h] [--lang {auto,zh,en}] [--top-k TOP_K]
                                  [--retrieval {hybrid,milvus,es}]
                                  [--mode {fast,balanced,quality}]
                                  [--source-types SOURCE_TYPES]
                                  [--format {json,markdown,content}]
                                  [--output OUTPUT]
                                  query

位置参数:
  query

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  --top-k TOP_K
  --retrieval {hybrid,milvus,es}
  --mode {fast,balanced,quality}
                        已弃用的兼容别名，映射为 --retrieval hybrid。
  --source-types SOURCE_TYPES
                        Sciverse 来源类型，用逗号分隔：web,pdf。
  --format {json,markdown,content}
  --output OUTPUT       将渲染后的输出写入文件。
```

解析器默认值：`--top-k` = `10`; `--retrieval` = ``; `--source-types` = ``; `--format` = `json`; `--output` = ``.

## `smart-search sciverse-read`

别名：`sv-read`

```text
用法：smart-search sciverse-read [-h] [--lang {auto,zh,en}] [--offset OFFSET]
                              [--limit LIMIT]
                              [--format {json,markdown,content}]
                              [--output OUTPUT]
                              doc_id

位置参数:
  doc_id

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  --offset OFFSET
  --limit LIMIT
  --format {json,markdown,content}
  --output OUTPUT       将渲染后的输出写入文件。
```

解析器默认值：`--offset` = `0`; `--limit` = `4096`; `--format` = `json`; `--output` = ``.

## `smart-search sciverse-relations`

别名：`sv-relations`

```text
用法：smart-search sciverse-relations [-h] [--lang {auto,zh,en}]
                                   [--relation {CITATIONS,REFERENCES,RELATED_WORKS}]
                                   [--page PAGE] [--page-size PAGE_SIZE]
                                   [--format {json,markdown,content}]
                                   [--output OUTPUT]
                                   unique_id

位置参数:
  unique_id

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  --relation {CITATIONS,REFERENCES,RELATED_WORKS}
  --page PAGE
  --page-size PAGE_SIZE
  --format {json,markdown,content}
  --output OUTPUT       将渲染后的输出写入文件。
```

解析器默认值：`--relation` = `CITATIONS`; `--page` = `1`; `--page-size` = `25`; `--format` = `json`; `--output` = ``.

## `smart-search context7-library`

别名：`c7`, `ctx7`

```text
用法：smart-search context7-library [-h] [--lang {auto,zh,en}]
                                 [--format {json,markdown,content}]
                                 [--output OUTPUT]
                                 name [query]

位置参数:
  name
  query

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  --format {json,markdown,content}
  --output OUTPUT       将渲染后的输出写入文件。
```

解析器默认值：`--format` = `json`; `--output` = ``.

## `smart-search context7-docs`

别名：`c7d`, `c7docs`, `ctx7-docs`

```text
用法：smart-search context7-docs [-h] [--lang {auto,zh,en}]
                              [--format {json,markdown,content}]
                              [--output OUTPUT]
                              library_id query

位置参数:
  library_id
  query

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  --format {json,markdown,content}
  --output OUTPUT       将渲染后的输出写入文件。
```

解析器默认值：`--format` = `json`; `--output` = ``.

## `smart-search deep`

别名：`dr`

```text
用法：smart-search deep [-h] [--lang {auto,zh,en}]
                     [--budget {quick,standard,deep}]
                     [--evidence-dir EVIDENCE_DIR]
                     [--format {json,markdown,content}] [--output OUTPUT]
                     query

位置参数:
  query

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  --budget {quick,standard,deep}
  --evidence-dir EVIDENCE_DIR
  --format {json,markdown,content}
  --output OUTPUT       将渲染后的输出写入文件。
```

解析器默认值：`--budget` = `standard`; `--evidence-dir` = ``; `--format` = `json`; `--output` = ``.

## `smart-search research`

别名：`rs`

```text
用法：smart-search research [-h] [--lang {auto,zh,en}]
                         [--budget {quick,standard,deep}]
                         [--evidence-dir EVIDENCE_DIR] [--fallback {auto,off}]
                         [--format {json,markdown,content}] [--output OUTPUT]
                         query

位置参数:
  query

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  --budget {quick,standard,deep}
  --evidence-dir EVIDENCE_DIR
  --fallback {auto,off}
  --format {json,markdown,content}
  --output OUTPUT       将渲染后的输出写入文件。
```

解析器默认值：`--budget` = `deep`; `--evidence-dir` = ``; `--fallback` = `auto`; `--format` = `json`; `--output` = ``.

## `smart-search smoke`

别名：`sm`

```text
用法：smart-search smoke [-h] [--lang {auto,zh,en}] [--mode {mock,live} |
                      --mock | --live] [--format {json,markdown,content}]
                      [--output OUTPUT]

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  --mode {mock,live}
  --mock                运行离线模拟冒烟检查。
  --live                运行真实服务商冒烟检查。
  --format {json,markdown,content}
  --output OUTPUT       将渲染后的输出写入文件。
```

解析器默认值：`--mode` = `mock`; `--mock` = `mock`; `--live` = `mock`; `--format` = `json`; `--output` = ``.

## `smart-search doctor`

别名：`d`

```text
用法：smart-search doctor [-h] [--lang {auto,zh,en}]
                       [--format {json,markdown,content}] [--output OUTPUT]

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  --format {json,markdown,content}
  --output OUTPUT       将渲染后的输出写入文件。
```

解析器默认值：`--format` = `json`; `--output` = ``.

## `smart-search diagnose`

别名：`diag`

```text
用法：smart-search diagnose [-h] [--lang {auto,zh,en}] [--timeout SECONDS]
                         [--format {json,markdown}] [--output OUTPUT]
                         {openai-compatible}

位置参数:
  {openai-compatible}

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  --timeout SECONDS     每次搜索形态探测的超时秒数。
  --format {json,markdown}
  --output OUTPUT       将渲染后的输出写入文件。
```

解析器默认值：`--timeout` = `30`; `--format` = `markdown`; `--output` = ``.

## `smart-search model`

别名：`mdl`

```text
用法：smart-search model [-h] [--lang {auto,zh,en}] {set,s,current,cur,c} ...

位置参数:
  {set,s,current,cur,c}

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
```

## `smart-search model set`

别名：`s`

```text
用法：smart-search model set [-h] [--lang {auto,zh,en}]
                          [--format {json,markdown,content}] [--output OUTPUT]
                          model

位置参数:
  model

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  --format {json,markdown,content}
  --output OUTPUT       将渲染后的输出写入文件。
```

解析器默认值：`--format` = `json`; `--output` = ``.

## `smart-search model current`

别名：`cur`, `c`

```text
用法：smart-search model current [-h] [--lang {auto,zh,en}]
                              [--format {json,markdown,content}]
                              [--output OUTPUT]

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  --format {json,markdown,content}
  --output OUTPUT       将渲染后的输出写入文件。
```

解析器默认值：`--format` = `json`; `--output` = ``.

## `smart-search skills`

别名：`skill`

```text
用法：smart-search skills [-h] [--lang {auto,zh,en}]
                       {status,st,update,up,remove} ...

位置参数:
  {status,st,update,up,remove}
    status (st)         比较内置技能文件与已安装文件。
    update (up)         用内置资源覆盖所选已安装技能的文件。
    remove              移除所选 Skills 并保留文件备份。

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
```

## `smart-search skills status`

别名：`st`

```text
用法：smart-search skills status [-h] [--lang {auto,zh,en}] [--targets TARGETS]
                              [--all] [--skills-root SKILLS_ROOT]
                              [--format {json,markdown,content}]
                              [--output OUTPUT]

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  --targets TARGETS     AI 工具目标，用逗号分隔，例如 codex,claude,cursor,hermes。
  --all                 检查所有已知技能目标。
  --skills-root SKILLS_ROOT
                        用于便携或测试安装的高级合成 home 目录覆盖；默认使用当前用户的 home 目录。
  --format {json,markdown,content}
  --output OUTPUT       将渲染后的输出写入文件。
```

解析器默认值：`--targets` = `codex,claude,cursor`; `--all` = `False`; `--skills-root` = ``; `--format` = `json`; `--output` = ``.

## `smart-search skills update`

别名：`up`

```text
用法：smart-search skills update [-h] [--lang {auto,zh,en}] [--targets TARGETS]
                              [--all] [--skills-root SKILLS_ROOT]
                              [--format {json,markdown,content}]
                              [--output OUTPUT]

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  --targets TARGETS     AI 工具目标，用逗号分隔，例如 codex,claude,cursor,hermes。
  --all                 更新所有已知技能目标。
  --skills-root SKILLS_ROOT
                        用于便携或测试安装的高级合成 home 目录覆盖；默认使用当前用户的 home 目录。
  --format {json,markdown,content}
  --output OUTPUT       将渲染后的输出写入文件。
```

解析器默认值：`--targets` = `codex,claude,cursor`; `--all` = `False`; `--skills-root` = ``; `--format` = `json`; `--output` = ``.

## `smart-search skills remove`

```text
用法：smart-search skills remove [-h] [--lang {auto,zh,en}] [--targets TARGETS]
                              [--all] [--skills-root SKILLS_ROOT]
                              [--format {json,markdown,content}]
                              [--output OUTPUT]

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  --targets TARGETS
  --all
  --skills-root SKILLS_ROOT
  --format {json,markdown,content}
  --output OUTPUT       将渲染后的输出写入文件。
```

解析器默认值：`--targets` = `codex,claude,cursor`; `--all` = `False`; `--skills-root` = ``; `--format` = `json`; `--output` = ``.

## `smart-search providers`

别名：`prov`

```text
用法：smart-search providers [-h] [--lang {auto,zh,en}]
                          {status,st,ls,reset,clear,test,check,probe} ...

位置参数:
  {status,st,ls,reset,clear,test,check,probe}
    status (st, ls)     显示正在冷却的服务商及原因。
    reset (clear)       清除冷却，让下次运行立即重试服务商。
    test (check, probe)
                        检查服务商已保存的凭据是否可用，会发起真实 API 请求。

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
```

## `smart-search providers status`

别名：`st`, `ls`

```text
用法：smart-search providers status [-h] [--lang {auto,zh,en}]
                                 [--format {json,markdown,content}]
                                 [--output OUTPUT]

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  --format {json,markdown,content}
  --output OUTPUT       将渲染后的输出写入文件。
```

解析器默认值：`--format` = `json`; `--output` = ``.

## `smart-search providers reset`

别名：`clear`

```text
用法：smart-search providers reset [-h] [--lang {auto,zh,en}]
                                [--format {json,markdown,content}]
                                [--output OUTPUT]
                                [providers ...]

位置参数:
  providers             要清除的服务商 ID，例如 zhipu zhipu-mcp。省略则清除全部冷却。

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  --format {json,markdown,content}
  --output OUTPUT       将渲染后的输出写入文件。
```

解析器默认值：`--format` = `json`; `--output` = ``.

## `smart-search providers test`

别名：`check`, `probe`

```text
用法：smart-search providers test [-h] [--lang {auto,zh,en}] [--timeout TIMEOUT]
                               [--format {json,markdown,content}]
                               [--output OUTPUT]
                               providers [providers ...]

位置参数:
  providers             Provider ids to check, e.g. exa zhipu. Known:
                        anysearch, context7, exa, firecrawl, jina, openai-
                        compatible, sciverse, tavily, tinyfish, xai-responses,
                        zhipu, zhipu-mcp, zhipu-mcp-reader.

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  --timeout TIMEOUT     每个服务商的时间上限，单位秒（默认：20.0）。
  --format {json,markdown,content}
  --output OUTPUT       将渲染后的输出写入文件。
```

解析器默认值：`--timeout` = `20.0`; `--format` = `json`; `--output` = ``.

## `smart-search ui`

别名：`web`

```text
用法：smart-search ui [-h] [--lang {auto,zh,en}] [--port PORT] [--no-browser]
                   [--idle-timeout IDLE_TIMEOUT] [--check]
                   [--format {json,markdown,content}] [--output OUTPUT]

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  --port PORT           绑定到 127.0.0.1 的端口（默认选择空闲端口）。
  --no-browser          只打印地址，不打开浏览器。
  --idle-timeout IDLE_TIMEOUT
                        空闲多少秒后退出；0 表示保持运行（默认：900.0）。
  --check               验证内置页面已安装，然后退出。
  --format {json,markdown,content}
  --output OUTPUT       将渲染后的输出写入文件。
```

解析器默认值：`--port` = `0`; `--no-browser` = `False`; `--idle-timeout` = `900.0`; `--check` = `False`; `--format` = `json`; `--output` = ``.

## `smart-search setup`

别名：`init`

```text
用法：smart-search setup [-h] [--lang {auto,zh,en}] [--non-interactive]
                      [--advanced] [--skip-skills]
                      [--install-skills INSTALL_SKILLS]
                      [--skills-root SKILLS_ROOT] [--xai-api-url XAI_API_URL]
                      [--xai-api-key XAI_API_KEY] [--xai-model XAI_MODEL]
                      [--xai-tools-explicit XAI_TOOLS_EXPLICIT]
                      [--openai-compatible-api-url OPENAI_COMPATIBLE_API_URL]
                      [--openai-compatible-api-key OPENAI_COMPATIBLE_API_KEY]
                      [--openai-compatible-model OPENAI_COMPATIBLE_MODEL]
                      [--openai-compatible-fallback-models OPENAI_COMPATIBLE_FALLBACK_MODELS]
                      [--openai-compatible-api-mode OPENAI_COMPATIBLE_API_MODE]
                      [--openai-compatible-stream OPENAI_COMPATIBLE_STREAM]
                      [--jev-synthesis-api-url JEV_SYNTHESIS_API_URL]
                      [--jev-synthesis-api-key JEV_SYNTHESIS_API_KEY]
                      [--jev-synthesis-model JEV_SYNTHESIS_MODEL]
                      [--jev-synthesis-api-mode JEV_SYNTHESIS_API_MODE]
                      [--validation-level VALIDATION_LEVEL]
                      [--fallback-mode FALLBACK_MODE]
                      [--minimum-profile MINIMUM_PROFILE]
                      [--intent-router INTENT_ROUTER]
                      [--search-timeout SEARCH_TIMEOUT]
                      [--intent-embedding-api-url INTENT_EMBEDDING_API_URL]
                      [--intent-embedding-api-key INTENT_EMBEDDING_API_KEY]
                      [--intent-embedding-model INTENT_EMBEDDING_MODEL]
                      [--intent-embedding-threshold INTENT_EMBEDDING_THRESHOLD]
                      [--intent-embedding-margin INTENT_EMBEDDING_MARGIN]
                      [--intent-classifier-api-url INTENT_CLASSIFIER_API_URL]
                      [--intent-classifier-api-key INTENT_CLASSIFIER_API_KEY]
                      [--intent-classifier-model INTENT_CLASSIFIER_MODEL]
                      [--intent-router-timeout INTENT_ROUTER_TIMEOUT]
                      [--provider-cooldown PROVIDER_COOLDOWN]
                      [--provider-failure-threshold PROVIDER_FAILURE_THRESHOLD]
                      [--exa-key EXA_KEY] [--context7-key CONTEXT7_KEY]
                      [--zhipu-key ZHIPU_KEY] [--zhipu-api-url ZHIPU_API_URL]
                      [--zhipu-search-engine ZHIPU_SEARCH_ENGINE]
                      [--zhipu-mcp-key ZHIPU_MCP_KEY]
                      [--zhipu-mcp-search-api-url ZHIPU_MCP_SEARCH_API_URL]
                      [--zhipu-mcp-reader-api-url ZHIPU_MCP_READER_API_URL]
                      [--zhipu-mcp-zread-api-url ZHIPU_MCP_ZREAD_API_URL]
                      [--zhipu-mcp-timeout ZHIPU_MCP_TIMEOUT]
                      [--jina-key JINA_KEY]
                      [--jina-reader-api-url JINA_READER_API_URL]
                      [--jina-respond-with JINA_RESPOND_WITH]
                      [--jina-timeout JINA_TIMEOUT]
                      [--tavily-api-url TAVILY_API_URL]
                      [--tavily-key TAVILY_KEY]
                      [--firecrawl-api-url FIRECRAWL_API_URL]
                      [--firecrawl-key FIRECRAWL_KEY]
                      [--tinyfish-key TINYFISH_KEY]
                      [--tinyfish-search-api-url TINYFISH_SEARCH_API_URL]
                      [--tinyfish-fetch-api-url TINYFISH_FETCH_API_URL]
                      [--tinyfish-timeout TINYFISH_TIMEOUT]
                      [--anysearch-api-url ANYSEARCH_API_URL]
                      [--anysearch-key ANYSEARCH_KEY]
                      [--anysearch-timeout ANYSEARCH_TIMEOUT]
                      [--sciverse-api-url SCIVERSE_API_URL]
                      [--sciverse-token SCIVERSE_TOKEN]
                      [--sciverse-timeout SCIVERSE_TIMEOUT]
                      [--format {json,markdown,content}] [--output OUTPUT]

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  --non-interactive     只保存通过参数传入的值。
  --advanced            在交互式向导中显示全部底层配置键。
  --skip-skills         跳过用户级 smart-search-cli 技能安装。
  --install-skills INSTALL_SKILLS
                        安装 smart-search-cli 技能的 AI 目标，用逗号分隔，例如
                        codex,claude,cursor,hermes。
  --skills-root SKILLS_ROOT
                        用于便携或测试安装的高级合成 home 目录覆盖；默认使用当前用户的 home 目录。
  --xai-api-url XAI_API_URL
                        保存 XAI_API_URL。
  --xai-api-key XAI_API_KEY
                        保存 XAI_API_KEY。
  --xai-model XAI_MODEL
                        保存 XAI_MODEL。
  --xai-tools-explicit XAI_TOOLS_EXPLICIT
                        保存 XAI_TOOLS。
  --openai-compatible-api-url OPENAI_COMPATIBLE_API_URL
                        保存 OPENAI_COMPATIBLE_API_URL。
  --openai-compatible-api-key OPENAI_COMPATIBLE_API_KEY
                        保存 OPENAI_COMPATIBLE_API_KEY。
  --openai-compatible-model OPENAI_COMPATIBLE_MODEL
                        保存 OPENAI_COMPATIBLE_MODEL。
  --openai-compatible-fallback-models OPENAI_COMPATIBLE_FALLBACK_MODELS
                        保存 OPENAI_COMPATIBLE_FALLBACK_MODELS。
  --openai-compatible-api-mode OPENAI_COMPATIBLE_API_MODE
                        保存 OPENAI_COMPATIBLE_API_MODE（chat-completions 或
                        responses）。
  --openai-compatible-stream OPENAI_COMPATIBLE_STREAM
                        保存 OPENAI_COMPATIBLE_STREAM。
  --jev-synthesis-api-url JEV_SYNTHESIS_API_URL
                        Save SMART_SEARCH_JEV_SYNTHESIS_API_URL.
  --jev-synthesis-api-key JEV_SYNTHESIS_API_KEY
                        Save SMART_SEARCH_JEV_SYNTHESIS_API_KEY.
  --jev-synthesis-model JEV_SYNTHESIS_MODEL
                        Save SMART_SEARCH_JEV_SYNTHESIS_MODEL.
  --jev-synthesis-api-mode JEV_SYNTHESIS_API_MODE
                        Save SMART_SEARCH_JEV_SYNTHESIS_API_MODE.
  --validation-level VALIDATION_LEVEL
                        保存 SMART_SEARCH_VALIDATION_LEVEL。
  --fallback-mode FALLBACK_MODE
                        保存 SMART_SEARCH_FALLBACK_MODE。
  --minimum-profile MINIMUM_PROFILE
                        保存 SMART_SEARCH_MINIMUM_PROFILE。
  --intent-router INTENT_ROUTER
                        保存 SMART_SEARCH_INTENT_ROUTER。
  --search-timeout, --search-timeout-seconds SEARCH_TIMEOUT
                        保存 SMART_SEARCH_TIMEOUT_SECONDS。
  --intent-embedding-api-url INTENT_EMBEDDING_API_URL
                        保存 INTENT_EMBEDDING_API_URL。
  --intent-embedding-api-key INTENT_EMBEDDING_API_KEY
                        保存 INTENT_EMBEDDING_API_KEY。
  --intent-embedding-model INTENT_EMBEDDING_MODEL
                        保存 INTENT_EMBEDDING_MODEL。
  --intent-embedding-threshold INTENT_EMBEDDING_THRESHOLD
                        保存 INTENT_EMBEDDING_THRESHOLD。
  --intent-embedding-margin INTENT_EMBEDDING_MARGIN
                        保存 INTENT_EMBEDDING_MARGIN。
  --intent-classifier-api-url INTENT_CLASSIFIER_API_URL
                        保存 INTENT_CLASSIFIER_API_URL。
  --intent-classifier-api-key INTENT_CLASSIFIER_API_KEY
                        保存 INTENT_CLASSIFIER_API_KEY。
  --intent-classifier-model INTENT_CLASSIFIER_MODEL
                        保存 INTENT_CLASSIFIER_MODEL。
  --intent-router-timeout INTENT_ROUTER_TIMEOUT
                        保存 INTENT_ROUTER_TIMEOUT_SECONDS。
  --provider-cooldown, --provider-cooldown-seconds PROVIDER_COOLDOWN
                        保存 SMART_SEARCH_PROVIDER_COOLDOWN_SECONDS；0
                        表示关闭可选服务商失败冷却。
  --provider-failure-threshold PROVIDER_FAILURE_THRESHOLD
                        保存 SMART_SEARCH_PROVIDER_FAILURE_THRESHOLD。
  --exa-key EXA_KEY     保存 EXA_API_KEY。
  --context7-key CONTEXT7_KEY
                        保存 CONTEXT7_API_KEY。
  --zhipu-key ZHIPU_KEY
                        保存 ZHIPU_API_KEY。
  --zhipu-api-url ZHIPU_API_URL
                        保存 ZHIPU_API_URL。
  --zhipu-search-engine ZHIPU_SEARCH_ENGINE
                        保存 ZHIPU_SEARCH_ENGINE。
  --zhipu-mcp-key ZHIPU_MCP_KEY
                        保存 ZHIPU_MCP_API_KEY。
  --zhipu-mcp-search-api-url ZHIPU_MCP_SEARCH_API_URL
                        保存 ZHIPU_MCP_SEARCH_API_URL。
  --zhipu-mcp-reader-api-url ZHIPU_MCP_READER_API_URL
                        保存 ZHIPU_MCP_READER_API_URL。
  --zhipu-mcp-zread-api-url ZHIPU_MCP_ZREAD_API_URL
                        保存 ZHIPU_MCP_ZREAD_API_URL。
  --zhipu-mcp-timeout ZHIPU_MCP_TIMEOUT
                        保存 ZHIPU_MCP_TIMEOUT_SECONDS。
  --jina-key JINA_KEY   保存 JINA_API_KEY。
  --jina-reader-api-url JINA_READER_API_URL
                        保存 JINA_READER_API_URL。
  --jina-respond-with JINA_RESPOND_WITH
                        保存 JINA_RESPOND_WITH，例如 readerlm-v2。
  --jina-timeout JINA_TIMEOUT
                        保存 JINA_TIMEOUT_SECONDS。
  --tavily-api-url TAVILY_API_URL
                        保存 TAVILY_API_URL。
  --tavily-key TAVILY_KEY
                        保存 TAVILY_API_KEY。
  --firecrawl-api-url FIRECRAWL_API_URL
                        保存 FIRECRAWL_API_URL。
  --firecrawl-key FIRECRAWL_KEY
                        保存 FIRECRAWL_API_KEY。
  --tinyfish-key TINYFISH_KEY
                        保存 TINYFISH_API_KEY。
  --tinyfish-search-api-url TINYFISH_SEARCH_API_URL
                        保存 TINYFISH_SEARCH_API_URL。
  --tinyfish-fetch-api-url TINYFISH_FETCH_API_URL
                        保存 TINYFISH_FETCH_API_URL。
  --tinyfish-timeout TINYFISH_TIMEOUT
                        保存 TINYFISH_TIMEOUT_SECONDS。
  --anysearch-api-url ANYSEARCH_API_URL
                        保存 ANYSEARCH_API_URL。
  --anysearch-key ANYSEARCH_KEY
                        保存 ANYSEARCH_API_KEY。
  --anysearch-timeout ANYSEARCH_TIMEOUT
                        保存 ANYSEARCH_TIMEOUT_SECONDS。
  --sciverse-api-url SCIVERSE_API_URL
                        保存 SCIVERSE_API_URL。
  --sciverse-token SCIVERSE_TOKEN
                        保存 SCIVERSE_API_TOKEN。
  --sciverse-timeout SCIVERSE_TIMEOUT
                        保存 SCIVERSE_TIMEOUT_SECONDS。
  --format {json,markdown,content}
  --output OUTPUT       将渲染后的输出写入文件。
```

解析器默认值：`--non-interactive` = `False`; `--advanced` = `False`; `--skip-skills` = `False`; `--install-skills` = ``; `--skills-root` = ``; `--xai-api-url` = ``; `--xai-api-key` = ``; `--xai-model` = ``; `--xai-tools-explicit` = ``; `--openai-compatible-api-url` = ``; `--openai-compatible-api-key` = ``; `--openai-compatible-model` = ``; `--openai-compatible-fallback-models` = ``; `--openai-compatible-api-mode` = ``; `--openai-compatible-stream` = ``; `--jev-synthesis-api-url` = ``; `--jev-synthesis-api-key` = ``; `--jev-synthesis-model` = ``; `--jev-synthesis-api-mode` = ``; `--validation-level` = ``; `--fallback-mode` = ``; `--minimum-profile` = ``; `--intent-router` = ``; `--search-timeout / --search-timeout-seconds` = ``; `--intent-embedding-api-url` = ``; `--intent-embedding-api-key` = ``; `--intent-embedding-model` = ``; `--intent-embedding-threshold` = ``; `--intent-embedding-margin` = ``; `--intent-classifier-api-url` = ``; `--intent-classifier-api-key` = ``; `--intent-classifier-model` = ``; `--intent-router-timeout` = ``; `--provider-cooldown / --provider-cooldown-seconds` = ``; `--provider-failure-threshold` = ``; `--exa-key` = ``; `--context7-key` = ``; `--zhipu-key` = ``; `--zhipu-api-url` = ``; `--zhipu-search-engine` = ``; `--zhipu-mcp-key` = ``; `--zhipu-mcp-search-api-url` = ``; `--zhipu-mcp-reader-api-url` = ``; `--zhipu-mcp-zread-api-url` = ``; `--zhipu-mcp-timeout` = ``; `--jina-key` = ``; `--jina-reader-api-url` = ``; `--jina-respond-with` = ``; `--jina-timeout` = ``; `--tavily-api-url` = ``; `--tavily-key` = ``; `--firecrawl-api-url` = ``; `--firecrawl-key` = ``; `--tinyfish-key` = ``; `--tinyfish-search-api-url` = ``; `--tinyfish-fetch-api-url` = ``; `--tinyfish-timeout` = ``; `--anysearch-api-url` = ``; `--anysearch-key` = ``; `--anysearch-timeout` = ``; `--sciverse-api-url` = ``; `--sciverse-token` = ``; `--sciverse-timeout` = ``; `--format` = `json`; `--output` = ``.

## `smart-search config`

别名：`cfg`

```text
用法：smart-search config [-h] [--lang {auto,zh,en}]
                       {path,p,list,ls,l,set,s,unset,rm,u} ...

位置参数:
  {path,p,list,ls,l,set,s,unset,rm,u}

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
```

## `smart-search config path`

别名：`p`

```text
用法：smart-search config path [-h] [--lang {auto,zh,en}]
                            [--format {json,markdown,content}]
                            [--output OUTPUT]

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  --format {json,markdown,content}
  --output OUTPUT       将渲染后的输出写入文件。
```

解析器默认值：`--format` = `json`; `--output` = ``.

## `smart-search config list`

别名：`ls`, `l`

```text
用法：smart-search config list [-h] [--lang {auto,zh,en}]
                            [--format {json,markdown,content}]
                            [--output OUTPUT]

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  --format {json,markdown,content}
  --output OUTPUT       将渲染后的输出写入文件。
```

解析器默认值：`--format` = `json`; `--output` = ``.

## `smart-search config set`

别名：`s`

```text
用法：smart-search config set [-h] [--lang {auto,zh,en}]
                           [--format {json,markdown,content}]
                           [--output OUTPUT]
                           key value

位置参数:
  key
  value

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  --format {json,markdown,content}
  --output OUTPUT       将渲染后的输出写入文件。
```

解析器默认值：`--format` = `json`; `--output` = ``.

## `smart-search config unset`

别名：`rm`, `u`

```text
用法：smart-search config unset [-h] [--lang {auto,zh,en}]
                             [--format {json,markdown,content}]
                             [--output OUTPUT]
                             key

位置参数:
  key

选项:
  -h, --help            显示此帮助并退出
  --lang {auto,zh,en}   本次调用的界面语言，不改变已保存的偏好。
  --format {json,markdown,content}
  --output OUTPUT       将渲染后的输出写入文件。
```

解析器默认值：`--format` = `json`; `--output` = ``.

## `smart-search regression`

别名：`reg`

```text
用法：smart-search regression [-h] [--lang {auto,zh,en}]

选项:
  -h, --help           显示此帮助并退出
  --lang {auto,zh,en}  本次调用的界面语言，不改变已保存的偏好。
```
