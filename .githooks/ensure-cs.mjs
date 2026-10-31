#!/usr/bin/env node
// Claude Code 的 SessionStart hook：让 CodeStable-Lite 仓的 /cs 在会话里可用。
// 上游 CodeStable-Lite 没有许可证，技能不能提交进项目仓（公开仓等于再分发），所以按固定提交现取到
// .claude/skills/cs，这个目录必须被 .gitignore 忽略。board setup --lite 把本文件复制进项目的 .githooks/。
//
// 云端会话（CLAUDE_CODE_REMOTE=true）或带 --install 时：没设 core.hooksPath 就设成 .githooks，缺技能或
// 已装的不是下面钉住的提交（看技能目录里 UPSTREAM 的 commit 行）就安装。本地这两种情况只提示一句。
// 已是钉住的版本时什么都不输出。同步运行（会话等它结束，通常 2 秒），任何失败都只提示，退出码恒为 0。
// 取下来的上游临时检出留在系统临时目录，不做递归删除。
import { spawnSync } from 'node:child_process';
import { cpSync, existsSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const UPSTREAM = 'https://github.com/codestable/CodeStable-Lite';
const COMMIT = 'bf8ecc872cc4dbaec234ed4051df53bcceeed5f3';
const SKILL_DIR = 'skills/cs';

const repo = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const target = join(repo, '.claude', 'skills', 'cs');
const install = process.env.CLAUDE_CODE_REMOTE === 'true' || process.argv.includes('--install');
const git = (args, cwd) => spawnSync('git', args, { cwd, encoding: 'utf8', timeout: 40_000 });
const short = COMMIT.slice(0, 7);

if (install && !git(['config', '--get', 'core.hooksPath'], repo).stdout?.trim()) {
  git(['config', 'core.hooksPath', '.githooks'], repo);
}
const installed = (() => {
  try { return /^commit:\s*(\S+)/m.exec(readFileSync(join(target, 'UPSTREAM'), 'utf8'))?.[1] ?? '未知'; } catch { return existsSync(join(target, 'SKILL.md')) ? '未知' : ''; }
})();
if (installed === COMMIT) process.exit(0);
if (!install) {
  console.log(installed
    ? `本机的 /cs 是 ${installed.slice(0, 7)}，仓里钉的是 ${short}：要换就运行 node .githooks/ensure-cs.mjs --install。`
    : `本仓用 /cs（CodeStable-Lite），这台机器还没装：运行 node .githooks/ensure-cs.mjs --install（取 ${UPSTREAM} 的 ${short}）。`);
  process.exit(0);
}

const tmp = mkdtempSync(join(tmpdir(), 'codestable-lite-'));
const steps = [
  ['init', '-q'],
  ['fetch', '-q', '--depth', '1', `${UPSTREAM}.git`, COMMIT],
  ['-c', 'advice.detachedHead=false', 'checkout', '-q', 'FETCH_HEAD'],
];
for (const args of steps) {
  const r = git(args, tmp);
  if (r.status !== 0) {
    const why = (r.stderr || r.error?.message || `退出码 ${r.status}`).trim().split('\n')[0];
    console.log(`/cs 没装上：git ${args.filter((a) => !a.startsWith('-') && !a.includes('=')).at(0)} 失败（${why}）。这次会话按 AGENTS.md 的规则直接走流程；网络放行 github.com 后运行 node .githooks/ensure-cs.mjs --install。`);
    process.exit(0);
  }
}
if (!existsSync(join(tmp, SKILL_DIR, 'SKILL.md'))) {
  console.log(`/cs 没装上：上游 ${short} 里没有 ${SKILL_DIR}/SKILL.md。这次会话按 AGENTS.md 的规则直接走流程。`);
  process.exit(0);
}
cpSync(join(tmp, SKILL_DIR), target, { recursive: true });
writeFileSync(join(target, 'UPSTREAM'), [
  `source: ${UPSTREAM}`,
  `commit: ${COMMIT}`,
  `path: ${SKILL_DIR}`,
  `installed: ${new Date().toISOString().slice(0, 10)} by .githooks/ensure-cs.mjs（不提交，不改上游文件）`,
  '',
].join('\n'));
console.log(`已把 /cs（CodeStable-Lite ${short}）装到 .claude/skills/cs。技能列表里还没有 cs 时，直接读 .claude/skills/cs/SKILL.md 按它做。`);
