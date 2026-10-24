# NIGHTSHIFT · 夜班

**让你的 Agent 通宵干活，早上给你一份能审的飞行报告，而不是一段自我感觉良好的总结。**

一个 skill + 一个零依赖 CLI：把"跑了一整晚的 Agent"变成人五分钟内能审完的东西。

```
$ nsh brief
GOAL      ship the CSV-to-PDF report generator as a CLI: parser, templates, tests, docs, CI
WINDOW    7h32m used · 27m left
ACTIVITY  33 steps · 5 checks · 7 checkpoints · 33 pieces of evidence
EVIDENCE  85% of steps carry proof (28/33)
GATE      GREEN · 5/5 criteria proven
RISK      medium: 5 steps in a row with no evidence | medium: src/render.rs touched 4x with no check
TREND     improving - still climbing: +68 points over 5.7h
```

---

## 问题：最难的一个词是"完成"

你睡了。Agent 在干活。你醒来看到：

> "搞定了！我重构了解析器、补了测试、更新了文档。注意：测试可能需要小调整，CI 配置我没法验证。"

这句话里藏了三件事：

1. **"完成"从来没被定义过**，所以它不可能错。
2. **"补了测试"没有收据**——没有命令、没有退出码、没有输出。
3. **它早就漂了**：凌晨三点它花了 90 分钟做一个你根本没要的落地页。

Agent 框架解决编排，评测平台解决离线打分。**没有人解决你早上七点真正需要的东西：
一份关于你没能亲眼看着的那一夜的、诚实的总结。**

## 它做什么

| 机制 | 杀死什么 |
| --- | --- |
| **飞行计划**：目标 + 3~6 条**可命令校验**的完成标准 + 非目标 + 截止时间 | 把"完成"当成一种感觉 |
| **黑匣子**：只追加的 `events.jsonl`，证据在动作发生的那一刻就落盘 | 没有收据的断言 |
| **检查点**：每约 45 分钟一次诚实进度 + 漂移检测 | 无声漂移、无限打磨 |
| **收敛检测**：连续三次检查点没进展 = 该停 | 第七个小时的边际收益为负 |
| **证据门**：`nsh gate` 只有在每条标准都**带证据**通过时才返回 0 | 靠气氛变绿 |
| **飞行报告**：单文件 HTML，强制包含 **"未证明"** 一栏 | 早上的惊吓 |

## 60 秒上手（不用 API key，不用起服务）

```bash
git clone https://github.com/<you>/nightshift && cd nightshift
python -m nightshift demo --open
```

它会现场造一次 7.5 小时的脚本化运行（真的黑匣子、真的证据文件、真的 sha256），
然后打开飞行报告。**先读"未证明"那一栏**，那是重点。

然后驱动你自己的夜班：

```bash
nsh init --goal "把报表生成器做成 CLI，v0.1" --deadline "06:40"
nsh done add "测试全绿"     -- python -m pytest -q
nsh done add "能构建"       -- npm run build
nsh done add "有快速上手"   -- python scripts/check_readme.py

nsh run  -- python -m pytest -q        # 跑命令，顺手把 stdout + 退出码变成证据
nsh step "手写了开头那段" -e README.md
nsh tick --progress 40 --note "解析器好了，下一步模板"

nsh gate     # 只有每条标准都带证据通过才返回 0
nsh report   # .nightshift/reports/flight-report.html
nsh brief    # 上面那十行
```

## 装成 skill（让 Agent 自己这么干）

```bash
# Claude Code / Claude Agent SDK
cp -r . ~/.claude/skills/nightshift

# DeepSeek Harness
cp -r . ~/.dsh/skills/nightshift

# Codex / Cursor / 任何读 AGENTS.md 的
cat SKILL.md >> AGENTS.md
```

然后你只需要说：

> *"干到完成，我去睡了，六点半截止。"*

Agent 自己写飞行计划、记收据、打检查点、留报告。

## 七条铁律

1. 计划先于工作。
2. 每个断言都留收据，且在动作发生时留下。
3. 检查点很便宜，漂移很贵。
4. 红门不是这一夜的失败，红门是这一夜的产物。
5. 仪表说停就停。
6. 永不改写日志。
7. 简报写给陌生人看。

全文见 [`SKILL.md`](SKILL.md)；协议规范见 [`docs/PROTOCOL.md`](docs/PROTOCOL.md)。

## 这个仓库就是它自己跑出来的

`nightshift/.nightshift/` 里是构建 v0.1 这一夜的真实日志，只追加、没改过。
所有数字直接从日志里读。

## 基准测试，诚实版

```
drift detector   precision 1.00   recall 0.86   f1 0.92
gate             accuracy 1.00
confusion        tp=6 fp=0 tn=8 fn=1
```

两个必须说清的前提：

- **语料是合成的，标签是构造出来的。** 这些数字是启发式规则的回归测试，
  不是对真实 Agent 行为的科学基准。
- **有一个已知漏检**：没传 `--target` 的反复改同一文件，检测器看不见。

详见 [`docs/BENCHMARKS.md`](docs/BENCHMARKS.md)。

## 它不是什么

- **不是 Agent 框架**：它不跑你的 Agent，它盯着它。
- **不是评测平台**：它不打分模型，它给一次夜班打分。
- **不是沙箱**：它记录发生过什么，它不拦你。
- **不是魔法**：漂移检测就是五条启发式 + 一个分词器，它会错，而且它自己在报告里说。

## 常见问题

**要 API key 吗？** 不要。整个工具不调用任何模型。
**支持 Codex / Cursor / Claude Code / DSH 吗？** 支持，它就是一个 `SKILL.md` 加一个 CLI。
**Agent 真的会照做吗？** 这就是门存在的原因。skill 是请求，退出码是事实。
**非编程任务能用吗？** 能，只要"完成"能被一条命令校验：文档要存在且能解析、
数据要通过校验、构建要成功。
**Windows 行吗？** 行，CI 跑 Windows / macOS / Linux。

## License

MIT。去搞点凌晨两点该搞的东西。
