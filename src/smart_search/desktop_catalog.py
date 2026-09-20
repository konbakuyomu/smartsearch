"""Expose the existing argparse contract to both native frontends."""
from __future__ import annotations

import argparse
from functools import lru_cache

from .cli import build_parser

_MANAGED = {"setup", "config", "skills", "providers", "ui"}
_LABELS = {"search": "搜索", "route": "查看路由", "deep": "离线研究计划", "research": "在线研究",
           "fetch": "读取网页", "map": "站点地图", "doctor": "服务商全面诊断（在线）",
           "smoke": "冒烟检查", "regression": "离线回归检查", "model/current": "当前模型",
           "route-calibrate": "校准意图路由", "exa-search": "Exa 搜索", "exa-similar": "Exa 相似网页",
           "zhipu-search": "智谱搜索", "zhipu-mcp-search": "智谱 MCP 搜索", "zhipu-mcp-reader": "智谱 MCP 网页阅读",
           "zhipu-mcp-search-doc": "智谱 仓库文档检索", "zhipu-mcp-repo-structure": "智谱 仓库目录",
           "zhipu-mcp-read-file": "智谱 仓库文件阅读", "context7-library": "Context7 查找库", "context7-docs": "Context7 查文档",
           "anysearch-domains": "AnySearch 查询领域", "anysearch-search": "AnySearch 搜索", "anysearch-extract": "AnySearch 读取网页",
           "anysearch-batch": "AnySearch 批量搜索", "sciverse-catalog": "SciVerse 目录", "sciverse-search": "SciVerse 搜索",
           "sciverse-semantic": "SciVerse 语义搜索", "sciverse-read": "SciVerse 文献阅读", "sciverse-relations": "SciVerse 关联检索",
           "diagnose": "诊断 OpenAI 兼容接口"}
_FIELD_LABELS = {"query": "问题或关键词", "queries": "问题列表（每行一项）", "url": "网页地址",
                 "diagnose_target": "排查对象", "repo": "代码仓库", "path": "文件路径", "library_id": "库标识", "name": "名称",
                 "budget": "研究深度", "timeout": "超时（秒）", "model": "模型", "output": "输出文件（可选）",
                 "evidence_dir": "研究证据目录", "ref": "分支或版本", "count": "结果数量", "num_results": "结果数量",
                 "router_mode": "路由方式", "validation": "验证程度", "fallback": "回退策略", "providers": "服务商筛选",
                 "extra_sources": "额外来源数量", "stream": "启用流式请求", "no_stream": "禁用流式请求"}


# argparse help strings are written for `--help` and are English. Reflecting them
# straight into a Chinese window put "Run OpenAI-compatible web search." on the
# tools page, so these two tables carry the user-facing wording instead. Anything
# not listed falls back to the original help, which keeps new commands working.
_DESCRIPTIONS = {
    "search": "问一个问题，让主搜索模型联网回答，并带回可点开的来源。",
    "route": "只看这个问题会用到哪几类能力，不发任何网络请求，也不花钱。",
    "route-calibrate": "评估向量路由模型，给出推荐的阈值和间距。",
    "fetch": "把一个网页地址读成干净正文。",
    "map": "列出一个站点的结构。",
    "exa-search": "指定用 Exa 搜索，结果只来自这一家。",
    "exa-similar": "用 Exa 找出和某个网页相似的页面。",
    "zhipu-search": "指定用智谱搜索，结果只来自这一家。",
    "zhipu-mcp-search": "用智谱 Coding Plan 额度搜索。",
    "zhipu-mcp-reader": "用智谱 Coding Plan 额度读取网页正文。",
    "zhipu-mcp-search-doc": "在某个代码仓库的文档里检索。",
    "zhipu-mcp-repo-structure": "列出某个代码仓库的目录结构。",
    "zhipu-mcp-read-file": "读取某个代码仓库里的一个文件。",
    "anysearch-domains": "列出 AnySearch 支持的垂直领域。实验性能力。",
    "anysearch-search": "在指定垂直领域里搜索。实验性能力。",
    "anysearch-extract": "用 AnySearch 读取一个网页。实验性能力。",
    "anysearch-batch": "一次并行跑最多 5 条 AnySearch 查询。实验性能力。",
    "sciverse-catalog": "列出 Sciverse 学术库可用的检索字段。实验性能力。",
    "sciverse-search": "按结构化条件检索学术论文。实验性能力，需显式指定。",
    "sciverse-semantic": "按语义相似度检索学术论文。实验性能力，需显式指定。",
    "sciverse-read": "按文献 ID 读取正文片段。实验性能力。",
    "sciverse-relations": "查一篇论文的引用与被引关系。实验性能力。",
    "context7-library": "按名字找到对应的开源库标识。",
    "context7-docs": "读取某个开源库的文档。",
    "deep": "只生成研究计划，不联网、不花钱，用来先看它打算怎么查。",
    "research": "真正执行深度研究：拆子问题、找来源、抓正文、核对后给结论。耗时较长。",
    "smoke": "用假数据走一遍路由和兜底逻辑，不碰真实服务商。",
    "doctor": "逐个探测已配置的服务商是否可用。会对每一家发真实请求，可能计费。",
    "diagnose": "针对 OpenAI 兼容接口做一次定向排查。",
    "model/current": "显示当前生效的主搜索模型。",
    "regression": "离线跑一遍命令行回归检查，不联网。",
}
_FIELD_HELP = {
    "query": "要问的问题或关键词。",
    "queries": "多条查询，每行一条。",
    "url": "完整网页地址，需带 http:// 或 https://。",
    "diagnose_target": "要排查哪一路接口。",
    "repo": "代码仓库，形如 owner/name。",
    "path": "仓库内的文件路径。",
    "library_id": "开源库标识，可先用「Context7 查找库」拿到。",
    "name": "要查找的库名。",
    "budget": "研究深度。越深越慢，来源也越多。",
    "timeout": "这一条命令的总时间上限（秒），会覆盖全局设置。",
    "model": "本次改用哪个模型，留空用当前配置。",
    "output": "把渲染后的结果另存到这个文件。",
    "evidence_dir": "研究过程中抓到的证据存放目录。",
    "ref": "分支名、标签或提交号，留空用默认分支。",
    "count": "返回多少条结果。",
    "num_results": "返回多少条结果。",
    "router_mode": "本次改用哪种路由方式，仅影响这一次调用。",
    "validation": "结果核验的严格程度，越严越慢。",
    "fallback": "一家失败后要不要自动换下一家。",
    "providers": "限定只用哪些服务商，留空由路由决定。",
    "extra_sources": "在主结果之外额外并行发现多少条来源。",
    "stream": "对 OpenAI 兼容接口启用流式请求。部分服务只有流式下才肯长时间思考。",
    "no_stream": "对 OpenAI 兼容接口禁用流式请求。",
    # 实验性命令的高级参数
    "authors": "作者名，多个用英文逗号分隔。",
    "journals": "期刊或来源名，多个用英文逗号分隔。",
    "subjects": "学科标签，多个用英文逗号分隔。",
    "source_types": "来源类型，可填 web 或 pdf，多个用英文逗号分隔。",
    "collection": "旧版选择器；填 authors 或 sources 会直接返回参数错误。",
    "filters_advanced": "Sciverse 字段过滤条件，JSON 数组。",
    "sort_advanced": "Sciverse 排序条件，JSON 数组。",
    "sub_domain_params": "转发给 AnySearch 的 sub_domain_params，JSON 对象。",
    "param": "可重复的 key=value，会覆盖上面 JSON 里的同名键。",
    "models": "要评估的向量模型名，多个用英文逗号分隔，留空用内置候选。",
    "mode": "已废弃的兼容别名，等价于 --retrieval hybrid。",
    "live": "跑真实服务商的冒烟检查，会发网络请求。",
    "mock": "跑离线冒烟检查，不碰真实服务商。",
}


@lru_cache(maxsize=1)
def command_catalog() -> list[dict]:
    entries = []

    def visit(parser, tokens=(), help_text=""):
        sub = next((a for a in parser._actions if isinstance(a, argparse._SubParsersAction)), None)
        if sub is not None:
            seen = set()
            for name, child in sub.choices.items():
                if id(child) in seen:
                    continue
                seen.add(id(child))
                if not tokens and name in _MANAGED:
                    continue
                if tokens == ("model",) and name != "current":
                    continue
                identifier = "/".join((*tokens, name))
                description = _DESCRIPTIONS.get(identifier) or next(
                    (a.help for a in sub._choices_actions if a.dest == name), "")
                visit(child, (*tokens, name), description)
            return
        fields = []
        for arg in parser._actions:
            if arg.dest in {"help", "format"} or arg.help == argparse.SUPPRESS:
                continue
            flags = [s for s in arg.option_strings if s.startswith("--")]
            if isinstance(arg, (argparse._StoreTrueAction, argparse._StoreFalseAction)):
                kind, default = "bool", False
            else:
                kind = "choice" if arg.choices else "int" if arg.type is int else "float" if arg.type is float else "text"
                default = None if arg.default == argparse.SUPPRESS else arg.default
            field_name = flags[0][2:].replace("-", "_") if flags else arg.dest
            fields.append({"name": field_name,
                           "label": _FIELD_LABELS.get(field_name, flags[0] if flags else arg.dest),
                           "help": _FIELD_HELP.get(field_name) or arg.help or "", "flags": flags[:1],
                           "kind": kind, "choices": list(arg.choices or []), "required": arg.required,
                           "default": default, "multiple": isinstance(arg, argparse._AppendAction) or arg.nargs in {"+", "*"},
                           "nargs": arg.nargs, "advanced": bool(flags) and arg.dest not in {"budget", "evidence_dir"}})
        identifier = "/".join(tokens)
        entries.append({"id": identifier, "label": _LABELS.get(identifier, identifier),
                        "description": _DESCRIPTIONS.get(identifier) or help_text or parser.description or "",
                        "fields": fields,
                        "experimental": tokens[0].startswith(("anysearch-", "sciverse-"))})

    visit(build_parser())
    return entries


def command_arguments(command: str, arguments: list[str]) -> list[str]:
    if command not in {item["id"] for item in command_catalog()}:
        raise ValueError("未知或不可从工具页调用的命令。")
    if not isinstance(arguments, list) or any(not isinstance(arg, str) for arg in arguments):
        raise ValueError("arguments 必须是字符串数组。")
    if len(arguments) > 256 or sum(len(arg) for arg in arguments) > 256 * 1024:
        raise ValueError("命令参数过长。")
    if any(arg in {"--format", "-h", "--help"} or arg.startswith("--format=") for arg in arguments):
        raise ValueError("桌面结果格式由 App 管理。")
    return [*command.split("/"), *arguments]
