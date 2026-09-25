# 置信度

> TypeSafe 如何报告确定性、它与概率有何不同，以及如何用它控制系统行为。

export function ConfidenceExplorer() {
  const [probabilities, setProbabilities] = useState([90, 6, 4]);
  const options = ["A", "B", "C"];
  function changeProbability(index, value) {
    setProbabilities(current => {
      const others = [0, 1, 2].filter(i => i !== index);
      const remaining = 100 - value;
      const previousRemaining = current[others[0]] + current[others[1]];
      const next = [...current];
      next[index] = value;
      next[others[0]] = previousRemaining > 0 ? remaining * current[others[0]] / previousRemaining : remaining / 2;
      next[others[1]] = remaining - next[others[0]];
      return next;
    });
  }
  function formatProbability(value) {
    if (Math.abs(value - 100 / 3) < 0.000001) return "33⅓%";
    return `${Number(value.toFixed(1))}%`;
  }
  function choiceConfidence(values) {
    const count = values.length;
    const peak = Math.max(...values) / 100;
    return Math.max(0, Math.min(1, (count * peak - 1) / (count - 1)));
  }
  const confidence = choiceConfidence(probabilities);
  const maximum = Math.max(...probabilities);
  const winners = options.filter((option, i) => Math.abs(probabilities[i] - maximum) < 0.000001);
  const selected = winners.length === 1 ? `Option ${winners[0]}` : `Tie: ${winners.join(", ")}`;
  const buttonClass = "border px-3 py-2 text-sm hover:bg-zinc-100 dark:hover:bg-zinc-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-pink-500";
  const buttonStyle = {
    borderColor: "#71717a"
  };
  const eyebrow = {
    fontSize: "0.6875rem",
    fontWeight: 700,
    letterSpacing: "0.08em",
    textTransform: "uppercase"
  };
  return <section aria-label="Explore probabilities and confidence" className="not-prose my-6 border border-zinc-300 dark:border-zinc-700 p-5 sm:p-6 text-zinc-800 dark:text-zinc-200">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="text-zinc-600 dark:text-zinc-400" style={eyebrow}>Choice question with three options</div>
          <div className="mt-2 text-base font-semibold">See how probability distribution changes confidence</div>
        </div>
        <div className="text-right" role="status" aria-live="polite" aria-atomic="true">
          <div className="text-sm text-zinc-600 dark:text-zinc-400">Confidence</div>
          <output className="block text-3xl font-semibold tabular-nums" style={{
    color: "#E551BA"
  }}>
            {confidence.toFixed(2)}
          </output>
        </div>
      </div>

      <div role="img" aria-label={`Probability distribution: ${options.map((option, i) => `${option} ${formatProbability(probabilities[i])}`).join(", ")}. ${selected}.`} className="my-6">
        <div className="text-xs text-zinc-600 dark:text-zinc-400">Probability</div>
        <div aria-hidden="true" style={{
    position: "relative",
    height: "180px",
    margin: "34px 0 36px 44px"
  }}>
          {[0, 50, 100].map(tick => <div key={tick} style={{
    position: "absolute",
    bottom: `${tick}%`,
    width: "100%",
    borderBottom: "1px solid",
    borderColor: "color-mix(in srgb, currentColor 18%, transparent)"
  }}>
              <span className="text-xs" style={{
    position: "absolute",
    right: "calc(100% + 8px)",
    transform: "translateY(-50%)"
  }}>{tick}%</span>
            </div>)}
          <div style={{
    position: "absolute",
    inset: 0,
    display: "flex",
    justifyContent: "space-around",
    alignItems: "flex-end"
  }}>
            {options.map((option, index) => <div key={option} style={{
    position: "relative",
    width: "21%",
    height: `${probabilities[index]}%`
  }}>
                <span className="text-sm font-semibold tabular-nums" style={{
    position: "absolute",
    bottom: "calc(100% + 6px)",
    left: "50%",
    transform: "translateX(-50%)",
    whiteSpace: "nowrap"
  }}>{formatProbability(probabilities[index])}</span>
                <div style={{
    height: "100%",
    background: winners.length === 1 && winners[0] === option ? "#E551BA" : "currentColor",
    opacity: winners.length === 1 && winners[0] === option ? 1 : 0.45
  }} />
                <span className="text-sm" style={{
    position: "absolute",
    top: "calc(100% + 8px)",
    left: "50%",
    transform: "translateX(-50%)"
  }}>{option}</span>
              </div>)}
          </div>
        </div>
      </div>

      <div className="space-y-3">
        {options.map((option, index) => <label key={option} className="flex items-center gap-3 text-sm">
            <span className="w-5 font-semibold">{option}</span>
            <input type="range" min="0" max="100" step="1" value={probabilities[index]} onChange={event => changeProbability(index, Number(event.target.value))} aria-label={`Probability of ${option}`} aria-valuetext={formatProbability(probabilities[index])} className="min-w-0 flex-1 cursor-pointer" style={{
    accentColor: "#E551BA",
    minHeight: "44px"
  }} />
            <output className="w-16 text-right tabular-nums">{formatProbability(probabilities[index])}</output>
          </label>)}
      </div>
      <p className="mt-3 text-sm text-zinc-600 dark:text-zinc-400">Move a slider to change an option's probability. The other probabilities adjust to keep the total at 100%.</p>

      <div className="mt-4 flex flex-wrap gap-2" aria-label="Example distributions">
        <button type="button" className={buttonClass} style={buttonStyle} onClick={() => setProbabilities([90, 6, 4])}>Clear winner</button>
        <button type="button" className={buttonClass} style={buttonStyle} onClick={() => setProbabilities([40, 33, 27])}>Spread out</button>
        <button type="button" className={buttonClass} style={buttonStyle} onClick={() => setProbabilities([100 / 3, 100 / 3, 100 / 3])}>Even split</button>
      </div>
      <div className="mt-4 text-sm" aria-live="polite">{winners.length === 1 ? `Selected: ${selected}` : selected}</div>
      <details className="mt-4 text-sm text-zinc-600 dark:text-zinc-400">
        <summary className="cursor-pointer">How this demo calculates Confidence</summary>
        <p className="mt-3">TypeSafe computes confidence from how the probability is spread across the options. All of it on one option gives 1.0; the more evenly it spreads, the lower the confidence. This demo uses <code>(3 × largest probability − 1) / 2</code> to approximate confidence for three options.</p>
      </details>
    </section>;
}

TypeSafe 返回的所有 Score 和 Choice 答案都包含一个 `probabilities` 属性，表示在各个选项（Choice）或等级（Score）上的概率分布。正是这个分布的*形状*告诉你模型有多确定：集中于某个结果意味着答案很确定，分散则意味着不确定。

答案的 `confidence` 属性将这个形状压缩成一个 0 到 1 之间的单一数字，你可以直接基于它设置阈值，而无需自己计算。（Noul 答案不带这个属性。）

## 置信度由概率推导而来

`confidence` 是根据答案已经给出的概率分布计算出的统计量。TypeSafe 会替你完成计算，并在每个 Choice 和 Score 答案中返回它，因此常见场景无需你在本地做任何额外工作。

<ConfidenceExplorer />

<Note>
  **一个可靠的默认值：** 我们提供 `confidence` 作为适用于大多数用例的便捷度量，但你绝不会被困在我们的定义里。取决于你在评估什么，另一种度量可能更适合你——这正是我们在响应中给出完整 `probabilities` 的原因。不同计算方式的利弊是一个专门话题，我们会把它放到另一份实战指南中而非本页，届时会在这里补充链接！
</Note>

对于 [Choice](/primitives/choice)，分布是跨各个选项的 `probabilities`；对于 [Score](/primitives/score)，它是跨各个等级的分布。两种情况下，越平坦的分布意味着越低的置信度：Choice 的低置信度通常意味着没有任何一个选项明显胜过其他选项，而 Score 的低置信度通常意味着等级含糊、多维，或者状态中包含的信息不足以做出判断。

## “我不知道”是一个有用的信号

一个智能系统，无论是人还是机器，如果无法表达真实的不确定性，就无法被信任。

置信度为你提供了一种内置机制，让模型能够说“这个我不太确定”。这使你的代码可以针对不同的确定程度实现不同的行为，而这正是构建真正可依赖的系统的基础。

## 在代码中使用置信度的三条路径

一个实用的入门模式是将置信度划分为三个区间，每个区间对应不同的系统行为：

**高置信度：** 自动执行。模型的判断清晰明确，你可以在无需人工参与的情况下继续。

**中等置信度：** 谨慎推进。模型给出了合理的答案但并不确定。根据上下文，你可以请用户确认、标记以供审核，或在行动前收集更多信息。

**低置信度：** 不要行动。转给人工、请求澄清，或回退到另一个系统。模型在告诉你：它没有足够的信息，或者这个问题并不适合它。

这些边界画在哪里取决于风险高低。

## 阈值随风险调整

置信度阈值不是一个数字。同一系统中的不同操作，应根据出错的后果在不同的水平上设置门槛。

```python theme={null}
response = client.system_one(
    state=user_message,
    questions={
        "action": Choice(
            instructions="What is the user trying to do?",
            criteria={
                "check_balance": "View account balance",
                "approve_transfer": "Approve the pending withdrawal request",
                "support": "Get help with an issue",
            },
        ),
    },
)

action = response.answers["action"]
confidence = action.confidence

if confidence < 0.5:
    # Model is genuinely unsure. Don't guess.
    route_to_human(user_message)

elif action.choice == "check_balance":
    # Low stakes. Showing the wrong screen is recoverable.
    show_balance(account_id)

elif action.choice == "approve_transfer":
    if confidence > 0.9:
        # High stakes, high confidence. Proceed with confirmation.
        confirm_then_execute(account_id)
    else:
        # High stakes, moderate confidence. Verify first.
        ask_user_to_confirm(account_id)
```

0.5 的置信度下限会拦下所有模型报告为真正不确定的情况。在此基础上，未经确认就执行操作的阈值，对破坏性操作要高于只读操作。你的代码负责编码风险容忍度。

<Note>
  正确的阈值取决于你的领域以及模型在你的用例上的表现。从保守的阈值开始，用你自己的数据测试，并根据观察到的结果进行调整。
</Note>
