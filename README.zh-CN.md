# NIGHTSHIFT · 夜班

[English](README.md) · **中文** · [中文文档导读](docs/zh/README.md)

**让你的 Agent 通宵干活，早上给你一份能审的飞行报告，而不是一段自我感觉良好的总结。**

它是给 **DeepSeek Harness（DSH）** 写的 skill（`SKILL.md` + `nsh`），
也能用在任何"能跑一条 shell 命令"的 harness 上：Claude Code、Codex、Cursor、OpenCode，或者一个 cron。

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
| **证据校验**：`nsh verify` 重算每个摘要，篡改过的收据直接失败 | 从来没人核对过的"证据" |
| **改动报告**：`nsh diff` 列出计划之后改了什么、改完有没有人查 | "它说它改了 12 个文件" |
| **飞行报告**：单文件 HTML，强制包含 **"未证明"** 一栏 | 早上的惊吓 |

## 60 秒上手（不用 API key，不用起服务）

```bash
git clone https://github.com/RRRYJ7/nightshift && cd nightshift
python -m nightshift demo --open
```

它会现场造一次 7.5 小时的脚本化运行（真的黑匣子、真的证据文件、真的 sha256），
然后打开飞行报告。**先读"未证明"那一栏**，那是重点。

再看一眼失败长什么样——这条比上一条更能说明问题：

```bash
python -m nightshift demo --red --open    # 2 条没证明，门是红的
```

然后驱动你自己的夜班（下面的 `nsh` 是安装后的入口；没装就等于 `python -m nightshift`）：

```bash
pipx install .                           # 可选，给你一个 nsh
nsh init --goal "把报表生成器做成 CLI，v0.1" --deadline "06:40"
nsh done add "测试全绿"     -- python -m pytest -q
nsh done add "能构建"       -- npm run build
nsh done add "有快速上手"   -- python scripts/check_readme.py

nsh run  -- python -m pytest -q        # 跑命令，顺手把 stdout + 退出码变成证据
nsh step "手写了开头那段" -e README.md
nsh tick --progress 40 --note "解析器好了，下一步模板"

nsh gate     # 只有每条标准都带证据通过才返回 0
nsh verify   # 重算每个证据摘要，和磁盘上的字节比
nsh diff     # 计划之后改了什么，以及有没有被检查过
nsh report   # .nightshift/reports/flight-report.html
nsh brief    # 上面那十行
```

## 装成 skill（让 Agent 自己这么干）

```bash
# DeepSeek Harness（这个 skill 就是为它写的）
cp -r . ~/.dsh/skills/nightshift

# Claude Code / Claude Agent SDK
cp -r . ~/.claude/skills/nightshift

# Codex / Cursor / 任何读 AGENTS.md 的
cat SKILL.md >> AGENTS.md
```

然后你只需要说：

> *"干到完成，我去睡了，六点半截止。"*

Agent 自己写飞行计划、记收据、打检查点、留报告。

## 它适合谁

**任何"让 Agent 干活，然后必须信它的结果"的人**，不只程序员：

- **开发者**：通宵推一个功能。早上报告告诉你哪几条测试没跑过、哪个文件改了四次都没验证。
- **科研人员**：跑长任务。以前"流程跑完了"是一句话，现在是一行退出码加一个哈希；
  仿真写出结果文件，那个文件就是证据。（这也是这个工具最初被写出来的场景：
  一个人要在早上七点，验收一台跑了一夜的机器。）
- **数据分析**：重建数据集。行数、重复 id、时间范围、schema 校验都能变成完成标准，
  报告会告诉你哪一条在凌晨四点十分跑过、打印了什么。
- **写作者 / 设计 / 运营**：产出必须"能被解析"的交付物——PDF 要能渲染、
  方案要有全部九节、配置要能通过校验、PPT 要能打开。
- **学生和爱好者**：想知道 Agent 凌晨三点到底干了什么，而不是它说自己干了什么。

唯一的要求：**"完成"能被写成一条命令**。如果它只能是一种感觉，
那没有工具能帮你——包括这个。

## 七条铁律

1. 计划先于工作。
2. 每个断言都留收据，且在动作发生时留下。
3. 检查点很便宜，漂移很贵。
4. 红门不是这一夜的失败，红门是这一夜的产物。
5. 仪表说停就停。
6. 永不改写日志。
7. 简报写给陌生人看。

报告里除了"已证明 / 未证明"，还有两栏是评审最常问的：**时间花在哪**（每个 `--target` 被改了几次、之后有没有验证）和 **改了什么、谁看的**（对计划开跑时的快照做真实 diff，行数来自 git，并逐文件标注改完有没有被检查过）。

全文见 [`SKILL.md`](SKILL.md)；协议规范见 [`docs/PROTOCOL.md`](docs/PROTOCOL.md)。

## 这个仓库就是它自己跑出来的

`.nightshift/` 里是构建 v0.1 这一夜的真实日志，只追加、没改过：
11 步、15 次检查、3 个检查点、31 条证据，5/5 条标准带证据通过。
所有数字直接从日志里读，`python -m nightshift brief` 就是它们的出口。

`examples/sample-shift/` 里还有一次**非脚本化**的真实班次：一个 20 行模块的
unicode bug，日志里能翻到"第一次跑测试 exit 1、修完 exit 0"。

想完整看一遍用起来是什么感觉：**[`docs/WALKTHROUGH.md`](docs/WALKTHROUGH.md)**。

## 基准测试，诚实版

```
structural drift  precision 1.00   recall 0.80   f1 0.89   (silent_run + churn)
topical advisory  precision 0.75   recall 1.00   f1 0.86   (off_topic，低置信度)
gate              accuracy 1.00
confusion         tp=4 fp=0 tn=11 fn=1
```

语料是 15 个合成样本 + **1 个真实样本**（就是本仓库这一夜，含那条误报）。

三个必须说清的前提：

- **合成语料、构造标签。** 这些数字是启发式规则的回归测试，不是对真实 Agent 行为的科学基准。
- **有一个已知漏检**：没传 `--target` 的反复改同一文件，检测器看不见。
- **主题漂移检测被降级过，不是调参调好的。** 它在本仓库这一夜上误报了（0.097），
  我量完之后发现分不开"合法新词汇"和"真的跑题"，于是把它降成提示而不是猜一个阈值。
  过程在 [`docs/BENCHMARKS.md`](docs/BENCHMARKS.md)。

详见 [`docs/BENCHMARKS.md`](docs/BENCHMARKS.md)。

## 它不是什么

- **不是 Agent 框架**：它不跑你的 Agent，它盯着它。
- **不是评测平台**：它不打分模型，它给一次夜班打分。
- **不是沙箱**：它记录发生过什么，它不拦你。
- **不是魔法**：漂移检测就是四条启发式 + 一个分词器，它会错，而且它自己在报告里说。

## 常见问题

**要 API key 吗？** 不要。整个工具不调用任何模型。
**支持 Codex / Cursor / Claude Code / DSH 吗？** 支持，它就是一个 `SKILL.md` 加一个 CLI。
**Agent 真的会照做吗？** 这就是门存在的原因。skill 是请求，退出码是事实。
**非编程任务能用吗？** 能，只要"完成"能被一条命令校验：文档要存在且能解析、
数据要通过校验、构建要成功。
**Windows 行吗？** 行，CI 跑 Windows / macOS / Linux。

## License

MIT。去搞点凌晨两点该搞的东西。
