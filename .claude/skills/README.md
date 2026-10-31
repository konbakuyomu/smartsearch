# .claude/skills

这个目录要在会话开始前就存在：Claude Code 只监视会话开始时已有的技能目录，之后才建的目录要 /reload-skills 才生效。

`cs/`（CodeStable-Lite）不在仓里：上游没有许可证，由 SessionStart hook `.githooks/ensure-cs.mjs` 在云端会话开始时按固定提交取到这里，`.gitignore` 忽略它。
