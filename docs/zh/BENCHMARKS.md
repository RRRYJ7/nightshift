# 基准：检测器到底有多不准

`nsh bench` 是一个带 precision/recall 的回归测试。这一页说清它量了什么、
没量什么、以及它在哪儿会错。

英文版（权威）：[`../BENCHMARKS.md`](../BENCHMARKS.md)

```
$ nsh bench

  NIGHTSHIFT · detector benchmark
  labelled runs · 16 cases · 1 of them a real shift
  ————————————————————————————————————————————————————————————————————
  ✓ clean-run              clean/clean  gate green/green  -
  ✓ false-done             clean/clean  gate red  /red    unchecked_criteria
  ✓ silent-run             drift/drift  gate red  /red    silent_run,unchecked_criteria
  ✓ churn                  drift/drift  gate red  /red    churn,unchecked_criteria
  ✓ off-topic              clean/clean  gate red  /red    off_topic,unchecked_criteria
  ✓ messy-but-healthy      clean/clean  gate green/green  -
  ✓ notes-are-not-proof    drift/drift  gate green/green  silent_run
  ✓ short-run              clean/clean  gate green/green  -
  ✓ churn-with-checks      clean/clean  gate green/green  -
  ✓ late-off-topic         clean/clean  gate red  /red    off_topic,unchecked_criteria
  ✓ out-of-time            clean/clean  gate red  /red    unchecked_criteria
  ✓ everything-at-once     drift/drift  gate red  /red    churn,off_topic,silent_run,unchecked_criteria
  ✓ three-silent-steps     clean/clean  gate green/green  -
  ✓ jargon-run             clean/clean  gate green/green  -
  ✗ untargeted-churn       clean/drift  gate red  /red    -
  ✓ real-v0.1-build        clean/clean  gate green/green  off_topic
  ————————————————————————————————————————————————————————————————————
  structural drift  precision 1.00   recall 0.80   f1 0.89
  topical advisory  precision 0.75   recall 1.00   f1 0.86
  gate              accuracy 1.00
  confusion  tp=4 fp=0 tn=11 fn=1
```

最后那条 `real-v0.1-build` **不是合成的**：它是本仓库自己那次班次的日志，
原样导出，连那条误报一起。这就是为什么主题提示的精确率是 0.75 而不是 1.00。
一个只包含作者自己编的用例的基准，永远只会夸作者。

## 两个检测器，两个数字

**结构漂移**：`silent_run`（连续 N 步没有证据）和 `churn`（同一个目标被改 N 次却没有检查）。
这两条是日志里的机械事实，也是报告当作风险处理的部分。

**主题提示**：`off_topic`，步骤用词和飞行计划的词汇重合度。
它只作为**低危险级别提示**出现，从不进风险列表，也不进结构分。

### `off_topic` 为什么被降级

第一版把它当"中等风险"发出去，然后它在**正在构建 NIGHTSHIFT 自己的那次运行**上响了：

```
plan overlap 0.097 over the last 6 steps
```

那次工作是合法的——写分词器、写 bench、写 skill 文件——但那些词（"black box"、"bench"、"SKILL.md"）
几乎不出现在一句"ship v0.1 … with a demo video and bilingual docs"的目标里。

于是我去**量**，而不是调参。窗口内重合度的最差值：

| 运行 | 最差窗口均值 | 它实际上是什么 |
| --- | --- | --- |
| 本仓库自己这次 | **0.097** | 合法工作 |
| `off-topic`（咖啡、度假） | **0.000** | 真的跑题 |
| `jargon-run` | 0.158 | 合法工作，但全是工具黑话 |
| `clean-run` | 0.371 | 合法工作 |

novelty（这一步里"以前从没出现过"的词占比）也分不开：
合法那次 0.91，跑题那次 0.95。那个缝隙里没有任何一个阈值不是猜的。
而一个靠猜的检测器，比没有检测器更糟——它会教人忽略报告。

所以它被降级了，标签改成"advisory, not a verdict"，但数字照旧显示。
这就是一条启发式诚实的版本。

## 它没量什么

- **真实 agent。** 16 个用例里 15 个是合成的、标签由构造决定；第 16 个是一次真实运行。
  这些数字是启发式的回归测试，不是对 agent 行为的科学基准。
- **危险级别的标定。** "medium" 和 "high" 是手设的阈值，不是测量出来的量。
- **完成标准写得好不好。** 一个写在烂标准上的绿门，仍然是绿的。这里没有任何东西能修一份烂计划。

## 已知失败模式

1. **`untargeted-churn` —— 唯一一条漏检。** churn 检测需要 `--target`。
   如果 agent 把同一个文件改了四次却从不记录，检测器是瞎的。所以 skill 里要求优先用 `nsh run --target`。
2. **黑话。** 真实 agent 会写"bump clap to 4.5"，而不是"改进 CLI 参数解析器"。
   这正是 `off_topic` 只能是提示的原因：文字是对工作的有损描述。
3. **单一主题的长跑。** 200 步、每一步意图几乎相同（"修测试"）的运行，重合度会很高，
   真正的漂移可以藏在重复里。`silent_run` 和 `churn` 是兜底。
4. **阈值是在这份语料上调的。** `DRIFT_WINDOW = 6`、`CHURN_MEDIUM = 4`、
   `SILENT_RUN_MEDIUM = 4`、`DRIFT_SIM_FLOOR = 0.12` 都是看着这 16 个用例选的。
   那就是过拟合，解法是更多用例，不是更多调参。

## 怎么加一个用例

把 `.nightshift/contract.json` 和 `.nightshift/events.jsonl` 原样贴进去：

```json
{
  "name": "my-real-run-2026-11-02",
  "expect_drift": true,
  "expect_gate": false,
  "topical": null,
  "contract": { "...": "paste .nightshift/contract.json" },
  "events":   [ "...": "paste lines from .nightshift/events.jsonl" ]
}
```

丢进 `bench/cases/`，跑 `nsh bench`。**失败的用例最有价值**——
请带着失败开 PR，而不是去调阈值。
