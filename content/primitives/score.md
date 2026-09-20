# Score

> Score 是一种 System One 问题类型，用于按照有序的、描述性的级别对内容进行评级。答案包含一个分数、每个级别的概率以及置信度。

export function ScoreExplorer() {
  const examples = [{
    "id": "severity",
    "label": "Bug severity",
    "question": "How severe is the reported issue?",
    "state": "The export button crashes the settings page in Safari. It works in Chrome, but a few of our customers only use Safari.",
    "levels": ["Cosmetic; no impact to functionality", "Broken or degraded feature, but workaround exists", "Blocking issue; no workaround exists"],
    "shortLevels": ["Cosmetic", "Workaround", "Blocking"],
    "answer": {
      "type": "score",
      "score": 1.43,
      "confidence": 0.35,
      "legend": {
        "0": "Cosmetic; no impact to functionality",
        "1": "Broken or degraded feature, but workaround exists",
        "2": "Blocking issue; no workaround exists"
      },
      "probabilities": {
        "0": 0.0,
        "1": 0.57,
        "2": 0.43
      }
    }
  }, {
    "id": "formality",
    "label": "Outfit formality",
    "question": "How formal is this outfit based on the description?",
    "state": "A navy blazer over a plain white T-shirt, dark jeans, and clean leather loafers. No tie.",
    "levels": ["gym clothes", "casual", "business casual", "formal", "black tie"],
    "shortLevels": ["Gym", "Casual", "Business casual", "Formal", "Black tie"],
    "answer": {
      "type": "score",
      "score": 1.86,
      "confidence": 0.89,
      "legend": {
        "0": "gym clothes",
        "1": "casual",
        "2": "business casual",
        "3": "formal",
        "4": "black tie"
      },
      "probabilities": {
        "0": 0.0,
        "1": 0.14,
        "2": 0.86,
        "3": 0.0,
        "4": 0.0
      }
    }
  }, {
    "id": "relevance",
    "label": "Candidate fit",
    "question": "How relevant is this candidate's experience to the job posting?",
    "state": "Job posting: Senior backend engineer building Python APIs and PostgreSQL services. Candidate: Three years building Django REST APIs with PostgreSQL, preceded by two years in frontend JavaScript. Has owned small services but has not led a backend team.",
    "levels": ["completely unrelated", "adjacent field", "some direct experience", "deep, direct experience"],
    "shortLevels": ["Unrelated", "Adjacent", "Some direct", "Deep direct"],
    "answer": {
      "type": "score",
      "score": 2.52,
      "confidence": 0.52,
      "legend": {
        "0": "completely unrelated",
        "1": "adjacent field",
        "2": "some direct experience",
        "3": "deep, direct experience"
      },
      "probabilities": {
        "0": 0.0,
        "1": 0.0,
        "2": 0.48,
        "3": 0.52
      }
    }
  }, {
    "id": "frustration",
    "label": "Customer frustration",
    "question": "How frustrated is the customer?",
    "state": "Export to PDF fails with a spinner that never finishes. Some of our team say CSV export still works for them, others say it fails too. This is the third time I'm writing in and honestly I'm done. Steps: open any report, click Export, choose PDF. Chrome 128 on macOS.",
    "levels": ["Calm, just stating facts", "Frustrated but civil", "Very angry, strong language or threatening to leave"],
    "shortLevels": ["Calm", "Frustrated", "Very angry"],
    "answer": {
      "type": "score",
      "score": 1.26,
      "confidence": 0.61,
      "legend": {
        "0": "Calm, just stating facts",
        "1": "Frustrated but civil",
        "2": "Very angry, strong language or threatening to leave"
      },
      "probabilities": {
        "0": 0.0,
        "1": 0.74,
        "2": 0.26
      }
    }
  }, {
    "id": "detail",
    "label": "Report detail",
    "question": "How much does the report give an engineer to work with?",
    "state": "Export to PDF fails with a spinner that never finishes. Some of our team say CSV export still works for them, others say it fails too. This is the third time I'm writing in and honestly I'm done. Steps: open any report, click Export, choose PDF. Chrome 128 on macOS.",
    "levels": ["No detail; just says something is broken", "Names the feature but no steps or environment", "Steps to reproduce or environment, but not both", "Steps to reproduce and environment"],
    "shortLevels": ["No detail", "Feature only", "Some detail", "Steps + environment"],
    "answer": {
      "type": "score",
      "score": 3.0,
      "confidence": 1.0,
      "legend": {
        "0": "No detail; just says something is broken",
        "1": "Names the feature but no steps or environment",
        "2": "Steps to reproduce or environment, but not both",
        "3": "Steps to reproduce and environment"
      },
      "probabilities": {
        "0": 0.0,
        "1": 0.0,
        "2": 0.0,
        "3": 1.0
      }
    }
  }];
  const [selectedIndex, setSelectedIndex] = useState(0);
  const example = examples[selectedIndex];
  const topLevel = example.levels.length - 1;
  const score = example.answer.score;
  const confidence = example.answer.confidence;
  const probabilities = example.levels.map((_, level) => example.answer.probabilities[String(level)]);
  const percents = probabilities.map(probability => Number((probability * 100).toFixed(2)));
  const accent = "#E551BA";
  const eyebrow = {
    fontSize: "0.6875rem",
    fontWeight: 700,
    letterSpacing: "0.08em",
    textTransform: "uppercase"
  };
  const columnWidth = 56;
  const buttonClass = "border px-3 py-2 text-sm text-left hover:bg-zinc-100 dark:hover:bg-zinc-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-pink-500";
  const unselectedStyle = {
    borderColor: "#71717a"
  };
  const selectedStyle = {
    borderColor: accent,
    boxShadow: `inset 0 0 0 1px ${accent}`,
    background: "color-mix(in srgb, #E551BA 10%, transparent)"
  };
  const endNameClass = "text-xs text-zinc-600 dark:text-zinc-400";
  const midNameClass = "hidden sm:block text-xs text-zinc-600 dark:text-zinc-400";
  function position(value) {
    return `${value / topLevel * 100}%`;
  }
  function tickNameStyle(level) {
    if (level === 0) return {
      left: 0,
      textAlign: "left",
      maxWidth: "calc(50% - 8px)"
    };
    if (level === topLevel) return {
      right: 0,
      textAlign: "right",
      maxWidth: "calc(50% - 8px)"
    };
    return {
      left: position(level),
      transform: "translateX(-50%)",
      textAlign: "center",
      maxWidth: `calc(${100 / topLevel}% - 8px)`
    };
  }
  const chartSummary = example.levels.map((_, level) => `level ${level}, ${example.shortLevels[level]}: ${percents[level]}%`).join("; ");
  return <section aria-label="Explore Score examples" className="not-prose my-6 border border-zinc-300 dark:border-zinc-700 p-5 sm:p-6 text-zinc-800 dark:text-zinc-200">
      <div className="text-zinc-600 dark:text-zinc-400" style={eyebrow}>Example Score question</div>
      <div className="mt-3 flex flex-wrap gap-2" role="group" aria-label="Example questions">
        {examples.map((item, index) => <button key={item.id} type="button" aria-pressed={index === selectedIndex} onClick={() => setSelectedIndex(index)} className={buttonClass} style={index === selectedIndex ? selectedStyle : unselectedStyle}>
            {item.label}
          </button>)}
      </div>

      {}
      <div className="mt-6" style={{
    minHeight: "152px"
  }}>
        <div className="mt-2 text-base font-semibold">{example.question}</div>
        <div role="list" aria-label="Levels" className="mt-3 space-y-1 text-sm">
          {example.levels.map((description, level) => <div role="listitem" key={level}>
              <span className="font-semibold tabular-nums">{level}</span> {description}
            </div>)}
        </div>
      </div>

      {}
      <div className="mt-5 h-40 sm:h-32 overflow-y-auto bg-zinc-100 dark:bg-zinc-900 px-4 py-3" role="region" aria-label="Example state" tabIndex={0}>
        <div className="mb-1 text-zinc-600 dark:text-zinc-400" style={eyebrow}>State (content to evaluate)</div>
        <p className="text-sm leading-relaxed">{example.state}</p>
      </div>

      {}
      <div className="mt-6 border-t border-zinc-200 dark:border-zinc-800 pt-4">
        {}
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-zinc-600 dark:text-zinc-400" style={eyebrow}>Answer</div>
            <div className="mt-3 text-sm font-semibold">Probability of each level</div>
          </div>
          <div className="shrink-0 text-right" role="status" aria-live="polite" aria-atomic="true">
            <div className="text-sm text-zinc-600 dark:text-zinc-400">Confidence</div>
            <output aria-label="Confidence" className="block text-3xl font-semibold tabular-nums">{confidence.toFixed(2)}</output>
          </div>
        </div>
        <div className="mt-1 flex items-center justify-end gap-2 text-xs text-zinc-600 dark:text-zinc-400" aria-live="polite">
          <span aria-hidden="true" style={{
    display: "inline-block",
    width: "10px",
    height: "10px",
    background: accent,
    transform: "rotate(45deg)"
  }} />
          score {score.toFixed(2)}
        </div>

        <div role="img" aria-label={`Probability of each level: ${chartSummary}. Score ${score.toFixed(2)}`} style={{
    padding: `0 ${columnWidth / 2}px`
  }}>
          <div aria-hidden="true" style={{
    position: "relative",
    height: "150px",
    marginTop: "36px"
  }}>
            {[50, 100].map(tick => <div key={tick} style={{
    position: "absolute",
    left: 0,
    right: 0,
    bottom: `${tick}%`,
    borderTop: "1px dashed",
    borderColor: "color-mix(in srgb, currentColor 30%, transparent)"
  }} />)}
            {example.levels.map((_, level) => <div key={level} className="bg-zinc-500" style={{
    position: "absolute",
    left: position(level),
    bottom: 0,
    width: `${columnWidth}px`,
    height: `${percents[level]}%`,
    transform: "translateX(-50%)"
  }}>
                <span className="text-sm font-semibold tabular-nums" style={{
    position: "absolute",
    bottom: "calc(100% + 6px)",
    left: "50%",
    transform: "translateX(-50%)",
    whiteSpace: "nowrap"
  }}>{percents[level]}%</span>
              </div>)}
          </div>

          <div aria-hidden="true" style={{
    position: "relative",
    height: "72px"
  }}>
            <div className="bg-zinc-500" style={{
    position: "absolute",
    left: 0,
    right: 0,
    top: 0,
    height: "2px"
  }} />
            {example.levels.map((_, level) => <div key={level} className="bg-zinc-500" style={{
    position: "absolute",
    left: position(level),
    top: 0,
    width: "2px",
    height: "10px",
    transform: "translateX(-50%)"
  }} />)}
            {example.levels.map((_, level) => <div key={level} className="text-sm font-semibold tabular-nums" style={{
    position: "absolute",
    left: position(level),
    top: "14px",
    transform: "translateX(-50%)"
  }}>{level}</div>)}
            {example.levels.map((_, level) => <div key={level} className={level === 0 || level === topLevel ? endNameClass : midNameClass} style={{
    position: "absolute",
    top: "36px",
    ...tickNameStyle(level)
  }}>
                {example.shortLevels[level]}
              </div>)}
            <div className="ring-2 ring-white dark:ring-black" style={{
    position: "absolute",
    left: position(score),
    top: "1px",
    width: "14px",
    height: "14px",
    background: accent,
    transform: "translate(-50%, -50%) rotate(45deg)"
  }} />
          </div>
        </div>
      </div>

      <details className="mt-5 text-sm text-zinc-600 dark:text-zinc-400">
        <summary className="cursor-pointer">How the score and confidence are calculated</summary>
        <div className="mt-3 font-semibold text-zinc-800 dark:text-zinc-200">Score:</div>
        <p className="mt-1">Multiply each level number by its probability, then add the results:</p>
        <div className="mt-2 font-mono text-sm" style={{
    overflowWrap: "anywhere"
  }}>
          {probabilities.map((probability, level) => `${level} × ${probability}`).join(" + ")} ≈ {score.toFixed(2)}
        </div>
        <div className="mt-3 font-semibold text-zinc-800 dark:text-zinc-200">Confidence:</div>
        <p className="mt-1">TypeSafe computes this from how the probability is spread across the levels. All of it on one level gives 1.0; the more evenly it spreads, the lower the confidence.</p>
      </details>
    </section>;
}

export function TypesafeExample({example, display, title}) {
  const keyStrUriSafe = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+-$";
  function compressToEncodedURIComponent(input) {
    if (input == null) return "";
    return _compress(input, 6, function (a) {
      return keyStrUriSafe.charAt(a);
    });
  }
  function _compress(uncompressed, bitsPerChar, getCharFromInt) {
    if (uncompressed == null) return "";
    var i, value, context_dictionary = {}, context_dictionaryToCreate = {}, context_c = "", context_wc = "", context_w = "", context_enlargeIn = 2, context_dictSize = 3, context_numBits = 2, context_data = [], context_data_val = 0, context_data_position = 0, ii;
    for (ii = 0; ii < uncompressed.length; ii += 1) {
      context_c = uncompressed.charAt(ii);
      if (!Object.prototype.hasOwnProperty.call(context_dictionary, context_c)) {
        context_dictionary[context_c] = context_dictSize++;
        context_dictionaryToCreate[context_c] = true;
      }
      context_wc = context_w + context_c;
      if (Object.prototype.hasOwnProperty.call(context_dictionary, context_wc)) {
        context_w = context_wc;
      } else {
        if (Object.prototype.hasOwnProperty.call(context_dictionaryToCreate, context_w)) {
          if (context_w.charCodeAt(0) < 256) {
            for (i = 0; i < context_numBits; i++) {
              context_data_val = context_data_val << 1;
              if (context_data_position == bitsPerChar - 1) {
                context_data_position = 0;
                context_data.push(getCharFromInt(context_data_val));
                context_data_val = 0;
              } else {
                context_data_position++;
              }
            }
            value = context_w.charCodeAt(0);
            for (i = 0; i < 8; i++) {
              context_data_val = context_data_val << 1 | value & 1;
              if (context_data_position == bitsPerChar - 1) {
                context_data_position = 0;
                context_data.push(getCharFromInt(context_data_val));
                context_data_val = 0;
              } else {
                context_data_position++;
              }
              value = value >> 1;
            }
          } else {
            value = 1;
            for (i = 0; i < context_numBits; i++) {
              context_data_val = context_data_val << 1 | value;
              if (context_data_position == bitsPerChar - 1) {
                context_data_position = 0;
                context_data.push(getCharFromInt(context_data_val));
                context_data_val = 0;
              } else {
                context_data_position++;
              }
              value = 0;
            }
            value = context_w.charCodeAt(0);
            for (i = 0; i < 16; i++) {
              context_data_val = context_data_val << 1 | value & 1;
              if (context_data_position == bitsPerChar - 1) {
                context_data_position = 0;
                context_data.push(getCharFromInt(context_data_val));
                context_data_val = 0;
              } else {
                context_data_position++;
              }
              value = value >> 1;
            }
          }
          context_enlargeIn--;
          if (context_enlargeIn == 0) {
            context_enlargeIn = Math.pow(2, context_numBits);
            context_numBits++;
          }
          delete context_dictionaryToCreate[context_w];
        } else {
          value = context_dictionary[context_w];
          for (i = 0; i < context_numBits; i++) {
            context_data_val = context_data_val << 1 | value & 1;
            if (context_data_position == bitsPerChar - 1) {
              context_data_position = 0;
              context_data.push(getCharFromInt(context_data_val));
              context_data_val = 0;
            } else {
              context_data_position++;
            }
            value = value >> 1;
          }
        }
        context_enlargeIn--;
        if (context_enlargeIn == 0) {
          context_enlargeIn = Math.pow(2, context_numBits);
          context_numBits++;
        }
        context_dictionary[context_wc] = context_dictSize++;
        context_w = String(context_c);
      }
    }
    if (context_w !== "") {
      if (Object.prototype.hasOwnProperty.call(context_dictionaryToCreate, context_w)) {
        if (context_w.charCodeAt(0) < 256) {
          for (i = 0; i < context_numBits; i++) {
            context_data_val = context_data_val << 1;
            if (context_data_position == bitsPerChar - 1) {
              context_data_position = 0;
              context_data.push(getCharFromInt(context_data_val));
              context_data_val = 0;
            } else {
              context_data_position++;
            }
          }
          value = context_w.charCodeAt(0);
          for (i = 0; i < 8; i++) {
            context_data_val = context_data_val << 1 | value & 1;
            if (context_data_position == bitsPerChar - 1) {
              context_data_position = 0;
              context_data.push(getCharFromInt(context_data_val));
              context_data_val = 0;
            } else {
              context_data_position++;
            }
            value = value >> 1;
          }
        } else {
          value = 1;
          for (i = 0; i < context_numBits; i++) {
            context_data_val = context_data_val << 1 | value;
            if (context_data_position == bitsPerChar - 1) {
              context_data_position = 0;
              context_data.push(getCharFromInt(context_data_val));
              context_data_val = 0;
            } else {
              context_data_position++;
            }
            value = 0;
          }
          value = context_w.charCodeAt(0);
          for (i = 0; i < 16; i++) {
            context_data_val = context_data_val << 1 | value & 1;
            if (context_data_position == bitsPerChar - 1) {
              context_data_position = 0;
              context_data.push(getCharFromInt(context_data_val));
              context_data_val = 0;
            } else {
              context_data_position++;
            }
            value = value >> 1;
          }
        }
        context_enlargeIn--;
        if (context_enlargeIn == 0) {
          context_enlargeIn = Math.pow(2, context_numBits);
          context_numBits++;
        }
        delete context_dictionaryToCreate[context_w];
      } else {
        value = context_dictionary[context_w];
        for (i = 0; i < context_numBits; i++) {
          context_data_val = context_data_val << 1 | value & 1;
          if (context_data_position == bitsPerChar - 1) {
            context_data_position = 0;
            context_data.push(getCharFromInt(context_data_val));
            context_data_val = 0;
          } else {
            context_data_position++;
          }
          value = value >> 1;
        }
      }
      context_enlargeIn--;
      if (context_enlargeIn == 0) {
        context_enlargeIn = Math.pow(2, context_numBits);
        context_numBits++;
      }
    }
    value = 2;
    for (i = 0; i < context_numBits; i++) {
      context_data_val = context_data_val << 1 | value & 1;
      if (context_data_position == bitsPerChar - 1) {
        context_data_position = 0;
        context_data.push(getCharFromInt(context_data_val));
        context_data_val = 0;
      } else {
        context_data_position++;
      }
      value = value >> 1;
    }
    while (true) {
      context_data_val = context_data_val << 1;
      if (context_data_position == bitsPerChar - 1) {
        context_data.push(getCharFromInt(context_data_val));
        break;
      } else context_data_position++;
    }
    return context_data.join("");
  }
  function buildHref(ex) {
    const documentText = ex.state === undefined ? "" : typeof ex.state === "string" ? ex.state : JSON.stringify(ex.state, null, 2);
    return "https://console.typesafe.ai/decode#share/" + compressToEncodedURIComponent(JSON.stringify({
      apiVersion: "v1",
      documentText,
      promptsText: JSON.stringify(ex.questions, null, 2),
      selectedModels: ex.selectedModels
    }));
  }
  const displayedExample = display === "questions" ? example.questions : example.state === undefined ? {
    questions: example.questions
  } : {
    state: example.state,
    questions: example.questions
  };
  const code = JSON.stringify(displayedExample, null, 2);
  const href = buildHref(example);
  return <div style={{
    margin: "1.25rem 0"
  }}>
      <CodeBlock language="json" filename={title ?? "request"}>
        {code}
      </CodeBlock>
      <div className="pb-8">
        <a href={href} target="_blank" rel="noreferrer" className="text-primary">
          Try it in the Playground →
        </a>
      </div>
    </div>;
}

当答案是你可以用步骤描述的一个光谱上的位置时，使用 Score。例如，bug 有多严重、客户有多满意，或者候选人有多少 Python 经验。如果答案是固定选项集合之一且选项之间没有顺序，请使用 [Choice](/primitives/choice)。如果是“是”或“否”，请使用 [Noul](/primitives/noul)。[选择问题类型](/primitives#choose-a-question-type)对这三种类型进行了比较。

Score 的答案是在 `score` 中沿你的级别的一个位置，它可能落在两个级别之间。模型还会在 `probabilities` 中返回每个级别的概率，并为答案返回一个 `confidence` 值。

<ScoreExplorer />

每个步骤前面的数字是位置，相关说明见 [级别](#levels)。

## 请求结构

发送到 [TypeSafe API](/api) 的 POST 请求体与任何其他问题类型一样具有相同的三个顶层字段：`state`（要评估的内容）、`model` 和 `questions`。每个 Score 问题包含以下字段：

* `type`：始终为 `"score"`。
* `instructions`：模型要回答的问题，即它要评级的内容。
* `criteria`：一个有序的级别描述数组，从量表的低端到高端。应至少包含两个级别；API 最多接受 10 个。

下面是一个请求示例，其中状态是一份 bug 报告，问题是这个 bug 有多严重：

<TypesafeExample
  display="request"
  example={{
state: 'The export button crashes the settings page in Safari. It works in Chrome, but a few of our customers only use Safari.',
selectedModels: ['jev-latest'],
questions: {
  bug_severity: {
    type: 'score',
    instructions: 'How severe is the reported issue?',
    criteria: [
      'Cosmetic; no impact to functionality',
      'Broken or degraded feature, but workaround exists',
      'Blocking issue; no workaround exists',
    ],
  },
},
}}
/>

问题 id 由你选择，此处为 `bug_severity`。该 id 不会发送给模型。答案会以相同的 id 返回。

### 级别

`criteria` 中的每一项都是一个级别：可能答案光谱上的一个点，用文字描述。级别的编号是它在 `criteria` 数组中的位置，从 0 开始，因此上面的三项分别是级别 0、1 和 2。数组的顺序就是编号。

模型只拿到这些描述，别的什么都拿不到，而且每个级别都是独立地针对状态进行判断的。

响应中的 `score` 是级别光谱上的一个位置。对于三级量表，它从 0 到 2，并且可能落在两个级别之间。

我们的[客户端 SDK](/sdk) 提供类型化的问题。在 Python 中，同样的问题是一个 `Score`：

```python theme={null}
from typesafe_sdk import Score, TypeSafeClient

with TypeSafeClient() as client:
    response = client.system_one(
        state="The export button crashes the settings page in Safari. It works in Chrome, but a few of our customers only use Safari.",
        questions={
            "bug_severity": Score(
                instructions="How severe is the reported issue?",
                criteria=[
                    "Cosmetic; no impact to functionality",
                    "Broken or degraded feature, but workaround exists",
                    "Blocking issue; no workaround exists",
                ],
            ),
        },
    )

    print(response.answers["bug_severity"].score)
```

使用 `system_one` 方法或 `https://api.typesafe.ai/v1/systemone` 端点调用 System One 模型。`model` 字段选择由哪个模型处理该请求。[如何使用 TypeSafe 构建](/concepts/how-to-build-with-system-one)介绍了在代码中的什么位置调用它。

使用我们的[客户端 SDK](/sdk) 之一，或直接调用 [TypeSafe API](/api)。如果编码 agent 正在为你编写集成，请先安装 [TypeSafe agent 技能](/agent-skill#installation)，这样它就了解请求和响应的结构。

<Note>
  `instructions` 和 `criteria` 中的每个级别可以是字符串、对象或数组。先从字符串开始。当某个级别需要一段描述加上几个示例情境时，使用对象。参见下文的[结构化级别描述](#structured-level-descriptions)以及 [API 参考](/api#param-instructions-2)。
</Note>

## 响应结构

响应中的 `answers` 为每个问题包含一个条目，以请求中的 id 为键。以下是对上面示例请求的响应：

```json theme={null}
{
  "model": "jev-1.13.0",
  "answers": {
    "bug_severity": {
      "type": "score",
      "score": 1.43,
      "confidence": 0.35,
      "legend": {
        "0": "Cosmetic; no impact to functionality",
        "1": "Broken or degraded feature, but workaround exists",
        "2": "Blocking issue; no workaround exists"
      },
      "probabilities": {
        "0": 0.0,
        "1": 0.57,
        "2": 0.43
      }
    }
  },
  "usage": {
    "input_tokens": 332,
    "output_tokens": 18
  }
}
```

每个 Score 答案包含五个值：

* `type`：TypeSafe 问题的类型。
* `probabilities`：每个级别的概率，以字符串形式的级别编号为键。所有值之和为 1。
* `score`：级别编号轴上的位置，从 0 到最高级别编号（此处为 2）。它是每个级别编号乘以其概率后相加的结果：0 x 0.0 + 1 x 0.57 + 2 x 0.43 = 1.43。
* `legend`：每个级别编号映射回其描述。
* [`confidence`](/confidence)：一个 0 到 1 之间的数字，根据 `probabilities` 的分布情况计算得出。概率集中在单个级别上意味着高置信度；概率分散在多个级别上意味着低置信度。

1.43 的分数意味着模型在级别 1 和级别 2 之间有所摇摆，偏向级别 1。这与该报告相符：导出功能坏了，对大多数客户来说切换到 Chrome 是一种变通办法，但对只用 Safari 的客户来说不是。模型给“存在变通办法”分配了 0.57，给“没有变通办法”分配了 0.43，置信度为 0.35，因为它在两者之间摇摆。

使用 Python SDK 时，`ScoreAnswer` 以类型化字段的形式提供 `score`、`confidence`、`probabilities` 和 `legend`。SDK 以整数级别（而非字符串）作为 `probabilities` 和 `legend` 的键。

## 解读 Score

我们来看看分数如何随不同输入而变化。例如，使用上面请求中的问题及其级别：

```
"How severe is the reported issue?"
  → 0: Cosmetic; no impact to functionality
  → 1: Broken or degraded feature, but workaround exists
  → 2: Blocking issue; no workaround exists
```

我们可以看到不同的 bug 报告如何改变分数：

<table>
  <thead>
    <tr>
      <th colSpan={3} />

      <th colSpan={3} style={{ textAlign: 'left' }}><code>probabilities</code></th>
    </tr>

    <tr>
      <th style={{ width: '44%' }}>状态</th>
      <th style={{ width: '12%', whiteSpace: 'nowrap' }}><code>score</code></th>
      <th style={{ width: '16%', whiteSpace: 'nowrap' }}><code>confidence</code></th>
      <th style={{ width: '9%', whiteSpace: 'nowrap' }}>级别 0</th>
      <th style={{ width: '9%', whiteSpace: 'nowrap' }}>级别 1</th>
      <th style={{ width: '10%', whiteSpace: 'nowrap' }}>级别 2</th>
    </tr>
  </thead>

  <tbody>
    <tr>
      <td>设置页面上导出按钮的位置偏差了几个像素。</td>
      <td>0.0</td><td>1.0</td><td>1.0</td><td>0.0</td><td>0.0</td>
    </tr>

    <tr>
      <td>PDF 导出按钮点击后没有任何反应。我仍然可以导出 CSV 然后自己转换，但这太花时间了。</td>
      <td>1.0</td><td>1.0</td><td>0.0</td><td>1.0</td><td>0.0</td>
    </tr>

    <tr>
      <td>导出为 PDF 失败，转圈图标永远转不完。我们团队有些人说 CSV 导出对他们仍然有效，另一些人说也失败了。</td>
      <td>1.11</td><td>0.84</td><td>0.0</td><td>0.89</td><td>0.11</td>
    </tr>

    <tr>
      <td>导出按钮会让 Safari 中的设置页面崩溃。在 Chrome 中正常，但我们有少数客户只用 Safari。</td>
      <td>1.43</td><td>0.35</td><td>0.0</td><td>0.57</td><td>0.43</td>
    </tr>

    <tr>
      <td>从今天早上开始，我们团队没有人能登录。每次尝试都会收到 500 错误。</td>
      <td>2.0</td><td>1.0</td><td>0.0</td><td>0.0</td><td>1.0</td>
    </tr>
  </tbody>
</table>

在这些示例中，置信度 1.0 表示返回的分布把全部概率都放在了一个级别上。这描述的是模型的答案，并不保证答案一定正确。

分数是级别编号的概率加权平均值。在第三和第四个示例中，概率分布在级别 1 和级别 2 之间。级别 2 上的权重越大，分数越高。它并不衡量没有变通办法的客户比例。

不同的分布可能产生相同的分数。分数 1.0 可能意味着全部概率都在级别 1 上，也可能是一半在级别 0、一半在级别 2。要区分这些情况，需要结合 `probabilities` 和 `confidence` 一起解读分数。

小数分数是一个位置。你可以用它按严重程度对报告排序，或者在代码只需要一个结果时把它四舍五入到最接近的级别。我们的[实体对齐实战指南](/cookbooks/entity_alignment)展示了四舍五入到最接近级别以做出决策的示例。

Score 上的低置信度通常意味着三种情况之一：级别对这个状态来说相互重叠，问题在衡量不止一件事，或者状态提供的信息不足以定位它。我们的 [Confidence](/confidence) 文档介绍了如何在代码中使用置信度。

## 编写好的级别

描述情境，而不是程度。“功能损坏或降级，但存在变通办法”给了模型可以与状态匹配的具体内容。“中等严重”则没有。具体的描述可以帮助模型区分各个级别。用已知示例核对答案；仅凭更高的置信度并不能说明某个描述更好。

每个级别都是单独评估的。模型看不到级别的编号或相邻级别，所以“比上一个级别更严重”对它毫无意义，描述或 instructions 中出现数字也没有帮助。下面是上表中按钮错位报告在级别只有数字时的情况：

```
instructions: "Rate severity from 0 to 2, where 2 is worst"
criteria: ["0", "1", "2"]
→ score 0.55, confidence 0.33, probabilities 0: 0.45, 1: 0.55, 2: 0.0
```

同一份报告使用那三个描述性级别时，得分为 0.0，置信度 1.0。只有数字时，模型没有可以匹配的内容，于是把概率在 0 和 1 之间分摊。

有多少个能清晰区分描述的级别，就使用多少个，最多 10 个。三个就很好。不要添加你无法清晰描述的级别。

每个 Score 问题只保留一个维度。如果某个描述写的是“守时、聪明又有经验”，那这个问题就在衡量三件事，而一个在某方面高、另一方面低的输入就无法被定位。置信度会下降，分数的意义也随之减弱。把它拆成每个方面一个 Score 问题，然后在代码中组合，下一节会展示这种做法。

如果量表的顶端有一个需要区别处理的罕见极端情形，就为它单设一个级别。一个以“非常愤怒”结尾的情感量表可以加上“辱骂或威胁”。没有这个级别时，这两类消息都可能得到接近顶端的分数。单凭分数可能无法区分它们。

如果完全没有中间地带，且答案是几个离散类别之一，请改用 [Choice](/primitives/choice)，或者把问题拆成几个 [Noul](/primitives/noul) 问题。用你自己的数据测试级别非常重要。同一量表的两种措辞在你的数据上可能表现不同。

## 将复杂判断拆分为多个 Score 问题

复杂判断——即依赖于多个因素的判断——最好拆成每个因素一个 Score 问题。然后你可以在代码中组合 TypeSafe 返回的各个 Score 来做出判断。有些 Score 问题可能比其他的更重要，因此为每个 Score 问题赋予一个表示相对重要性的权重。权重由你决定。当组合结果与你的团队会做出的决定不符时，在代码中修改权重并重新运行。把 Score 问题放在一个请求中发送。它们会被并行评估。增加问题几乎不会改变响应时间，只多消耗几个问题 token；参见[一次提出多个问题](/primitives#ask-multiple-questions-together)。

下面的请求是上表中那个转圈工单，并补充了一些上下文。它提出三个 Score 问题：bug 有多严重、客户有多沮丧，以及报告给工程师提供了多少可用信息。

<TypesafeExample
  display="request"
  example={{
state: 'Export to PDF fails with a spinner that never finishes. Some of our team say CSV export still works for them, others say it fails too. This is the third time I\'m writing in and honestly I\'m done. Steps: open any report, click Export, choose PDF. Chrome 128 on macOS.',
selectedModels: ['jev-latest'],
questions: {
  severity: {
    type: 'score',
    instructions: 'How severe is the reported issue?',
    criteria: [
      'Cosmetic; no impact to functionality',
      'Broken or degraded feature, but workaround exists',
      'Blocking issue; no workaround exists',
    ],
  },
  frustration: {
    type: 'score',
    instructions: 'How frustrated is the customer?',
    criteria: [
      'Calm, just stating facts',
      'Frustrated but civil',
      'Very angry, strong language or threatening to leave',
    ],
  },
  report_quality: {
    type: 'score',
    instructions: 'How much does the report give an engineer to work with?',
    criteria: [
      'No detail; just says something is broken',
      'Names the feature but no steps or environment',
      'Steps to reproduce or environment, but not both',
      'Steps to reproduce and environment',
    ],
  },
},
}}
/>

TypeSafe 的响应：

```json theme={null}
{
  "model": "jev-1.13.0",
  "answers": {
    "severity": {
      "type": "score",
      "score": 1.24,
      "confidence": 0.64,
      "legend": {
        "0": "Cosmetic; no impact to functionality",
        "1": "Broken or degraded feature, but workaround exists",
        "2": "Blocking issue; no workaround exists"
      },
      "probabilities": {
        "0": 0.0,
        "1": 0.76,
        "2": 0.24
      }
    },
    "frustration": {
      "type": "score",
      "score": 1.28,
      "confidence": 0.58,
      "legend": {
        "0": "Calm, just stating facts",
        "1": "Frustrated but civil",
        "2": "Very angry, strong language or threatening to leave"
      },
      "probabilities": {
        "0": 0.0,
        "1": 0.72,
        "2": 0.28
      }
    },
    "report_quality": {
      "type": "score",
      "score": 3.0,
      "confidence": 1.0,
      "legend": {
        "0": "No detail; just says something is broken",
        "1": "Names the feature but no steps or environment",
        "2": "Steps to reproduce or environment, but not both",
        "3": "Steps to reproduce and environment"
      },
      "probabilities": {
        "0": 0.0,
        "1": 0.0,
        "2": 0.0,
        "3": 1.0
      }
    }
  },
  "usage": {
    "input_tokens": 468,
    "output_tokens": 43
  }
}
```

每个问题都独立地针对工单作答并获得一个分数：

* `severity` 为 1.24，置信度 0.64。与开头示例的解读相同：导出功能坏了，但一些人有变通办法。
* `frustration` 为 1.28，置信度 0.58。措辞仍然礼貌，但“第三次”和“我受够了”把部分分数推向了最高级别，因此模型在“沮丧但礼貌”和“非常愤怒”之间按 0.72 和 0.28 分配。对这个工单来说两个级别有所重叠，这就是置信度中等的原因。
* `report_quality` 为 3.0，置信度 1.0。复现步骤和浏览器版本都有说明。

这三个量表长度不同，因此在组合之前，先对每个分数做归一化。四级量表返回 0 到 3，三级量表返回 0 到 2，所以一个量表上的最高分数比另一个上的大。将每个分数除以其最高级别编号，即 `len(criteria) - 1`，就能把每个分数都归到 0 到 1。这样权重才有其字面含义：severity 权重 0.6、frustration 权重 0.3，意味着 severity 的分量是 frustration 的两倍。

下面的 TypeSafe Python SDK 代码提出这三个问题，对每个分数做归一化，并用一个示例优先级计算将它们组合起来：

```python theme={null}
from typesafe_sdk import Score, TypeSafeClient

TRIAGE_QUESTIONS = {
    "severity": Score(
        instructions="How severe is the reported issue?",
        criteria=[
            "Cosmetic; no impact to functionality",
            "Broken or degraded feature, but workaround exists",
            "Blocking issue; no workaround exists",
        ],
    ),
    "frustration": Score(
        instructions="How frustrated is the customer?",
        criteria=[
            "Calm, just stating facts",
            "Frustrated but civil",
            "Very angry, strong language or threatening to leave",
        ],
    ),
    "report_quality": Score(
        instructions="How much does the report give an engineer to work with?",
        criteria=[
            "No detail; just says something is broken",
            "Names the feature but no steps or environment",
            "Steps to reproduce or environment, but not both",
            "Steps to reproduce and environment",
        ],
    ),
}


def normalized(answers, question_id: str) -> float:
    """Put a score on 0 to 1 by dividing by its top level number."""
    top_level = len(TRIAGE_QUESTIONS[question_id].criteria) - 1
    return answers[question_id].score / top_level


def priority(ticket: str) -> float:
    with TypeSafeClient() as client:
        response = client.system_one(
            state=ticket,
            questions=TRIAGE_QUESTIONS,
        )
    answers = response.answers

    severity = normalized(answers, "severity")
    frustration = normalized(answers, "frustration")
    report_quality = normalized(answers, "report_quality")

    # A detailed report helps an engineer investigate, so it raises priority a little.
    return 0.6 * severity + 0.3 * frustration + 0.1 * report_quality
```

对于上面的示例响应，归一化后的分数为：severity 0.62，frustration 0.64，报告质量 1.0。优先级为 `0.6 × 0.62 + 0.3 × 0.64 + 0.1 × 1.0 = 0.664`，四舍五入为 `0.66`。

权重存在于你的代码中，所以你能清楚地看到这个数字是如何得出的，并在排序与团队判断不符时修改它。如果以后需要更多 Score 问题，把它们加入 `TRIAGE_QUESTIONS` 即可。请求数量保持为一个。这种把复杂判断拆分为多个独立的 Score、然后在代码中用权重组合它们的技术，称为[组合评分](/patterns/composite-scoring)模式。

## 结构化级别描述

先为每个级别使用基本的文本描述。当模型在你认为很清晰的输入上持续给出介于两个相邻级别之间的分数时，把每个级别从字符串改为对象，其中一个字段说明该级别涵盖什么，另一个字段给出几个示例情境。每个级别使用相同的字段名，以便模型进行同类比较。

下面的请求是之前用过的那个转圈工单，但每个级别都附带了示例：

<TypesafeExample
  display="request"
  example={{
state: 'Export to PDF fails with a spinner that never finishes. Some of our team say CSV export still works for them, others say it fails too.',
selectedModels: ['jev-latest'],
questions: {
  bug_severity: {
    type: 'score',
    instructions: 'How severe is the reported issue?',
    criteria: [
      {
        what: 'Cosmetic; no impact to functionality',
        examples: ['typo in a label', 'misaligned icon'],
      },
      {
        what: 'Broken or degraded feature, but workaround exists',
        examples: ['export fails in one browser but works in another'],
      },
      {
        what: 'Blocking issue; no workaround exists',
        examples: ['cannot log in', 'data loss'],
      },
    ],
  },
},
}}
/>

响应：

```json theme={null}
{
  "model": "jev-1.13.0",
  "answers": {
    "bug_severity": {
      "type": "score",
      "score": 1.09,
      "confidence": 0.87,
      "legend": {
        "0": {
          "what": "Cosmetic; no impact to functionality",
          "examples": [
            "typo in a label",
            "misaligned icon"
          ]
        },
        "1": {
          "what": "Broken or degraded feature, but workaround exists",
          "examples": [
            "export fails in one browser but works in another"
          ]
        },
        "2": {
          "what": "Blocking issue; no workaround exists",
          "examples": [
            "cannot log in",
            "data loss"
          ]
        }
      },
      "probabilities": {
        "0": 0.0,
        "1": 0.91,
        "2": 0.09
      }
    }
  },
  "usage": {
    "input_tokens": 379,
    "output_tokens": 18
  }
}
```

使用纯字符串时，这份工单得分为 1.11，置信度 0.84。使用示例后，得分为 1.09，置信度 0.87，变化很小，因为纯字符串本来就定位得不错。当纯字符串让模型摇摆不定时，效果会更明显，如下表所示。

示例会引导模型，而且只有当它们看起来像你的真实输入时才有帮助。下表是开头那个 Safari 报告配三组不同的级别对象：

| 级别描述 | `score` | `confidence` |
| --- | --- | --- |
| 纯字符串：没有带示例的对象 | 1.43 | 0.35 |
| 添加了 examples 数组，示例切题：“导出在一个浏览器中失败但在另一个浏览器中正常” | 1.03 | 0.96 |
| 添加了 examples 数组，但示例与浏览器无关：“搜索失败，但浏览分类仍然正常” | 1.43 | 0.35 |

在这个对比中，切题的示例几乎把全部概率集中到了一个级别上。无关的示例返回的结果与纯字符串相同。更高的置信度并不能证明哪个答案正确。选择具有已知预期级别的示例，然后在不同的输入上测试修改后的描述，再决定是否采用。
