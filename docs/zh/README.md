# 中文文档 / Chinese docs

> English readers: the authoritative docs are [`README.md`](../../README.md),
> [`docs/PROTOCOL.md`](../PROTOCOL.md) and [`SKILL.md`](../../SKILL.md). This
> folder is a Chinese reading path, not a fork of the spec.

NIGHTSHIFT 的文档以**英文为准**（因为协议要和不同语言的实现对齐），
但下面这些是中文写成的，读完基本不用再翻英文。

| 文档 | 内容 |
| --- | --- |
| [WHY.md](WHY.md) | 为什么"完成"是 agent 工程里最难的词（设计论证） |
| [WALKTHROUGH.md](WALKTHROUGH.md) | 一次完整班次的逐分钟走查，带真实命令输出 |
| [BENCHMARKS.md](BENCHMARKS.md) | 基准数字、已知失败模式、以及一次"把检测器降级"的全过程 |
| [PROTOCOL.md](PROTOCOL.md) | 协议摘要（事件的权威定义在英文版） |

另外：

- [README.zh-CN.md](../../README.zh-CN.md) —— 中文首页
- [`examples/sample-shift/`](../../examples/sample-shift/) —— 一次真实的、非脚本化的班次，
  日志里能翻到"第一次跑测试 exit 1、修完 exit 0"

## 三句话说完

1. **先定"完成"**：3~6 条能被命令判真假的完成标准，写不出命令的叫愿望。
2. **证据在动作发生时落盘**：stdout + 退出码 + sha256，只追加；没有"事后补证据"这个命令。
3. **说完成之前过门**：`nsh gate` 全绿才叫完成，红了就写红——报告里那一栏叫"未证明"。

## 为什么它是 DSH 的 skill

它由 `SKILL.md` + 一个零依赖 CLI 组成，装到 `~/.dsh/skills/nightshift` 之后，
DeepSeek Harness 里的 Agent 会在"用户要它跑很久"的场景下自动按这套协议工作：
写飞行计划 → 记收据 → 打检查点 → 过门 → 出报告。

同样的 `SKILL.md` 也能放进 Claude Code（`~/.claude/skills/`）、
或直接追加到 `AGENTS.md`（Codex / Cursor）。CLI 不依赖任何 harness。
