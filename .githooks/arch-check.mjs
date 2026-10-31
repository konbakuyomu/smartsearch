#!/usr/bin/env node
// arch-check：让"代码变了、知识没跟上"在提交时就失败。零依赖，Node 18+。
//
//   node arch-check.mjs check [--repo <路径>] [--staged | --range <A..B> | --worktree] [--no-fail]
//   node arch-check.mjs tidy  [--repo <路径>] [--older-than 90] [--apply]
//
// 布局自动识别：有 codestable/spec/index.md 按 CodeStable-Lite 处理，否则按 ARCHITECTURE.md 处理。
// 结构路径写在仓库根目录 .arch-check.json：{"structural": ["src/**", "firmware/**"]}。
// 规则（见设计稿 §5 第 1 层）：
//   1. 改了结构路径，就必须同提交改现状规格 / 决定笔记，或者本次 ff / Issue 的 codestable 一栏写明影响。
//   2. ff 声明"已同步 spec/x"，spec/x 必须在同一次提交里。
//   3. 文件名含 -x- 的 Issue 必须 status: closed，ff 要有四答，常规 Issue 要有非空「关闭时」并同提交回写。
//   4. AGENTS.md / CLAUDE.md / 现状规格 / notes 里反引号包的仓库路径必须存在（本次改过的文件算错误，其他算警告）。
//   5. 现状规格入口超过 150 行给警告。
import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { basename, dirname, join, relative, resolve } from 'node:path';

const argv = process.argv.slice(2);
const command = argv[0] && !argv[0].startsWith('--') ? argv[0] : 'check';
const option = (name, fallback) => { const i = argv.indexOf(name); return i >= 0 ? (argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[i + 1] : true) : fallback; };
const has = (name) => argv.includes(name);

const gitExe = process.platform === 'win32' && existsSync('D:\\scoop\\shims\\git.exe') ? 'D:\\scoop\\shims\\git.exe' : 'git';
const start = resolve(String(option('--repo', process.cwd())));
const repo = execFileSync(gitExe, ['-C', start, 'rev-parse', '--show-toplevel'], { encoding: 'utf8' }).trim().replace(/\\/g, '/');
const git = (...a) => execFileSync(gitExe, ['-C', repo, '-c', 'core.quotepath=off', ...a], { encoding: 'utf8' });
const tryGit = (...a) => { try { return git(...a); } catch { return ''; } };
const slash = (p) => p.replace(/\\/g, '/');
const lines = (s) => s.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);

// ---------- 配置与布局 ----------
const configPath = join(repo, '.arch-check.json');
const config = existsSync(configPath) ? JSON.parse(readFileSync(configPath, 'utf8')) : {};
const lite = existsSync(join(repo, 'codestable/spec/index.md'));
const specGlobs = config.spec ?? (lite ? ['codestable/spec/**'] : ['ARCHITECTURE.md', 'docs/ARCHITECTURE.md']);
const knowledgeGlobs = [...specGlobs, '.agents/notes/**', ...(lite ? ['codestable/notes/**', 'codestable/epics/**/spec.md'] : [])];
const docGlobs = config.docs ?? ['AGENTS.md', 'CLAUDE.md', 'ARCHITECTURE.md', 'GLOSSARY.md', 'codestable/spec/**/*.md', 'codestable/notes/**/*.md'];
const issueGlob = 'codestable/**/issues/**/*.md';
const structuralGlobs = config.structural ?? [];
const specEntry = lite ? 'codestable/spec/index.md' : (existsSync(join(repo, 'ARCHITECTURE.md')) ? 'ARCHITECTURE.md' : 'docs/ARCHITECTURE.md');

function globToRegExp(glob) {
  const escaped = glob.replace(/[.+^${}()|[\]\\]/g, '\\$&')
    .replace(/\*\*\//g, '\u0000').replace(/\*\*/g, '\u0001').replace(/\*/g, '[^/]*').replace(/\?/g, '[^/]')
    .replace(/\u0000/g, '(?:.*/)?').replace(/\u0001/g, '.*');
  return new RegExp(`^${escaped}$`);
}
const matchAny = (globs) => { const res = globs.map(globToRegExp); return (p) => res.some((r) => r.test(p)); };
const isStructural = matchAny(structuralGlobs);
const isKnowledge = matchAny(knowledgeGlobs);
const isSpec = matchAny(specGlobs);
const isDoc = matchAny(docGlobs);
const isIssue = (p) => globToRegExp(issueGlob).test(p) && /^\d{3,}-[ox]-/.test(basename(p));

function walk(dir, out = []) {
  if (!existsSync(dir)) return out;
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === '.git' || entry.name === 'node_modules') continue;
    const full = join(dir, entry.name);
    if (entry.isDirectory()) walk(full, out); else out.push(slash(relative(repo, full)));
  }
  return out;
}

// ---------- 改动集 ----------
// 纯改名（R100，比如 tidy 把 ff 挪进 done/）算"位置变了"，不算"内容变了"：参与同提交判断，但不重新验证它的声明。
const mode = has('--range') ? 'range' : has('--worktree') ? 'worktree' : 'staged';
let renamedOnly = new Set();
function parseStatus(raw) {
  const out = [];
  for (const line of raw.split(/\r?\n/)) {
    if (!line.trim()) continue;
    const [status, a, b] = line.split('\t');
    const path = b ?? a;
    if (!path) continue;
    if (status === 'D') continue;
    if (/^R100/.test(status)) renamedOnly.add(path);
    out.push(path);
  }
  return out;
}
function changedFiles() {
  renamedOnly = new Set();
  if (mode === 'range') return parseStatus(git('diff', '--name-status', '-M', String(option('--range'))));
  if (mode === 'worktree') {
    const tracked = parseStatus(tryGit('diff', '--name-status', '-M', 'HEAD'));
    return [...new Set([...tracked, ...lines(git('ls-files', '--others', '--exclude-standard'))])];
  }
  return parseStatus(git('diff', '--cached', '--name-status', '-M'));
}
function content(path) {
  if (mode === 'staged') { const staged = tryGit('show', `:${path}`); if (staged) return staged; }
  const full = join(repo, path);
  return existsSync(full) ? readFileSync(full, 'utf8') : '';
}

// ---------- Issue / ff 解析 ----------
function analyzeIssue(path) {
  const text = content(path);
  const name = basename(path);
  const closed = /^\d{3,}-x-/.test(name);
  const ff = /^\d{3,}-[ox]-ff-/.test(name);
  const statusClosed = /^status:\s*closed\s*$/m.test(text);
  const impactLine = /^\s*[-*]?\s*codestable\s*[:：]\s*(.+)$/im.exec(text)?.[1]?.trim() ?? '';
  const impact = !impactLine ? 'missing' : /无影响/.test(impactLine) ? 'none' : /已同步/.test(impactLine) ? 'synced' : /漂移/.test(impactLine) ? 'drift' : /升级/.test(impactLine) ? 'escalate' : 'other';
  const declared = [...impactLine.matchAll(/`([^`]+)`|((?:codestable\/)?(?:spec|notes)\/[^\s，,;；)）]+)/g)].map((m) => (m[1] ?? m[2]).trim()).filter(Boolean);
  const fourAnswers = ['改动', '验证', 'codestable'].filter((k) => !new RegExp(`^\\s*[-*]\\s*${k}`, 'im').test(text));
  const closeSection = /^##\s*关闭时[^\n]*\n([\s\S]*?)(?=^##\s|(?![\s\S]))/m.exec(text)?.[1] ?? '';
  const closeBody = closeSection.replace(/\[[^\]]*\]/g, '').split(/\r?\n/).filter((l) => !/^\s*[-*]?\s*(回写[^：:]*|关闭判断[^：:]*|遗留)[：:]\s*$/.test(l)).join('\n').trim();
  const noWriteBack = /无需回写|不回写|无回写|回写[^\n]*[：:]\s*无\b/.test(closeSection);
  return { path, ff, closed, statusClosed, impact, impactLine, declared, fourAnswers, closeBody, noWriteBack };
}

// ---------- 引用检查 ----------
function references(path) {
  const text = content(path).replace(/```[\s\S]*?```/g, '');
  const out = [];
  for (const m of text.matchAll(/`([^`\n]+)`/g)) {
    let t = m[1].trim();
    if (/\s/.test(t) || /^https?:|^[A-Za-z]:[\\/]|^~|^\/|[<>{}*$()|]|^-{1,2}[A-Za-z]/.test(t)) continue;
    if (!/[\\/]|\.(md|c|h|cpp|hpp|py|ts|tsx|js|mjs|json|ya?ml|toml|ps1|cmd|txt|sh|kicad_pcb|kicad_sch|base)$/i.test(t)) continue;
    const isDir = /[\\/]$/.test(t);
    t = t.replace(/[:#]\d+(?:[-–]\d+)?$/, '').replace(/[\\/]+$/, '').replace(/\\/g, '/');
    if (!t || t === '.' || t === '..') continue;
    // 依次按仓库根、文档所在目录及其每一级上级目录解析（Lite 的 spec 常写成相对 codestable/ 的 issues/NNN-…）
    const bases = [repo];
    for (let d = dirname(path); d && d !== '.'; d = dirname(d)) bases.push(join(repo, d));
    // 以 / 结尾的是目录：目录本身或它的上级存在就算（空目录不进 git，按需创建是常态）
    const found = bases.some((b) => existsSync(join(b, t)) || (isDir && existsSync(join(b, dirname(t)))));
    if (!found) out.push(t);
  }
  return [...new Set(out)];
}

// ---------- check ----------
function check() {
  const errors = [], warnings = [], notes = [];
  const changed = changedFiles();
  if (!structuralGlobs.length) warnings.push(`没有 .arch-check.json 或其中没有 structural：结构路径同提交检查没有生效。写法：{"structural": ["src/**", "firmware/**"]}`);
  const structural = changed.filter(isStructural);
  const knowledge = changed.filter(isKnowledge);
  const issues = changed.filter((p) => isIssue(p) && !renamedOnly.has(p)).map(analyzeIssue);
  for (const p of changed.filter((p) => isIssue(p) && renamedOnly.has(p))) notes.push(`${p}：只是改名或移动，不重新验证`);

  for (const i of issues) {
    const tag = relative(repo, join(repo, i.path)).replace(/\\/g, '/');
    if (i.ff) {
      if (i.impact === 'missing') errors.push(`${tag}：ff 缺少「codestable」一栏。按模板补一行：- codestable：无影响 / 已同步 \`spec/<页>\` / 已知漂移：<原因> / 应升级完整流程：<原因>`);
      if (i.closed && i.fourAnswers.length) errors.push(`${tag}：已关闭的 ff 缺少四答里的「${i.fourAnswers.join('、')}」`);
      if (i.closed && !i.statusClosed) errors.push(`${tag}：文件名是 -x-，但正文没有 status: closed`);
      if (i.impact === 'synced') {
        const targets = i.declared.map((d) => d.replace(/^\.\//, '').replace(/^codestable\//, 'codestable/'));
        const normalized = targets.map((t) => (t.startsWith('codestable/') ? t : `codestable/${t}`));
        const missing = normalized.filter((t) => !changed.some((c) => c === t || c.startsWith(`${t.replace(/\/$/, '')}/`)));
        if (!targets.length) errors.push(`${tag}：codestable 一栏写了「已同步」，但没写同步到哪个 spec 页。写成：已同步 \`spec/<页>.md\``);
        else if (missing.length) errors.push(`${tag}：声明已同步 ${missing.join('、')}，但这些文件不在本次提交里。把对应 spec 改动一起暂存，或把一栏改成「已知漂移：<原因>」`);
      }
      if (i.impact === 'drift' || i.impact === 'escalate') notes.push(`${tag}：codestable 一栏为「${i.impactLine}」，已记入园丁待办`);
    } else if (i.closed) {
      if (!i.statusClosed) errors.push(`${tag}：文件名是 -x-，但正文没有 status: closed`);
      if (i.closeBody.length < 10) errors.push(`${tag}：已关闭的 Issue 没有写「关闭时」：回写到哪里、关闭判断与验证摘要、遗留。按 close.md 毕业后再关`);
      else if (!knowledge.length && !i.noWriteBack) errors.push(`${tag}：Issue 已关闭，但本次提交没有改现状规格或笔记。Lite 的关闭契约是毕业回写与关闭同一 commit；确实无需回写就在「关闭时」写明「无需回写」`);
      if (/排除|取舍|备选|不选|否掉/.test(content(i.path)) && !changed.some((c) => c.startsWith('.agents/notes/'))) {
        warnings.push(`${tag}：方案里有取舍或被排除的做法，但本次没有 .agents/notes 决定笔记。过得了「非平凡」闸的决定要写 DSH 笔记并在 Issue 里链接，看板才看得到`);
      }
    } else {
      notes.push(`${tag}：开放中的 Issue 随本次提交更新`);
    }
  }

  if (structural.length) {
    const tracked = issues.some((i) => (i.ff && i.impact !== 'missing') || (!i.ff && (!i.closed || i.closeBody.length >= 10)));
    if (!knowledge.length && !tracked) {
      errors.push([
        `结构路径有改动，但现状规格没有同提交更新，本次也没有 ff / Issue 说明影响：`,
        `    改动：${structural.slice(0, 8).join(', ')}${structural.length > 8 ? ` 等 ${structural.length} 个` : ''}`,
        lite
          ? `    需要（任选其一）：改 codestable/spec/ 下相应页面并一起暂存；或在本次 ff / Issue 的「codestable」一栏写明「无影响」「已同步 spec/<页>」或「已知漂移：<原因>」；或写一篇 .agents/notes 决定笔记`
          : `    需要（任选其一）：更新 ${specEntry} 的现状段或不变量；或写一篇 .agents/notes 决定笔记；确属无关结构的目录就从 .arch-check.json 的 structural 里去掉`,
      ].join('\n'));
    } else if (!knowledge.length) {
      notes.push(`结构路径改动 ${structural.length} 个文件，规格未变；本次 ff / Issue 已声明影响`);
    }
  }

  const docs = walk(repo).filter(isDoc);
  for (const doc of docs) {
    const missing = references(doc);
    if (!missing.length) continue;
    const message = `${doc} 引用了不存在的路径：${missing.slice(0, 6).join('、')}${missing.length > 6 ? ` 等 ${missing.length} 处` : ''}`;
    (changed.includes(doc) ? errors : warnings).push(changed.includes(doc) ? `${message}。改成现有路径，或去掉反引号` : message);
  }

  if (existsSync(join(repo, specEntry))) {
    const n = readFileSync(join(repo, specEntry), 'utf8').split(/\r?\n/).length;
    if (n > 150) warnings.push(`${specEntry} 有 ${n} 行，超过 150 行；只保留慢变量，把细节下沉到子页或证据索引`);
  }

  for (const n of notes) console.log(`· ${n}`);
  for (const w of warnings) console.log(`! ${w}`);
  for (const e of errors) console.log(`✗ ${e}`);
  if (!errors.length) console.log(`✓ arch-check 通过（${mode}，改动 ${changed.length} 个文件，结构 ${structural.length}，知识 ${knowledge.length}）`);
  process.exit(errors.length && !has('--no-fail') ? 1 : 0);
}

// ---------- tidy：把久未引用的已关闭 ff 挪进 done/ ----------
function tidy() {
  const days = Number(option('--older-than', 90));
  const apply = has('--apply');
  const all = walk(repo);
  const candidates = all.filter((p) => isIssue(p) && /^\d{3,}-x-ff-/.test(basename(p)) && !/\/done\//.test(p));
  const haystack = all.filter((p) => /\.md$/i.test(p) && (p.startsWith('codestable/') || p.startsWith('.agents/notes/') || /^(AGENTS|CLAUDE|ARCHITECTURE|GLOSSARY)\.md$/.test(p)));
  const now = Date.now();
  let moved = 0;
  for (const p of candidates) {
    const last = tryGit('log', '-1', '--format=%cs', '--', p).trim();
    const age = last ? Math.floor((now - Date.parse(last)) / 86400000) : 0;
    if (age < days) continue;
    const name = basename(p);
    const referenced = haystack.some((h) => h !== p && readFileSync(join(repo, h), 'utf8').includes(name));
    if (referenced) { console.log(`· 保留 ${p}（仍被引用）`); continue; }
    const target = join(dirname(p), 'done', name);
    if (apply) {
      mkdirSync(join(repo, dirname(p), 'done'), { recursive: true });
      git('mv', p, slash(target));
      moved++;
      console.log(`→ ${p} → ${slash(target)}`);
    } else console.log(`候选 ${p}（${age} 天未动，无引用）`);
  }
  console.log(apply ? `✓ 已移动 ${moved} 个文件到 done/（已 git mv，未提交）` : `✓ 预览结束；加 --apply 执行`);
}

if (command === 'tidy') tidy(); else check();
