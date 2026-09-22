"""Expose focused configuration tests using the existing argparse contract."""
from __future__ import annotations

import argparse
from functools import lru_cache

from .cli import build_parser
from .i18n import tr

_TEST_COMMANDS = {"search", "fetch", "context7-library", "context7-docs", "route", "smoke"}
_LABELS = {'search': '搜索',
 'route': '查看路由',
 'fetch': '读取网页',
 'smoke': '冒烟检查',
 'context7-library': 'Context7 查找库',
 'context7-docs': 'Context7 查文档'}
_FIELD_LABELS = {'query': '问题或关键词',
 'url': '网页地址',
 'library_id': '库标识',
 'name': '名称',
 'timeout': '超时（秒）',
 'model': '模型',
 'output': '输出文件（可选）',
 'router_mode': '路由方式',
 'validation': '验证程度',
 'fallback': '回退策略',
 'providers': '服务商筛选',
 'extra_sources': '额外来源数量',
 'stream': '启用流式请求',
 'no_stream': '禁用流式请求',
 'remote': '允许远程路由判断'}


# argparse help strings are written for `--help` and are English. Reflecting them
# straight into a Chinese window put "Run OpenAI-compatible web search." on the
# tools page, so these two tables carry the user-facing wording instead. Anything
# not listed falls back to the original help, which keeps new commands working.
_DESCRIPTIONS = {'search': '问一个问题，让主搜索模型联网回答，并带回可点开的来源。',
 'route': '默认只预览本地可用能力；勾选远程判断会调用路由服务，但不执行搜索。',
 'fetch': '把一个网页地址读成干净正文。',
 'context7-library': '按名字找到对应的开源库标识。',
 'context7-docs': '读取某个开源库的文档。',
 'smoke': '用假数据走一遍路由和兜底逻辑，不碰真实服务商。'}
_FIELD_HELP = {'query': '要问的问题或关键词。',
 'url': '完整网页地址，需带 http:// 或 https://。',
 'library_id': '开源库标识，可先用「Context7 查找库」拿到。',
 'name': '要查找的库名。',
 'timeout': '这一条命令的总时间上限（秒），会覆盖全局设置。',
 'model': '本次改用哪个模型，留空用当前配置。',
 'output': '把渲染后的结果另存到这个文件。',
 'router_mode': '本次改用哪种路由方式，仅影响这一次调用。',
 'remote': '明确允许远程路由判断，可能计费；默认关闭，且不执行检索。',
 'validation': '结果核验的严格程度，越严越慢。',
 'fallback': '一家失败后要不要自动换下一家。',
 'providers': '限定只用哪些服务商，留空由路由决定。',
 'extra_sources': '在主结果之外额外并行发现多少条来源。',
 'stream': '对 OpenAI 兼容接口启用流式请求。部分服务只有流式下才肯长时间思考。',
 'no_stream': '对 OpenAI 兼容接口禁用流式请求。',
 'mode': '已废弃的兼容别名，等价于 --retrieval hybrid。',
 'live': '跑真实服务商的冒烟检查，会发网络请求。',
 'mock': '跑离线冒烟检查，不碰真实服务商。'}


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
                if not tokens and name not in _TEST_COMMANDS:
                    continue
                identifier = "/".join((*tokens, name))
                description = _DESCRIPTIONS.get(identifier) or next(
                    (a.help for a in sub._choices_actions if a.dest == name), "")
                visit(child, (*tokens, name), description)
            return
        fields = []
        for arg in parser._actions:
            if arg.dest in {"help", "format", "lang"} or arg.help == argparse.SUPPRESS:
                continue
            flags = [s for s in arg.option_strings if s.startswith("--")]
            if isinstance(arg, (argparse._StoreTrueAction, argparse._StoreFalseAction)):
                kind, default = "bool", False
            else:
                kind = "choice" if arg.choices else "int" if arg.type is int else "float" if arg.type is float else "text"
                default = None if arg.default == argparse.SUPPRESS else arg.default
            field_name = flags[0][2:].replace("-", "_") if flags else arg.dest
            fields.append({"name": field_name,
                           "label": tr(_FIELD_LABELS.get(field_name, flags[0] if flags else arg.dest)),
                           "help": tr(_FIELD_HELP.get(field_name) or arg.help or ""), "flags": flags[:1],
                           "kind": kind, "choices": list(arg.choices or []), "required": arg.required,
                           "default": default, "multiple": isinstance(arg, argparse._AppendAction) or arg.nargs in {"+", "*"},
                           "nargs": arg.nargs, "advanced": bool(flags) and arg.dest not in {"budget", "evidence_dir"}})
        identifier = "/".join(tokens)
        entries.append({"id": identifier, "label": tr(_LABELS.get(identifier, identifier)),
                        "description": tr(_DESCRIPTIONS.get(identifier) or help_text or parser.description or ""),
                        "fields": fields,
                        "experimental": tokens[0].startswith(("anysearch-", "sciverse-"))})

    visit(build_parser())
    return entries


def command_arguments(command: str, arguments: list[str]) -> list[str]:
    if command not in {item["id"] for item in command_catalog()}:
        raise ValueError(tr("未知或不可从工具页调用的命令。"))
    if not isinstance(arguments, list) or any(not isinstance(arg, str) for arg in arguments):
        raise ValueError(tr("arguments 必须是字符串数组。"))
    if len(arguments) > 256 or sum(len(arg) for arg in arguments) > 256 * 1024:
        raise ValueError(tr("命令参数过长。"))
    if any(arg in {"--format", "-h", "--help"} or arg.startswith("--format=") for arg in arguments):
        raise ValueError(tr("桌面结果格式由 App 管理。"))
    return [*command.split("/"), *arguments]
