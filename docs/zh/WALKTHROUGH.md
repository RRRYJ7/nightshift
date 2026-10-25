# 一次完整的班次：从 22:49 到早上七点

这是用 NIGHTSHIFT 真实跑一夜的样子，命令输出来自本仓库自己的那次班次。
读完大约五分钟，也是判断"这工具适不适合我"最快的办法。

---

## 22:49 —— 先定计划

```console
$ nsh init --goal "把报表生成器做成 CLI，v0.1" --deadline 06:30 \
           --non-goal "不做 Web UI" --risk "测试数据依赖 locale"

✈ NIGHTSHIFT · flight plan created  .nightshift
────────────────────────────────────────────────────────────────
  goal        ship v0.1 of the report CLI
  deadline    2026-10-25T06:30:00+08:00
```

然后是最关键的一步：

```console
$ nsh done add "测试全绿"   -- python -m pytest -q
  + d1 测试全绿  $ python -m pytest -q
$ nsh done add "有快速上手" -- python scripts/check_readme.py
  + d2 有快速上手  $ python scripts/check_readme.py
```

**写不出命令的完成标准，叫愿望。** `nsh done add "代码干净"`（不带命令）也允许，
但检查的时候你得自己补命令——那是个更差的位置。

---

## 23:10 —— 干活，顺手留收据

和普通 agent 跑的区别只有一个词：用 `run`，而不是"顺手做了"。

```console
$ nsh run --target src/parser.py -- python -m pytest tests/test_parser.py -q
  ● 23:14:02 e000003 python -m pytest tests/test_parser.py -q  ok (2.4s)
      │ 12 passed in 2.41s

$ nsh step "手写重写了开头那段" -e README.md
  ● 23:15:38 e000004 手写重写了开头那段  1 evidence
```

`nsh run` 把 stdout、退出码、耗时、以及内容的 sha256 一起存了下来；
`nsh step` 存了文件哈希。两者都在**动作发生的那一刻**进了只追加的日志——
那是收据唯一有意义的时刻。

---

## 00:20 —— 第一个检查点

```console
$ nsh tick --progress 40 --note "解析器好了，下一步模板"

✈ NIGHTSHIFT · checkpoint  #1
────────────────────────────────────────────────────────────────
  progress    40%
  elapsed     1h31m  · 5h09m left
  gate        RED  1/2 criteria
  coverage    100%
  drift       clean
  advisory    1 low-confidence: plan overlap 0.10 over the last 6 steps
```

两点值得注意：

- **`gate RED 1/2`** 在 00:20 是正常的。它不是失败，它是此刻的真相，而且你不用打开任何东西就能看到。
- **`advisory`** 和 `drift` 是故意分开的。它在这里响了——就在本仓库那次班次上——而且它是**错的**。
  所以它是低危险级别，所以基准里单独给它记分。测量过程见 [BENCHMARKS.md](BENCHMARKS.md)。

---

## 03:40 —— 出问题的那一刻

大约第五个小时，agent 把 `src/render.rs` 改了四次，什么都没跑。下一个检查点直接说了：

```console
$ nsh tick --progress 61

✈ NIGHTSHIFT · checkpoint  #3
────────────────────────────────────────────────────────────────
  drift       1 flag(s)
      ▸ `src/render.rs` touched 4x with no check in between
```

`churn` 是这个盒子里最便宜有用的检测器：不需要模型、不需要判断、不需要上下文，
只需要在改文件的步骤上带 `--target`。它也是唯一一个**你忘了 `--target` 就会瞎**的检测器——
那是基准里唯一一条漏检。

这时候 agent 该做的不是自责，是去跑检查：

```console
$ nsh check d3
  PASS d3 three templates render without warnings  exit 0
```

---

## 06:12 —— 过门

写报告之前，把所有检查重跑一遍。检查会过期。

```console
$ nsh check --all
  PASS d1 测试全绿          exit 0
  PASS d2 有快速上手        exit 0

$ nsh gate
✈ NIGHTSHIFT · completion gate  DONE & PROVEN
────────────────────────────────────────────────────────────────
  ✓ d1  测试全绿                                                 proven
  ✓ d2  有快速上手                                               proven

  GATE GREEN — every criterion is proven with evidence.
```

这里如果是红的，也是合法结果——报告会写 `PARTIAL · NOT PROVEN` 并列出缺什么。
**一份诚实的红报告比一份假绿报告值钱**，因为让 agent 独自跑一夜的全部意义，就是早上没有惊吓。

---

## 06:15 —— 校验，然后出报告

```console
$ nsh verify
  7 intact · 0 tampered · 14 changed · 0 missing · 0 without a digest
  VERIFY OK — every captured artefact is intact; 14 project file(s) moved on
  since they were snapshotted.
```

`verify` 把两件"只比哈希就分不清"的事分开了：
存进 `.nightshift/evidence/` 的捕获件不许变（变了 = **篡改**，退出 1），
项目文件后来又改了是正常的（记为 **changed**，只提示）。
没有这个区分，每一次跑都过不了自己的校验，然后没人会读那个检查。

```console
$ nsh report
  ✓ wrote .nightshift/reports/flight-report.html  (17240 bytes)

$ nsh brief
GOAL      ship v0.1 of the report CLI
WINDOW    7h26m used · 46m left
ACTIVITY  11 steps · 10 checks · 3 checkpoints · 26 pieces of evidence
EVIDENCE  100% of steps carry proof (11/11)
GATE      GREEN · 5/5 criteria proven
RISK      no structural drift flags
TREND     improving - still climbing: +37 points over 0.2h
```

---

## 06:30 —— 人读什么

打开 `flight-report.html`，按这个顺序读：

1. **判决** —— 一行，和支撑它的那个数字。
2. **未证明** —— 永远先读这一栏，哪怕是空的。如果不空，你刚刚省下四个小时。
3. **漂移与差点翻车** —— 那个反复改同一文件的循环、那段没证据的沉默、那四十分钟花在非目标上。
   这些是教训；一份没有这些的报告是营销。
4. **已证明** —— 每条都带捕获字节的 sha256，你可以自己核对。

然后去倒咖啡。这一夜结束了，而且它没有任何一部分是惊吓。
