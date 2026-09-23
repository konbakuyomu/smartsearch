[Guide](../README.md) · [简体中文](../zh-CN/cli-reference.md)

# Complete command reference

Generated from the current command parser. See the [CLI guide](cli.md) for examples and exit codes. Put `--lang` before or after the command; text following `--` remains a literal argument.

## `smart-search`

```text
usage: smart-search [-h] [--lang {auto,zh,en}] [-v]
                    {agent-guide,search,s,route,rt,route-calibrate,route-cal,rcal,fetch,f,map,m,exa-search,exa,x,exa-similar,xs,zhipu-search,z,zp,zhipu-mcp-search,zmcp-search,zhipu-mcp-reader,zmcp-reader,zhipu-mcp-search-doc,zmcp-doc,zhipu-mcp-repo-structure,zmcp-tree,zhipu-mcp-read-file,zmcp-file,anysearch-domains,as-domains,anysearch-search,as-search,as,anysearch-extract,as-extract,anysearch-batch,as-batch,sciverse-catalog,sv-catalog,sciverse-search,sv-search,sv,sciverse-semantic,sv-semantic,sciverse-read,sv-read,sciverse-relations,sv-relations,context7-library,c7,ctx7,context7-docs,c7d,c7docs,ctx7-docs,deep,dr,research,rs,smoke,sm,doctor,d,diagnose,diag,model,mdl,skills,skill,providers,prov,ui,web,setup,init,config,cfg,regression,reg} ...

Smart Search CLI for AI-agent web research.

positional arguments:
  {agent-guide,search,s,route,rt,route-calibrate,route-cal,rcal,fetch,f,map,m,exa-search,exa,x,exa-similar,xs,zhipu-search,z,zp,zhipu-mcp-search,zmcp-search,zhipu-mcp-reader,zmcp-reader,zhipu-mcp-search-doc,zmcp-doc,zhipu-mcp-repo-structure,zmcp-tree,zhipu-mcp-read-file,zmcp-file,anysearch-domains,as-domains,anysearch-search,as-search,as,anysearch-extract,as-extract,anysearch-batch,as-batch,sciverse-catalog,sv-catalog,sciverse-search,sv-search,sv,sciverse-semantic,sv-semantic,sciverse-read,sv-read,sciverse-relations,sv-relations,context7-library,c7,ctx7,context7-docs,c7d,c7docs,ctx7-docs,deep,dr,research,rs,smoke,sm,doctor,d,diagnose,diag,model,mdl,skills,skill,providers,prov,ui,web,setup,init,config,cfg,regression,reg}
    agent-guide         Read the current CLI instructions for Agents.
    search (s)          Run OpenAI-compatible web search.
    route (rt)          Explain intent routing without running providers.
    route-calibrate (route-cal, rcal)
                        Evaluate embedding intent-routing models and recommend
                        threshold/margin.
    fetch (f)           Fetch a URL as markdown.
    map (m)             Map a website structure.
    exa-search (exa, x)
                        Run Exa source-first search.
    exa-similar (xs)    Find pages similar to a URL with Exa.
    zhipu-search (z, zp)
                        Run Zhipu Web Search source-first search.
    zhipu-mcp-search (zmcp-search)
                        Run Zhipu Coding Plan Remote MCP web_search_prime.
    zhipu-mcp-reader (zmcp-reader)
                        Run Zhipu Coding Plan Remote MCP webReader.
    zhipu-mcp-search-doc (zmcp-doc)
                        Search repository docs through Zhipu Coding Plan zread
                        MCP.
    zhipu-mcp-repo-structure (zmcp-tree)
                        Read repository structure through Zhipu Coding Plan
                        zread MCP.
    zhipu-mcp-read-file (zmcp-file)
                        Read a repository file through Zhipu Coding Plan zread
                        MCP.
    anysearch-domains (as-domains)
                        List AnySearch vertical search domains.
    anysearch-search (as-search, as)
                        Run experimental AnySearch vertical/general search.
    anysearch-extract (as-extract)
                        Extract a URL through AnySearch experimental extract.
    anysearch-batch (as-batch)
                        Run up to 5 AnySearch queries in parallel.
    sciverse-catalog (sv-catalog)
                        List Sciverse academic metadata fields (current API
                        supports papers only).
    sciverse-search (sv-search, sv)
                        Run explicit experimental Sciverse structured academic
                        search.
    sciverse-semantic (sv-semantic)
                        Run explicit experimental Sciverse semantic paper
                        search.
    sciverse-read (sv-read)
                        Read a Sciverse document content chunk by doc_id.
    sciverse-relations (sv-relations)
                        List Sciverse paper relations by unique_id; CITATIONS
                        are papers citing the target, REFERENCES are papers
                        cited by it.
    context7-library (c7, ctx7)
                        Resolve Context7 library candidates.
    context7-docs (c7d, c7docs, ctx7-docs)
                        Fetch Context7 docs for a library.
    deep (dr)           Create an offline Deep Research plan without calling
                        providers.
    research (rs)       Run live Deep Research with provider-advantage routing
                        and evidence-only synthesis.
    smoke (sm)          Run provider routing and fallback smoke checks.
    doctor (d)          Show masked configuration and connection checks.
    diagnose (diag)     Run focused troubleshooting checks for a provider.
    model (mdl)         Inspect explicit provider models; use config set
                        XAI_MODEL or OPENAI_COMPATIBLE_MODEL to change them.
    skills (skill)      Inspect or update installed smart-search-cli skills.
    providers (prov)    Inspect or clear the persisted failure cooldown for
                        optional providers.
    ui (web)            Open a temporary local page to review configuration
                        and test provider keys.
    setup (init)        Interactively save local provider configuration.
    config (cfg)        Read or edit the local Smart Search config file.
    regression (reg)    Run offline CLI regression tests.

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  -v, --v, --version    show program's version number and exit
```

## `smart-search agent-guide`

```text
usage: smart-search agent-guide [-h] [--lang {auto,zh,en}] [section]

positional arguments:
  section

options:
  -h, --help           show this help message and exit
  --lang {auto,zh,en}  Interface language for this call; does not change the
                       saved preference.
```

## `smart-search search`

Aliases: `s`

```text
usage: smart-search search [-h] [--lang {auto,zh,en}] [--platform PLATFORM]
                           [--model MODEL] [--extra-sources EXTRA_SOURCES]
                           [--validation {fast,balanced,strict}]
                           [--fallback {auto,off}] [--providers PROVIDERS]
                           [--stream | --no-stream] [--timeout SECONDS]
                           [--format {json,markdown,content}]
                           [--output OUTPUT]
                           query

positional arguments:
  query

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  --platform PLATFORM
  --model MODEL
  --extra-sources EXTRA_SOURCES
  --validation {fast,balanced,strict}
  --fallback {auto,off}
  --providers PROVIDERS
  --stream              Use stream=true for OpenAI-compatible main search.
  --no-stream           Force stream=false for OpenAI-compatible main search.
  --timeout SECONDS     Total search budget in seconds; overrides
                        SMART_SEARCH_TIMEOUT_SECONDS.
  --format {json,markdown,content}
  --output OUTPUT       Write rendered output to a file.
```

Parser defaults: `--platform` = ``; `--model` = ``; `--extra-sources` = `0`; `--validation` = ``; `--fallback` = ``; `--providers` = `auto`; `--no-stream` = `True`; `--format` = `json`; `--output` = ``.

## `smart-search route`

Aliases: `rt`

```text
usage: smart-search route [-h] [--lang {auto,zh,en}]
                          [--validation {fast,balanced,strict}] [--remote]
                          [--router-mode {hybrid,rules,off,jev}]
                          [--format {json,markdown,content}] [--output OUTPUT]
                          query

positional arguments:
  query

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  --validation {fast,balanced,strict}
  --remote              Explicitly allow remote routing judgments; may incur
                        API charges. No retrieval is executed.
  --router-mode {hybrid,rules,off,jev}
                        Override SMART_SEARCH_INTENT_ROUTER for this
                        diagnostic call.
  --format {json,markdown,content}
  --output OUTPUT       Write rendered output to a file.
```

Parser defaults: `--validation` = ``; `--remote` = `False`; `--router-mode` = ``; `--format` = `json`; `--output` = ``.

## `smart-search route-calibrate`

Aliases: `route-cal`, `rcal`

```text
usage: smart-search route-calibrate [-h] [--lang {auto,zh,en}]
                                    [--models MODELS]
                                    [--format {json,markdown,content}]
                                    [--output OUTPUT]

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  --models MODELS       Comma-separated embedding model names. Defaults to
                        known candidates plus the configured model.
  --format {json,markdown,content}
  --output OUTPUT       Write rendered output to a file.
```

Parser defaults: `--models` = ``; `--format` = `json`; `--output` = ``.

## `smart-search fetch`

Aliases: `f`

```text
usage: smart-search fetch [-h] [--lang {auto,zh,en}]
                          [--format {json,markdown,content}] [--output OUTPUT]
                          url

positional arguments:
  url

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  --format {json,markdown,content}
  --output OUTPUT       Write rendered output to a file.
```

Parser defaults: `--format` = `json`; `--output` = ``.

## `smart-search map`

Aliases: `m`

```text
usage: smart-search map [-h] [--lang {auto,zh,en}]
                        [--instructions INSTRUCTIONS] [--max-depth MAX_DEPTH]
                        [--max-breadth MAX_BREADTH] [--limit LIMIT]
                        [--timeout TIMEOUT] [--format {json,markdown,content}]
                        [--output OUTPUT]
                        url

positional arguments:
  url

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  --instructions INSTRUCTIONS
  --max-depth MAX_DEPTH
  --max-breadth MAX_BREADTH
  --limit LIMIT
  --timeout TIMEOUT
  --format {json,markdown,content}
  --output OUTPUT       Write rendered output to a file.
```

Parser defaults: `--instructions` = ``; `--max-depth` = `1`; `--max-breadth` = `20`; `--limit` = `50`; `--timeout` = `150`; `--format` = `json`; `--output` = ``.

## `smart-search exa-search`

Aliases: `exa`, `x`

```text
usage: smart-search exa-search [-h] [--lang {auto,zh,en}]
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

positional arguments:
  query

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  --num-results NUM_RESULTS
  --search-type {neural,keyword,auto}
  --include-text
  --include-highlights
  --start-published-date START_PUBLISHED_DATE
  --include-domains INCLUDE_DOMAINS [INCLUDE_DOMAINS ...]
  --exclude-domains EXCLUDE_DOMAINS [EXCLUDE_DOMAINS ...]
  --category CATEGORY
  --format {json,markdown,content}
  --output OUTPUT       Write rendered output to a file.
```

Parser defaults: `--num-results` = `5`; `--search-type` = `neural`; `--include-text` = `False`; `--include-highlights` = `False`; `--start-published-date` = ``; `--include-domains` = ``; `--exclude-domains` = ``; `--category` = ``; `--format` = `json`; `--output` = ``.

## `smart-search exa-similar`

Aliases: `xs`

```text
usage: smart-search exa-similar [-h] [--lang {auto,zh,en}]
                                [--num-results NUM_RESULTS]
                                [--format {json,markdown,content}]
                                [--output OUTPUT]
                                url

positional arguments:
  url

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  --num-results NUM_RESULTS
  --format {json,markdown,content}
  --output OUTPUT       Write rendered output to a file.
```

Parser defaults: `--num-results` = `5`; `--format` = `json`; `--output` = ``.

## `smart-search zhipu-search`

Aliases: `z`, `zp`

```text
usage: smart-search zhipu-search [-h] [--lang {auto,zh,en}] [--count COUNT]
                                 [--search-engine SEARCH_ENGINE]
                                 [--search-recency-filter SEARCH_RECENCY_FILTER]
                                 [--search-domain-filter SEARCH_DOMAIN_FILTER]
                                 [--content-size {medium,high}]
                                 [--format {json,markdown,content}]
                                 [--output OUTPUT]
                                 query

positional arguments:
  query

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  --count COUNT
  --search-engine SEARCH_ENGINE
  --search-recency-filter SEARCH_RECENCY_FILTER
  --search-domain-filter SEARCH_DOMAIN_FILTER
  --content-size {medium,high}
  --format {json,markdown,content}
  --output OUTPUT       Write rendered output to a file.
```

Parser defaults: `--count` = `10`; `--search-engine` = ``; `--search-recency-filter` = `noLimit`; `--search-domain-filter` = ``; `--content-size` = `medium`; `--format` = `json`; `--output` = ``.

## `smart-search zhipu-mcp-search`

Aliases: `zmcp-search`

```text
usage: smart-search zhipu-mcp-search [-h] [--lang {auto,zh,en}]
                                     [--count COUNT]
                                     [--format {json,markdown,content}]
                                     [--output OUTPUT]
                                     query

positional arguments:
  query

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  --count COUNT
  --format {json,markdown,content}
  --output OUTPUT       Write rendered output to a file.
```

Parser defaults: `--count` = `5`; `--format` = `json`; `--output` = ``.

## `smart-search zhipu-mcp-reader`

Aliases: `zmcp-reader`

```text
usage: smart-search zhipu-mcp-reader [-h] [--lang {auto,zh,en}]
                                     [--format {json,markdown,content}]
                                     [--output OUTPUT]
                                     url

positional arguments:
  url

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  --format {json,markdown,content}
  --output OUTPUT       Write rendered output to a file.
```

Parser defaults: `--format` = `json`; `--output` = ``.

## `smart-search zhipu-mcp-search-doc`

Aliases: `zmcp-doc`

```text
usage: smart-search zhipu-mcp-search-doc [-h] [--lang {auto,zh,en}]
                                         [--max-results MAX_RESULTS]
                                         [--format {json,markdown,content}]
                                         [--output OUTPUT]
                                         repo query

positional arguments:
  repo
  query

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  --max-results MAX_RESULTS
  --format {json,markdown,content}
  --output OUTPUT       Write rendered output to a file.
```

Parser defaults: `--max-results` = `5`; `--format` = `json`; `--output` = ``.

## `smart-search zhipu-mcp-repo-structure`

Aliases: `zmcp-tree`

```text
usage: smart-search zhipu-mcp-repo-structure [-h] [--lang {auto,zh,en}]
                                             [--ref REF]
                                             [--format {json,markdown,content}]
                                             [--output OUTPUT]
                                             repo

positional arguments:
  repo

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  --ref REF
  --format {json,markdown,content}
  --output OUTPUT       Write rendered output to a file.
```

Parser defaults: `--ref` = ``; `--format` = `json`; `--output` = ``.

## `smart-search zhipu-mcp-read-file`

Aliases: `zmcp-file`

```text
usage: smart-search zhipu-mcp-read-file [-h] [--lang {auto,zh,en}] [--ref REF]
                                        [--format {json,markdown,content}]
                                        [--output OUTPUT]
                                        repo path

positional arguments:
  repo
  path

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  --ref REF
  --format {json,markdown,content}
  --output OUTPUT       Write rendered output to a file.
```

Parser defaults: `--ref` = ``; `--format` = `json`; `--output` = ``.

## `smart-search anysearch-domains`

Aliases: `as-domains`

```text
usage: smart-search anysearch-domains [-h] [--lang {auto,zh,en}]
                                      [--format {json,markdown,content}]
                                      [--output OUTPUT]
                                      [domain]

positional arguments:
  domain

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  --format {json,markdown,content}
  --output OUTPUT       Write rendered output to a file.
```

Parser defaults: `--format` = `json`; `--output` = ``.

## `smart-search anysearch-search`

Aliases: `as-search`, `as`

```text
usage: smart-search anysearch-search [-h] [--lang {auto,zh,en}]
                                     [--domain DOMAIN]
                                     [--sub-domain SUB_DOMAIN]
                                     [--sub-domain-params SUB_DOMAIN_PARAMS]
                                     [--param PARAM]
                                     [--max-results MAX_RESULTS]
                                     [--format {json,markdown,content}]
                                     [--output OUTPUT]
                                     query

positional arguments:
  query

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  --domain DOMAIN
  --sub-domain SUB_DOMAIN
  --sub-domain-params SUB_DOMAIN_PARAMS
                        JSON object forwarded to AnySearch sub_domain_params.
  --param PARAM         Repeatable key=value entries that override matching
                        JSON sub_domain_params keys.
  --max-results MAX_RESULTS
  --format {json,markdown,content}
  --output OUTPUT       Write rendered output to a file.
```

Parser defaults: `--domain` = ``; `--sub-domain` = ``; `--sub-domain-params` = ``; `--param` = `[]`; `--max-results` = `5`; `--format` = `json`; `--output` = ``.

## `smart-search anysearch-extract`

Aliases: `as-extract`

```text
usage: smart-search anysearch-extract [-h] [--lang {auto,zh,en}]
                                      [--max-length MAX_LENGTH]
                                      [--format {json,markdown,content}]
                                      [--output OUTPUT]
                                      url

positional arguments:
  url

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  --max-length MAX_LENGTH
  --format {json,markdown,content}
  --output OUTPUT       Write rendered output to a file.
```

Parser defaults: `--max-length` = `20000`; `--format` = `json`; `--output` = ``.

## `smart-search anysearch-batch`

Aliases: `as-batch`

```text
usage: smart-search anysearch-batch [-h] [--lang {auto,zh,en}]
                                    [--max-results MAX_RESULTS]
                                    [--format {json,markdown,content}]
                                    [--output OUTPUT]
                                    queries [queries ...]

positional arguments:
  queries

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  --max-results MAX_RESULTS
  --format {json,markdown,content}
  --output OUTPUT       Write rendered output to a file.
```

Parser defaults: `--max-results` = `3`; `--format` = `json`; `--output` = ``.

## `smart-search sciverse-catalog`

Aliases: `sv-catalog`

```text
usage: smart-search sciverse-catalog [-h] [--lang {auto,zh,en}]
                                     [--collection {papers,authors,sources}]
                                     [--include-sample-values]
                                     [--include-field-stats]
                                     [--format {json,markdown,content}]
                                     [--output OUTPUT]

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  --collection {papers,authors,sources}
                        Legacy selector; authors and sources return
                        parameter_error with the current API.
  --include-sample-values
  --include-field-stats
  --format {json,markdown,content}
  --output OUTPUT       Write rendered output to a file.
```

Parser defaults: `--collection` = `papers`; `--include-sample-values` = `False`; `--include-field-stats` = `False`; `--format` = `json`; `--output` = ``.

## `smart-search sciverse-search`

Aliases: `sv-search`, `sv`

```text
usage: smart-search sciverse-search [-h] [--lang {auto,zh,en}]
                                    [--collection {papers,authors,sources}]
                                    [--title-contains TITLE_CONTAINS]
                                    [--abstract-contains ABSTRACT_CONTAINS]
                                    [--authors AUTHORS] [--journals JOURNALS]
                                    [--subjects SUBJECTS]
                                    [--year-from YEAR_FROM]
                                    [--year-to YEAR_TO]
                                    [--filters-advanced FILTERS_ADVANCED]
                                    [--sort-advanced SORT_ADVANCED]
                                    [--sort-by-year {desc,asc,none}]
                                    [--freshness-boost {NONE,MILD,STRONG}]
                                    [--page PAGE] [--page-size PAGE_SIZE]
                                    [--format {json,markdown,content}]
                                    [--output OUTPUT]
                                    [query]

positional arguments:
  query

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  --collection {papers,authors,sources}
                        Legacy selector; authors and sources return
                        parameter_error with the current API.
  --title-contains TITLE_CONTAINS
  --abstract-contains ABSTRACT_CONTAINS
  --authors AUTHORS     Comma-separated author names.
  --journals JOURNALS   Comma-separated journal/source names.
  --subjects SUBJECTS   Comma-separated subject labels.
  --year-from YEAR_FROM
  --year-to YEAR_TO
  --filters-advanced FILTERS_ADVANCED
                        JSON array of current Sciverse FieldFilterItem values.
  --sort-advanced SORT_ADVANCED
                        JSON array of current Sciverse SortFieldItem values.
  --sort-by-year {desc,asc,none}
  --freshness-boost {NONE,MILD,STRONG}
  --page PAGE
  --page-size PAGE_SIZE
  --format {json,markdown,content}
  --output OUTPUT       Write rendered output to a file.
```

Parser defaults: `--collection` = `papers`; `--title-contains` = ``; `--abstract-contains` = ``; `--authors` = ``; `--journals` = ``; `--subjects` = ``; `--filters-advanced` = ``; `--sort-advanced` = ``; `--sort-by-year` = `none`; `--freshness-boost` = `NONE`; `--page` = `1`; `--page-size` = `10`; `--format` = `json`; `--output` = ``.

## `smart-search sciverse-semantic`

Aliases: `sv-semantic`

```text
usage: smart-search sciverse-semantic [-h] [--lang {auto,zh,en}]
                                      [--top-k TOP_K]
                                      [--retrieval {hybrid,milvus,es}]
                                      [--mode {fast,balanced,quality}]
                                      [--source-types SOURCE_TYPES]
                                      [--format {json,markdown,content}]
                                      [--output OUTPUT]
                                      query

positional arguments:
  query

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  --top-k TOP_K
  --retrieval {hybrid,milvus,es}
  --mode {fast,balanced,quality}
                        Deprecated compatibility alias; maps to --retrieval
                        hybrid.
  --source-types SOURCE_TYPES
                        Comma-separated Sciverse source types: web,pdf.
  --format {json,markdown,content}
  --output OUTPUT       Write rendered output to a file.
```

Parser defaults: `--top-k` = `10`; `--retrieval` = ``; `--source-types` = ``; `--format` = `json`; `--output` = ``.

## `smart-search sciverse-read`

Aliases: `sv-read`

```text
usage: smart-search sciverse-read [-h] [--lang {auto,zh,en}] [--offset OFFSET]
                                  [--limit LIMIT]
                                  [--format {json,markdown,content}]
                                  [--output OUTPUT]
                                  doc_id

positional arguments:
  doc_id

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  --offset OFFSET
  --limit LIMIT
  --format {json,markdown,content}
  --output OUTPUT       Write rendered output to a file.
```

Parser defaults: `--offset` = `0`; `--limit` = `4096`; `--format` = `json`; `--output` = ``.

## `smart-search sciverse-relations`

Aliases: `sv-relations`

```text
usage: smart-search sciverse-relations [-h] [--lang {auto,zh,en}]
                                       [--relation {CITATIONS,REFERENCES,RELATED_WORKS}]
                                       [--page PAGE] [--page-size PAGE_SIZE]
                                       [--format {json,markdown,content}]
                                       [--output OUTPUT]
                                       unique_id

positional arguments:
  unique_id

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  --relation {CITATIONS,REFERENCES,RELATED_WORKS}
  --page PAGE
  --page-size PAGE_SIZE
  --format {json,markdown,content}
  --output OUTPUT       Write rendered output to a file.
```

Parser defaults: `--relation` = `CITATIONS`; `--page` = `1`; `--page-size` = `25`; `--format` = `json`; `--output` = ``.

## `smart-search context7-library`

Aliases: `c7`, `ctx7`

```text
usage: smart-search context7-library [-h] [--lang {auto,zh,en}]
                                     [--format {json,markdown,content}]
                                     [--output OUTPUT]
                                     name [query]

positional arguments:
  name
  query

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  --format {json,markdown,content}
  --output OUTPUT       Write rendered output to a file.
```

Parser defaults: `--format` = `json`; `--output` = ``.

## `smart-search context7-docs`

Aliases: `c7d`, `c7docs`, `ctx7-docs`

```text
usage: smart-search context7-docs [-h] [--lang {auto,zh,en}]
                                  [--format {json,markdown,content}]
                                  [--output OUTPUT]
                                  library_id query

positional arguments:
  library_id
  query

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  --format {json,markdown,content}
  --output OUTPUT       Write rendered output to a file.
```

Parser defaults: `--format` = `json`; `--output` = ``.

## `smart-search deep`

Aliases: `dr`

```text
usage: smart-search deep [-h] [--lang {auto,zh,en}]
                         [--budget {quick,standard,deep}]
                         [--evidence-dir EVIDENCE_DIR]
                         [--format {json,markdown,content}] [--output OUTPUT]
                         query

positional arguments:
  query

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  --budget {quick,standard,deep}
  --evidence-dir EVIDENCE_DIR
  --format {json,markdown,content}
  --output OUTPUT       Write rendered output to a file.
```

Parser defaults: `--budget` = `standard`; `--evidence-dir` = ``; `--format` = `json`; `--output` = ``.

## `smart-search research`

Aliases: `rs`

```text
usage: smart-search research [-h] [--lang {auto,zh,en}]
                             [--budget {quick,standard,deep}]
                             [--evidence-dir EVIDENCE_DIR]
                             [--fallback {auto,off}]
                             [--format {json,markdown,content}]
                             [--output OUTPUT]
                             query

positional arguments:
  query

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  --budget {quick,standard,deep}
  --evidence-dir EVIDENCE_DIR
  --fallback {auto,off}
  --format {json,markdown,content}
  --output OUTPUT       Write rendered output to a file.
```

Parser defaults: `--budget` = `deep`; `--evidence-dir` = ``; `--fallback` = `auto`; `--format` = `json`; `--output` = ``.

## `smart-search smoke`

Aliases: `sm`

```text
usage: smart-search smoke [-h] [--lang {auto,zh,en}] [--mode {mock,live} |
                          --mock | --live] [--format {json,markdown,content}]
                          [--output OUTPUT]

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  --mode {mock,live}
  --mock                Run offline mock smoke checks.
  --live                Run live provider smoke checks.
  --format {json,markdown,content}
  --output OUTPUT       Write rendered output to a file.
```

Parser defaults: `--mode` = `mock`; `--mock` = `mock`; `--live` = `mock`; `--format` = `json`; `--output` = ``.

## `smart-search doctor`

Aliases: `d`

```text
usage: smart-search doctor [-h] [--lang {auto,zh,en}]
                           [--format {json,markdown,content}]
                           [--output OUTPUT]

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  --format {json,markdown,content}
  --output OUTPUT       Write rendered output to a file.
```

Parser defaults: `--format` = `json`; `--output` = ``.

## `smart-search diagnose`

Aliases: `diag`

```text
usage: smart-search diagnose [-h] [--lang {auto,zh,en}] [--timeout SECONDS]
                             [--format {json,markdown}] [--output OUTPUT]
                             {openai-compatible}

positional arguments:
  {openai-compatible}

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  --timeout SECONDS     Per search-shape probe timeout in seconds.
  --format {json,markdown}
  --output OUTPUT       Write rendered output to a file.
```

Parser defaults: `--timeout` = `30`; `--format` = `markdown`; `--output` = ``.

## `smart-search model`

Aliases: `mdl`

```text
usage: smart-search model [-h] [--lang {auto,zh,en}] {set,s,current,cur,c} ...

positional arguments:
  {set,s,current,cur,c}

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
```

## `smart-search model set`

Aliases: `s`

```text
usage: smart-search model set [-h] [--lang {auto,zh,en}]
                              [--format {json,markdown,content}]
                              [--output OUTPUT]
                              model

positional arguments:
  model

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  --format {json,markdown,content}
  --output OUTPUT       Write rendered output to a file.
```

Parser defaults: `--format` = `json`; `--output` = ``.

## `smart-search model current`

Aliases: `cur`, `c`

```text
usage: smart-search model current [-h] [--lang {auto,zh,en}]
                                  [--format {json,markdown,content}]
                                  [--output OUTPUT]

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  --format {json,markdown,content}
  --output OUTPUT       Write rendered output to a file.
```

Parser defaults: `--format` = `json`; `--output` = ``.

## `smart-search skills`

Aliases: `skill`

```text
usage: smart-search skills [-h] [--lang {auto,zh,en}]
                           {status,st,update,up,remove} ...

positional arguments:
  {status,st,update,up,remove}
    status (st)         Compare bundled and installed skill files.
    update (up)         Overwrite selected installed skill files with bundled
                        assets.
    remove              Remove selected Skills, keeping a backup of their
                        files.

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
```

## `smart-search skills status`

Aliases: `st`

```text
usage: smart-search skills status [-h] [--lang {auto,zh,en}]
                                  [--targets TARGETS] [--all]
                                  [--skills-root SKILLS_ROOT]
                                  [--format {json,markdown,content}]
                                  [--output OUTPUT]

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  --targets TARGETS     Comma-separated AI tool targets, e.g.
                        codex,claude,cursor,hermes.
  --all                 Check every known skill target.
  --skills-root SKILLS_ROOT
                        Advanced synthetic home-directory override for
                        portable or test installs; defaults to the current
                        user's home directory.
  --format {json,markdown,content}
  --output OUTPUT       Write rendered output to a file.
```

Parser defaults: `--targets` = `codex,claude,cursor`; `--all` = `False`; `--skills-root` = ``; `--format` = `json`; `--output` = ``.

## `smart-search skills update`

Aliases: `up`

```text
usage: smart-search skills update [-h] [--lang {auto,zh,en}]
                                  [--targets TARGETS] [--all]
                                  [--skills-root SKILLS_ROOT]
                                  [--format {json,markdown,content}]
                                  [--output OUTPUT]

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  --targets TARGETS     Comma-separated AI tool targets, e.g.
                        codex,claude,cursor,hermes.
  --all                 Update every known skill target.
  --skills-root SKILLS_ROOT
                        Advanced synthetic home-directory override for
                        portable or test installs; defaults to the current
                        user's home directory.
  --format {json,markdown,content}
  --output OUTPUT       Write rendered output to a file.
```

Parser defaults: `--targets` = `codex,claude,cursor`; `--all` = `False`; `--skills-root` = ``; `--format` = `json`; `--output` = ``.

## `smart-search skills remove`

```text
usage: smart-search skills remove [-h] [--lang {auto,zh,en}]
                                  [--targets TARGETS] [--all]
                                  [--skills-root SKILLS_ROOT]
                                  [--format {json,markdown,content}]
                                  [--output OUTPUT]

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  --targets TARGETS
  --all
  --skills-root SKILLS_ROOT
  --format {json,markdown,content}
  --output OUTPUT       Write rendered output to a file.
```

Parser defaults: `--targets` = `codex,claude,cursor`; `--all` = `False`; `--skills-root` = ``; `--format` = `json`; `--output` = ``.

## `smart-search providers`

Aliases: `prov`

```text
usage: smart-search providers [-h] [--lang {auto,zh,en}]
                              {status,st,ls,reset,clear,test,check,probe} ...

positional arguments:
  {status,st,ls,reset,clear,test,check,probe}
    status (st, ls)     Show which providers are on cooldown and why.
    reset (clear)       Clear cooldowns so the next run retries the provider
                        immediately.
    test (check, probe)
                        Check whether a provider's saved credentials still
                        work. Makes a real API request.

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
```

## `smart-search providers status`

Aliases: `st`, `ls`

```text
usage: smart-search providers status [-h] [--lang {auto,zh,en}]
                                     [--format {json,markdown,content}]
                                     [--output OUTPUT]

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  --format {json,markdown,content}
  --output OUTPUT       Write rendered output to a file.
```

Parser defaults: `--format` = `json`; `--output` = ``.

## `smart-search providers reset`

Aliases: `clear`

```text
usage: smart-search providers reset [-h] [--lang {auto,zh,en}]
                                    [--format {json,markdown,content}]
                                    [--output OUTPUT]
                                    [providers ...]

positional arguments:
  providers             Provider ids to clear, e.g. zhipu zhipu-mcp. Omit to
                        clear every cooldown.

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  --format {json,markdown,content}
  --output OUTPUT       Write rendered output to a file.
```

Parser defaults: `--format` = `json`; `--output` = ``.

## `smart-search providers test`

Aliases: `check`, `probe`

```text
usage: smart-search providers test [-h] [--lang {auto,zh,en}]
                                   [--timeout TIMEOUT]
                                   [--format {json,markdown,content}]
                                   [--output OUTPUT]
                                   providers [providers ...]

positional arguments:
  providers             Provider ids to check, e.g. exa zhipu. Known:
                        anysearch, context7, exa, firecrawl, jina, openai-
                        compatible, sciverse, tavily, tinyfish, xai-responses,
                        zhipu, zhipu-mcp, zhipu-mcp-reader.

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  --timeout TIMEOUT     Per-provider ceiling in seconds (default: 20.0).
  --format {json,markdown,content}
  --output OUTPUT       Write rendered output to a file.
```

Parser defaults: `--timeout` = `20.0`; `--format` = `json`; `--output` = ``.

## `smart-search ui`

Aliases: `web`

```text
usage: smart-search ui [-h] [--lang {auto,zh,en}] [--port PORT] [--no-browser]
                       [--idle-timeout IDLE_TIMEOUT] [--check]
                       [--format {json,markdown,content}] [--output OUTPUT]

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  --port PORT           Port to bind on 127.0.0.1 (default: a free one).
  --no-browser          Print the URL without opening a browser.
  --idle-timeout IDLE_TIMEOUT
                        Exit after this many idle seconds; 0 keeps it running
                        (default: 900.0).
  --check               Verify the bundled page is installed, then exit.
  --format {json,markdown,content}
  --output OUTPUT       Write rendered output to a file.
```

Parser defaults: `--port` = `0`; `--no-browser` = `False`; `--idle-timeout` = `900.0`; `--check` = `False`; `--format` = `json`; `--output` = ``.

## `smart-search setup`

Aliases: `init`

```text
usage: smart-search setup [-h] [--lang {auto,zh,en}] [--non-interactive]
                          [--advanced] [--skip-skills]
                          [--install-skills INSTALL_SKILLS]
                          [--skills-root SKILLS_ROOT]
                          [--xai-api-url XAI_API_URL]
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
                          [--zhipu-key ZHIPU_KEY]
                          [--zhipu-api-url ZHIPU_API_URL]
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

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  --non-interactive     Only save values passed as flags.
  --advanced            Show every low-level config key in interactive setup.
  --skip-skills         Skip user-level smart-search-cli skill installation.
  --install-skills INSTALL_SKILLS
                        Comma-separated AI tool targets for smart-search-cli
                        skill installation, e.g. codex,claude,cursor,hermes.
  --skills-root SKILLS_ROOT
                        Advanced synthetic home-directory override for
                        portable or test installs; defaults to the current
                        user's home directory.
  --xai-api-url XAI_API_URL
                        Save XAI_API_URL.
  --xai-api-key XAI_API_KEY
                        Save XAI_API_KEY.
  --xai-model XAI_MODEL
                        Save XAI_MODEL.
  --xai-tools-explicit XAI_TOOLS_EXPLICIT
                        Save XAI_TOOLS.
  --openai-compatible-api-url OPENAI_COMPATIBLE_API_URL
                        Save OPENAI_COMPATIBLE_API_URL.
  --openai-compatible-api-key OPENAI_COMPATIBLE_API_KEY
                        Save OPENAI_COMPATIBLE_API_KEY.
  --openai-compatible-model OPENAI_COMPATIBLE_MODEL
                        Save OPENAI_COMPATIBLE_MODEL.
  --openai-compatible-fallback-models OPENAI_COMPATIBLE_FALLBACK_MODELS
                        Save OPENAI_COMPATIBLE_FALLBACK_MODELS.
  --openai-compatible-api-mode OPENAI_COMPATIBLE_API_MODE
                        Save OPENAI_COMPATIBLE_API_MODE (chat-completions or
                        responses).
  --openai-compatible-stream OPENAI_COMPATIBLE_STREAM
                        Save OPENAI_COMPATIBLE_STREAM.
  --jev-synthesis-api-url JEV_SYNTHESIS_API_URL
                        Save SMART_SEARCH_JEV_SYNTHESIS_API_URL.
  --jev-synthesis-api-key JEV_SYNTHESIS_API_KEY
                        Save SMART_SEARCH_JEV_SYNTHESIS_API_KEY.
  --jev-synthesis-model JEV_SYNTHESIS_MODEL
                        Save SMART_SEARCH_JEV_SYNTHESIS_MODEL.
  --jev-synthesis-api-mode JEV_SYNTHESIS_API_MODE
                        Save SMART_SEARCH_JEV_SYNTHESIS_API_MODE.
  --validation-level VALIDATION_LEVEL
                        Save SMART_SEARCH_VALIDATION_LEVEL.
  --fallback-mode FALLBACK_MODE
                        Save SMART_SEARCH_FALLBACK_MODE.
  --minimum-profile MINIMUM_PROFILE
                        Save SMART_SEARCH_MINIMUM_PROFILE.
  --intent-router INTENT_ROUTER
                        Save SMART_SEARCH_INTENT_ROUTER.
  --search-timeout, --search-timeout-seconds SEARCH_TIMEOUT
                        Save SMART_SEARCH_TIMEOUT_SECONDS.
  --intent-embedding-api-url INTENT_EMBEDDING_API_URL
                        Save INTENT_EMBEDDING_API_URL.
  --intent-embedding-api-key INTENT_EMBEDDING_API_KEY
                        Save INTENT_EMBEDDING_API_KEY.
  --intent-embedding-model INTENT_EMBEDDING_MODEL
                        Save INTENT_EMBEDDING_MODEL.
  --intent-embedding-threshold INTENT_EMBEDDING_THRESHOLD
                        Save INTENT_EMBEDDING_THRESHOLD.
  --intent-embedding-margin INTENT_EMBEDDING_MARGIN
                        Save INTENT_EMBEDDING_MARGIN.
  --intent-classifier-api-url INTENT_CLASSIFIER_API_URL
                        Save INTENT_CLASSIFIER_API_URL.
  --intent-classifier-api-key INTENT_CLASSIFIER_API_KEY
                        Save INTENT_CLASSIFIER_API_KEY.
  --intent-classifier-model INTENT_CLASSIFIER_MODEL
                        Save INTENT_CLASSIFIER_MODEL.
  --intent-router-timeout INTENT_ROUTER_TIMEOUT
                        Save INTENT_ROUTER_TIMEOUT_SECONDS.
  --provider-cooldown, --provider-cooldown-seconds PROVIDER_COOLDOWN
                        Save SMART_SEARCH_PROVIDER_COOLDOWN_SECONDS; 0
                        disables the optional-provider failure cooldown.
  --provider-failure-threshold PROVIDER_FAILURE_THRESHOLD
                        Save SMART_SEARCH_PROVIDER_FAILURE_THRESHOLD.
  --exa-key EXA_KEY     Save EXA_API_KEY.
  --context7-key CONTEXT7_KEY
                        Save CONTEXT7_API_KEY.
  --zhipu-key ZHIPU_KEY
                        Save ZHIPU_API_KEY.
  --zhipu-api-url ZHIPU_API_URL
                        Save ZHIPU_API_URL.
  --zhipu-search-engine ZHIPU_SEARCH_ENGINE
                        Save ZHIPU_SEARCH_ENGINE.
  --zhipu-mcp-key ZHIPU_MCP_KEY
                        Save ZHIPU_MCP_API_KEY.
  --zhipu-mcp-search-api-url ZHIPU_MCP_SEARCH_API_URL
                        Save ZHIPU_MCP_SEARCH_API_URL.
  --zhipu-mcp-reader-api-url ZHIPU_MCP_READER_API_URL
                        Save ZHIPU_MCP_READER_API_URL.
  --zhipu-mcp-zread-api-url ZHIPU_MCP_ZREAD_API_URL
                        Save ZHIPU_MCP_ZREAD_API_URL.
  --zhipu-mcp-timeout ZHIPU_MCP_TIMEOUT
                        Save ZHIPU_MCP_TIMEOUT_SECONDS.
  --jina-key JINA_KEY   Save JINA_API_KEY.
  --jina-reader-api-url JINA_READER_API_URL
                        Save JINA_READER_API_URL.
  --jina-respond-with JINA_RESPOND_WITH
                        Save JINA_RESPOND_WITH, e.g. readerlm-v2.
  --jina-timeout JINA_TIMEOUT
                        Save JINA_TIMEOUT_SECONDS.
  --tavily-api-url TAVILY_API_URL
                        Save TAVILY_API_URL.
  --tavily-key TAVILY_KEY
                        Save TAVILY_API_KEY.
  --firecrawl-api-url FIRECRAWL_API_URL
                        Save FIRECRAWL_API_URL.
  --firecrawl-key FIRECRAWL_KEY
                        Save FIRECRAWL_API_KEY.
  --tinyfish-key TINYFISH_KEY
                        Save TINYFISH_API_KEY.
  --tinyfish-search-api-url TINYFISH_SEARCH_API_URL
                        Save TINYFISH_SEARCH_API_URL.
  --tinyfish-fetch-api-url TINYFISH_FETCH_API_URL
                        Save TINYFISH_FETCH_API_URL.
  --tinyfish-timeout TINYFISH_TIMEOUT
                        Save TINYFISH_TIMEOUT_SECONDS.
  --anysearch-api-url ANYSEARCH_API_URL
                        Save ANYSEARCH_API_URL.
  --anysearch-key ANYSEARCH_KEY
                        Save ANYSEARCH_API_KEY.
  --anysearch-timeout ANYSEARCH_TIMEOUT
                        Save ANYSEARCH_TIMEOUT_SECONDS.
  --sciverse-api-url SCIVERSE_API_URL
                        Save SCIVERSE_API_URL.
  --sciverse-token SCIVERSE_TOKEN
                        Save SCIVERSE_API_TOKEN.
  --sciverse-timeout SCIVERSE_TIMEOUT
                        Save SCIVERSE_TIMEOUT_SECONDS.
  --format {json,markdown,content}
  --output OUTPUT       Write rendered output to a file.
```

Parser defaults: `--non-interactive` = `False`; `--advanced` = `False`; `--skip-skills` = `False`; `--install-skills` = ``; `--skills-root` = ``; `--xai-api-url` = ``; `--xai-api-key` = ``; `--xai-model` = ``; `--xai-tools-explicit` = ``; `--openai-compatible-api-url` = ``; `--openai-compatible-api-key` = ``; `--openai-compatible-model` = ``; `--openai-compatible-fallback-models` = ``; `--openai-compatible-api-mode` = ``; `--openai-compatible-stream` = ``; `--jev-synthesis-api-url` = ``; `--jev-synthesis-api-key` = ``; `--jev-synthesis-model` = ``; `--jev-synthesis-api-mode` = ``; `--validation-level` = ``; `--fallback-mode` = ``; `--minimum-profile` = ``; `--intent-router` = ``; `--search-timeout / --search-timeout-seconds` = ``; `--intent-embedding-api-url` = ``; `--intent-embedding-api-key` = ``; `--intent-embedding-model` = ``; `--intent-embedding-threshold` = ``; `--intent-embedding-margin` = ``; `--intent-classifier-api-url` = ``; `--intent-classifier-api-key` = ``; `--intent-classifier-model` = ``; `--intent-router-timeout` = ``; `--provider-cooldown / --provider-cooldown-seconds` = ``; `--provider-failure-threshold` = ``; `--exa-key` = ``; `--context7-key` = ``; `--zhipu-key` = ``; `--zhipu-api-url` = ``; `--zhipu-search-engine` = ``; `--zhipu-mcp-key` = ``; `--zhipu-mcp-search-api-url` = ``; `--zhipu-mcp-reader-api-url` = ``; `--zhipu-mcp-zread-api-url` = ``; `--zhipu-mcp-timeout` = ``; `--jina-key` = ``; `--jina-reader-api-url` = ``; `--jina-respond-with` = ``; `--jina-timeout` = ``; `--tavily-api-url` = ``; `--tavily-key` = ``; `--firecrawl-api-url` = ``; `--firecrawl-key` = ``; `--tinyfish-key` = ``; `--tinyfish-search-api-url` = ``; `--tinyfish-fetch-api-url` = ``; `--tinyfish-timeout` = ``; `--anysearch-api-url` = ``; `--anysearch-key` = ``; `--anysearch-timeout` = ``; `--sciverse-api-url` = ``; `--sciverse-token` = ``; `--sciverse-timeout` = ``; `--format` = `json`; `--output` = ``.

## `smart-search config`

Aliases: `cfg`

```text
usage: smart-search config [-h] [--lang {auto,zh,en}]
                           {path,p,list,ls,l,set,s,unset,rm,u} ...

positional arguments:
  {path,p,list,ls,l,set,s,unset,rm,u}

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
```

## `smart-search config path`

Aliases: `p`

```text
usage: smart-search config path [-h] [--lang {auto,zh,en}]
                                [--format {json,markdown,content}]
                                [--output OUTPUT]

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  --format {json,markdown,content}
  --output OUTPUT       Write rendered output to a file.
```

Parser defaults: `--format` = `json`; `--output` = ``.

## `smart-search config list`

Aliases: `ls`, `l`

```text
usage: smart-search config list [-h] [--lang {auto,zh,en}]
                                [--format {json,markdown,content}]
                                [--output OUTPUT]

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  --format {json,markdown,content}
  --output OUTPUT       Write rendered output to a file.
```

Parser defaults: `--format` = `json`; `--output` = ``.

## `smart-search config set`

Aliases: `s`

```text
usage: smart-search config set [-h] [--lang {auto,zh,en}]
                               [--format {json,markdown,content}]
                               [--output OUTPUT]
                               key value

positional arguments:
  key
  value

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  --format {json,markdown,content}
  --output OUTPUT       Write rendered output to a file.
```

Parser defaults: `--format` = `json`; `--output` = ``.

## `smart-search config unset`

Aliases: `rm`, `u`

```text
usage: smart-search config unset [-h] [--lang {auto,zh,en}]
                                 [--format {json,markdown,content}]
                                 [--output OUTPUT]
                                 key

positional arguments:
  key

options:
  -h, --help            show this help message and exit
  --lang {auto,zh,en}   Interface language for this call; does not change the
                        saved preference.
  --format {json,markdown,content}
  --output OUTPUT       Write rendered output to a file.
```

Parser defaults: `--format` = `json`; `--output` = ``.

## `smart-search regression`

Aliases: `reg`

```text
usage: smart-search regression [-h] [--lang {auto,zh,en}]

options:
  -h, --help           show this help message and exit
  --lang {auto,zh,en}  Interface language for this call; does not change the
                       saved preference.
```
