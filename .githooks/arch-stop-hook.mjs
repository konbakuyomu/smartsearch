#!/usr/bin/env node
// Claude Code Stop hook：会话结束前，结构路径改了而规格没改，就提醒一句（不阻塞）。
// 设 ARCH_CHECK_STRICT=1 时改为 block，让 Claude 先补规格再结束。
// settings.json：
//   "hooks": { "Stop": [ { "hooks": [ { "type": "command", "command": "node \"<dev-board>/scripts/arch-stop-hook.mjs\"", "timeout": 20 } ] } ] }
import { spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

let input = {};
try { input = JSON.parse(readFileSync(0, 'utf8') || '{}'); } catch { /* 无输入也能跑 */ }
if (input.stop_hook_active) process.exit(0); // 已经因为本 hook 续跑过一次，不再循环

const cwd = input.cwd || process.cwd();
const checker = join(dirname(fileURLToPath(import.meta.url)), 'arch-check.mjs');
const result = spawnSync(process.execPath, [checker, 'check', '--repo', cwd, '--worktree', '--no-fail'], { encoding: 'utf8' });
const out = (result.stdout || '') + (result.stderr || '');
// 取 ✗ 开头的行，连同它后面缩进的说明行
const problems = [];
let keep = false;
for (const l of out.split(/\r?\n/)) {
  if (l.startsWith('✗')) { keep = true; problems.push(l); continue; }
  if (keep && /^\s+\S/.test(l)) { problems.push(l); continue; }
  keep = false;
}
if (!problems.length) process.exit(0);

const text = `arch-check 在工作区发现未同步的知识：\n${problems.join('\n')}\n结束前先按提示补规格、笔记或 ff 的 codestable 一栏，再提交。`;
if (process.env.ARCH_CHECK_STRICT === '1') {
  console.log(JSON.stringify({ decision: 'block', reason: text }));
} else {
  console.log(JSON.stringify({ hookSpecificOutput: { hookEventName: 'Stop', additionalContext: text } }));
}
