# Agent Instructions

Read this entire file before starting any task.

## Self-Correcting Rules Engine

This file contains a growing ruleset that improves over time. **At session start, read the entire "Learned Rules" section before doing anything.**

### How it works

1. When the user corrects you or you make a mistake, **immediately append a new rule** to the "Learned Rules" section at the bottom of this file.
2. Rules are numbered sequentially and written as clear, imperative instructions.
3. Format: `N. [CATEGORY] Never/Always do X — because Y.`
4. Categories: `[STYLE]`, `[CODE]`, `[ARCH]`, `[TOOL]`, `[PROCESS]`, `[DATA]`, `[UX]`, `[OTHER]`
5. Before starting any task, scan all rules below for relevant constraints.
6. If two rules conflict, the higher-numbered (newer) rule wins.
7. Never delete rules. If a rule becomes obsolete, append a new rule that supersedes it.

### When to add a rule

- User explicitly corrects your output ("no, do it this way")
- User rejects a file, approach, or pattern
- You hit a bug caused by a wrong assumption about this codebase
- User states a preference ("always use X", "never do Y")

### Rule format example

```
14. [CODE] Always use `bun` instead of `npm` — user preference, bun is installed globally.
15. [STYLE] Never add emojis to commit messages — project convention.
16. [ARCH] API routes live in `src/server/routes/`, not `src/api/` — existing codebase pattern.
```

---

## Learned Rules

<!-- New rules are appended below this line. Do not edit above this section. -->
1. [UX] Always generate price-only spin-off charts without volume panels and label the companies as `Child Company` and `Mother Company` in the final image because the user wants cleaner visual review and explicit relationship labels.
2. [UX] Always lay out combined images with `Child Company` on the left, `Mother Company` on the right, and stack timeframes from top to bottom as `1wk`, `1d`, `4h`, `1h`; when a timeframe has too few bars to read cleanly, render a placeholder instead of a distorted chart.
3. [PROCESS] Always inspect the generated local image directly before claiming a chart layout or rendering issue is fixed because log output and code changes are not enough to verify visual correctness.
4. [PROCESS] Always iterate on chart rendering until the generated JPG looks acceptable by direct inspection, and do not treat the task as visually complete without that image check.
5. [ARCH] Always send Telegram results graph by graph and delete old chart outputs before each new daily run because the user does not want historical chart storage or grouped Telegram delivery.
6. [ARCH] Always expose an explicit one-shot send script and prefer GitHub Actions for the automated 9:00 run when the user asks for script-based automation.
7. [CODE] Always make script entrypoints runnable both as `python -m src...` and as direct `python src/...py` commands because the user runs the files directly from the workspace.
8. [ARCH] Always use an 18-month spin-off universe, generate only daily and weekly charts, create one image per company, and send the two company images together as a pair because the user no longer wants 1h/4h charts or a single 8-panel image.
