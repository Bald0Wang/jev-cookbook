# 结构恢复

> 通过两次请求，从丢失格式的纯文本中重建 Markdown：一次把硬换行的行重新拼接起来，一次对每个块（标题、列表、代码、标注）进行分类。

本实战指南处理标记（markup）已被剥离的纯文本（句子中间被硬换行、没有标题标记、没有列表符号），并将其结构重建为 Markdown：标题、段落、列表、引用、代码、标注。输入正是一份恰好处于这种状态的团队备忘录。

文本生成模型可以把文本改写成 Markdown，但改写也可能改变用词。在这里，模型从不生成文本：它只回答关于文档的狭窄问题（*这一行是不是从句子中间接续的？这个块属于哪类内容？*），渲染则由代码完成，因此输出的每个字符都来自输入，而每个判断都带有概率。

整个流水线是每个文档两次 API 请求，按顺序执行：

* **第 1 遍，拼接：** 对每对相邻行提出一个 `Noul` 问题（一种是非问题，其答案就是"是"为正确的概率），询问换行是否把一个句子拆到了两行。所有问题对都放进单次请求，接续被拆分句子的行会被合并回块。
* **第 2 遍，分类：** 对每个合并后的块提出一个 `Choice` 问题（从列表中选一个选项，每个选项都有概率），在标题、段落、列表项、引用、代码或标注（与正文分开的提示、技巧或警告）之间做选择。这些块只有等第 1 遍回答之后才存在，所以这是第二次请求；它还携带每个块的伴随问题（标题级别、步骤顺序、标注种类），只有当块的类型使它们相关时才会读取答案。
* **直接证据留在代码里。** 空行和显式标记（`- `、`1.`、`#`）由代码读取，从不交给模型重新考虑；这份备忘录保留了空行，却丢失了所有标记。模型只收到代码无法从文本中回答的问题。

所有行为都由第 2 遍的问题标准规定：三个由单行描述构成的字典，加上 `classify_questions` 内步骤问题的真/假标准。其余代码都是围绕它们的管道工作。成本和延迟数字见附录：两趟往返、10,211 个 token、0.8 秒，本备忘录花费 \$0.0015。

## 环境准备

```bash theme={null}
pip install ipython 'cooksafe>=0.2.0,<0.3.0'
```

然后设置 `TYPESAFE_API_KEY`。每个 API 调用都缓存在 `json_cache.json` 中，该文件随实战指南一起提供，因此重新渲染时无需调用 API 即可重放已公布的数字。删除该文件即可实时重新运行全部内容。

```python theme={null}
import os
import re
import urllib.request
from pathlib import Path
from time import perf_counter

from cooksafe import JsonCache, make_playground_link
from IPython.display import Markdown, display
from typesafe_sdk import Choice, Noul, NoulCriteria, TypeSafeClient

TYPESAFE_MODEL = "jev-1.12"
PRICE = (0.042, 0.00)  # $ per 1M tokens (input, output); TypeSafe jev-1.12 as of 2026-09
client = TypeSafeClient(api_key=os.environ["TYPESAFE_API_KEY"], timeout=120.0)
json_cache = JsonCache(Path("json_cache.json"))
```

## 文档：一份丢失格式的团队备忘录

测试文档是一份关于构建系统迁移的备忘录，处于它到达纯文本收件箱时的状态：段落被硬换行到句子中间，一条 shell 命令孤零零地占一行，两个列表没有符号或编号，一条警告没有任何标记表明它是警告。文本从一个固定的 gist 获取，以保证实战指南的数字可复现。

```python theme={null}
GIST = (
    "https://gist.githubusercontent.com/eugene-shvarts/6df7daf97233bf92bcdd6b386a0fa561"
    "/raw/5da03690611fb6ddcbaabdb91fb9f91d9751b113/build-memo.txt"
)


@json_cache
def fetch_document(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "typesafe-cookbook/1.0"})
    with urllib.request.urlopen(request) as response:
        return response.read().decode()


RAW = fetch_document(GIST)
print(RAW[:560])
```

```
Migration to the new build system

Hi everyone, quick heads up about the build system migration that is
happening next week. We have been running the new pipeline in shadow
mode for three weeks and the results look solid, so it is time to
make the switch for real.

What changes for you

The old make targets keep working until the end of the month. The new
entrypoint is a single command that wraps everything, including the
docs build that used to be separate.

bun run build

Generated artifacts no longer need to be committed. The new pipeline
uploads them
```

行拆分、空行跟踪和 id 标注都在代码中完成；不涉及模型。每行获得一个短 id（`L014| `）；这些 id 是模型作为状态一部分读取的普通文本，问题和答案通过这些 id 引用行（与[语义搜索实战指南](/cookbooks/semantic_find)相同的方案）。

```python theme={null}
def to_lines(text: str) -> list[dict]:
    lines, gap = [], False
    for raw in text.split("\n"):
        stripped = re.sub(r"[\t ]+", " ", raw).strip()
        if not stripped:
            gap = bool(lines)  # a leading blank is not a break
            continue
        lines.append({"text": stripped, "gap": gap})
        gap = False
    return lines


def tag(items: list[dict], prefix: str) -> str:
    return "\n".join(
        f"{chr(10) if item['gap'] else ''}{prefix}{i:03d}| {item['text']}"
        for i, item in enumerate(items)
    )


def line_id(i: int) -> str:
    return f"L{i:03d}"


def block_id(i: int) -> str:
    return f"B{i:03d}"


LINES = to_lines(RAW)
print(f"{len(LINES)} non-blank lines. The model sees, e.g.:")
print("\n".join(tag(LINES, "L").splitlines()[19:24]))
```

```
28 non-blank lines. The model sees, e.g.:
L013| The cutover touches three teams, so check whether you are on this
L014| list before you plan anything for Monday:
L015| The platform team
L016| The web client team
L017| Whoever still owns the release tooling
```

## 第 1 遍：拼接被拆分的句子

每对相邻行一个 Noul 问题，全部放进一次请求；被空行分隔的行对会被跳过。这个问题刻意狭窄（"这一行是不是从句子中间接续的？"），这接近于关于文本的客观事实。附录涵盖了两方面：措辞的选择，以及合并阈值是如何推导出来的。

```python expandable theme={null}
def join_question(i: int) -> Noul:
    return Noul(
        instructions=f"Does line {line_id(i)} pick up mid-sentence, continuing a sentence left unfinished at the end of line {line_id(i - 1)}?",
        criteria=NoulCriteria(
            true="The line starts in the middle of a sentence that began on the previous line - the line break tore the sentence apart",
            false="The line begins a new sentence, item, heading, or thought of its own",
        ),
    )


@json_cache
def stitch(wording: str = "mid-sentence") -> dict:
    make = join_question if wording == "mid-sentence" else naive_join_question
    questions = {line_id(i): make(i) for i in range(1, len(LINES)) if not LINES[i]["gap"]}
    started = perf_counter()
    response = client.system_one(
        state=tag(LINES, "L"), questions=questions, model=TYPESAFE_MODEL
    )
    return {
        "joins": [
            response.answers[line_id(i)].noul if line_id(i) in response.answers else 0.0
            for i in range(len(LINES))
        ],
        "seconds": round(perf_counter() - started, 2),
        "usage": [response.usage.input_tokens, response.usage.output_tokens],
    }


result = stitch()
print(f"{sum(1 for l in LINES if not l['gap']) - 1} pair questions, one request, "
      f"{result['seconds']}s")
```

```
16 pair questions, one request, 0.32s
```

合并的截断值取决于上一行如何结束。在悬空行（没有句末标点的行）之后，拼接概率达到 0.2 或以上就合并该行对；在终结性标点（`.` `!` `?` `:` `;`）之后，截断提高到 0.5。附录逐步讲解了这两个数字背后的概率。

```python theme={null}
JOIN_AFTER_DANGLING, JOIN_AFTER_TERMINAL = 0.2, 0.5


def ends_terminal(text: str) -> bool:
    return re.search(r'[.!?:;…]["\')\]]*$', text) is not None


def merge(joins: list[float]) -> list[dict]:
    blocks = []
    for i, line in enumerate(LINES):
        bar = (
            JOIN_AFTER_TERMINAL
            if i and ends_terminal(LINES[i - 1]["text"])
            else JOIN_AFTER_DANGLING
        )
        if blocks and not line["gap"] and joins[i] >= bar:
            blocks[-1]["text"] += " " + line["text"]
            blocks[-1]["lines"].append(i)
        else:
            blocks.append({"text": line["text"], "lines": [i], "gap": line["gap"]})
    return blocks


blocks = merge(result["joins"])
healed = len(LINES) - len(blocks)
print(f"{len(LINES)} lines -> {len(blocks)} blocks ({healed} line breaks healed)")
for i, block in enumerate(blocks):
    n = len(block["lines"])
    print(f"{block_id(i)}  {n} line{'s' if n > 1 else ' '}  {block['text'][:62]}")
```

```
28 lines -> 17 blocks (11 line breaks healed)
B000  1 line   Migration to the new build system
B001  4 lines  Hi everyone, quick heads up about the build system migration t
B002  1 line   What changes for you
B003  3 lines  The old make targets keep working until the end of the month. 
B004  1 line   bun run build
B005  3 lines  Generated artifacts no longer need to be committed. The new pi
B006  2 lines  The cutover touches three teams, so check whether you are on t
B007  1 line   The platform team
B008  1 line   The web client team
B009  1 line   Whoever still owns the release tooling
B010  1 line   Things to do before Monday
B011  1 line   Update your local toolchain to version 2.4 or later
B012  1 line   Delete the old build cache directory
B013  1 line   Run the doctor script and fix anything it flags
B014  3 lines  If the doctor script reports a red result on the toolchain che
B015  2 lines  As Dana put it in the kickoff, "a migration nobody notices is 
B016  1 line   Thanks, and shout if anything looks off.
```

## 第 2 遍：为块分类

每个拼接后的块都会得到一个 `Choice` 问题：*这是什么类型的内容？* 下面这三个字典，加上 `classify_questions` 内步骤问题的真/假标准，构成了分类器的全部规范。没有其他逻辑。要把这个流水线适配到你自己的文档上，只需编辑这些描述。

```python theme={null}
TYPE_CRITERIA = {
    "heading": "A short label or title that names the document or the section that follows it - not a full sentence of content",
    "paragraph": "Running prose: one or more complete sentences of explanatory or narrative text",
    "list_item": "One entry in a list of parallel items - an ingredient, a feature, a task, an attendee; reads as one of several sibling entries",
    "quote": "Words attributed to a person or source - quoted speech, a citation, an excerpt someone else wrote",
    "code": "Computer code, a shell command, terminal output, or a config snippet meant to be read verbatim",
    "callout": "A warning, tip, or important note that interrupts the flow to flag something the reader must not miss",
}
HLEVEL_CRITERIA = {
    "title": "The title of the whole document",
    "section": "A major section heading within the document",
    "subsection": "A minor heading nested under a section",
}
CALLOUT_CRITERIA = {
    "note": "Neutral extra information the reader should be aware of",
    "tip": "A helpful suggestion or shortcut that makes things easier",
    "warning": "A caution about something that can go wrong or cause harm",
}
```

下面的一切都是管道工作：构建问题、发送一次请求、读回答案。如果类型返回 `heading`，渲染器需要标题级别；如果是 `list_item`，需要知道顺序是否重要；如果是 `callout`，需要知道是哪一种。类型此刻还未知，而等待它们意味着第三次往返，所以伴随问题在同一次请求中提前提出。这些答案大多永远不会被读取：段落的步骤概率毫无意义，直接忽略即可。多加一个问题代价很小，因为状态占了大部分 token，无论如何都只发送一次；而多一次往返会增加整整一个请求的延迟。

```python expandable theme={null}
HEADING_MAX_CHARS = 90  # longer blocks can't render as headings, so don't ask


def classify_questions(texts: list[str]) -> dict:
    questions = {}
    for i, text in enumerate(texts):
        bid = block_id(i)
        questions[f"type_{bid}"] = Choice(
            instructions=f"What kind of content is block {bid}?", criteria=TYPE_CRITERIA
        )
        if len(text) <= HEADING_MAX_CHARS:
            questions[f"hlevel_{bid}"] = Choice(
                instructions=f"As a heading, what level would block {bid} occupy in this document's structure?",
                criteria=HLEVEL_CRITERIA,
            )
        questions[f"step_{bid}"] = Noul(
            instructions=f"Is block {bid} an instruction in a sequence where the order of the items matters?",
            criteria=NoulCriteria(
                true="It is one step of a procedure - the items around it must happen in order",
                false="Order is irrelevant - it is a loose collection, or not a list item at all",
            ),
        )
        questions[f"callout_{bid}"] = Choice(
            instructions=f"What kind of aside is block {bid}?", criteria=CALLOUT_CRITERIA
        )
    return questions


@json_cache
def classify(texts: list[str], gaps: list[bool]) -> dict:
    tagged = tag([{"text": t, "gap": g} for t, g in zip(texts, gaps)], "B")
    questions = classify_questions(texts)
    started = perf_counter()
    response = client.system_one(state=tagged, questions=questions, model=TYPESAFE_MODEL)
    judgments = []
    for i in range(len(texts)):
        bid = block_id(i)
        type_answer = response.answers[f"type_{bid}"]
        hlevel = response.answers.get(f"hlevel_{bid}")
        judgments.append(
            {
                "type": type_answer.choice,
                "confidence": type_answer.confidence,
                "probabilities": type_answer.probabilities,
                "hlevel": hlevel.choice if hlevel else "section",
                "step": response.answers[f"step_{bid}"].noul,
                "callout": response.answers[f"callout_{bid}"].choice,
            }
        )
    return {
        "judgments": judgments,
        "n_questions": len(questions),
        "seconds": round(perf_counter() - started, 2),
        "usage": [response.usage.input_tokens, response.usage.output_tokens],
    }


classified = classify([b["text"] for b in blocks], [b["gap"] for b in blocks])
for block, judgment in zip(blocks, classified["judgments"]):
    block.update(judgment)
print(f"{classified['n_questions']} questions about {len(blocks)} blocks, one request, "
      f"{classified['seconds']}s\n")
print(f"{'block':<6}{'type':<11}{'conf':<6}{'companion used':<18}text")
for i, b in enumerate(blocks):
    companion = {
        "heading": f"level={b['hlevel']}",
        "list_item": f"step={b['step']:.2f}",
        "callout": f"kind={b['callout']}",
    }.get(b["type"], "-")
    print(f"{block_id(i):<6}{b['type']:<11}{b['confidence']:.2f}  {companion:<18}"
          f"{b['text'][:46]}")
```

```
62 questions about 17 blocks, one request, 0.51s

block type       conf  companion used    text
B000  heading    0.99  level=title       Migration to the new build system
B001  paragraph  0.98  -                 Hi everyone, quick heads up about the build sy
B002  heading    0.75  level=section     What changes for you
B003  paragraph  0.89  -                 The old make targets keep working until the en
B004  code       1.00  -                 bun run build
B005  paragraph  0.90  -                 Generated artifacts no longer need to be commi
B006  paragraph  0.43  -                 The cutover touches three teams, so check whet
B007  list_item  0.99  step=0.15         The platform team
B008  list_item  1.00  step=0.16         The web client team
B009  list_item  0.99  step=0.12         Whoever still owns the release tooling
B010  heading    0.96  level=section     Things to do before Monday
B011  list_item  0.98  step=0.86         Update your local toolchain to version 2.4 or 
B012  list_item  0.99  step=0.87         Delete the old build cache directory
B013  list_item  0.92  step=0.90         Run the doctor script and fix anything it flag
B014  callout    0.65  kind=warning      If the doctor script reports a red result on t
B015  quote      0.99  -                 As Dana put it in the kickoff, "a migration no
B016  paragraph  0.92  -                 Thanks, and shout if anything looks off.
```

每个块的判断都在那张表里，伴随问题一列展示了提前拿到的答案如何派上用场："Things to do before Monday" 下面的三行带着接近 0.9 的步骤概率（它们会渲染成编号列表），三行团队条目接近 0.1（渲染为圆点列表），而那条没有任何标记的 doctor 脚本警告被分类为 `warning` 类型的标注。附录分析了模型唯一没有把握的那个块。

## 渲染

代码根据这些判断组装页面。连续的列表项合并成一个列表，当各项步骤概率的平均值至少为 0.5 时使用编号。该阈值是一个组级别的决策，没有任何单个问题直接问过它。

````python expandable theme={null}
STEP_THRESHOLD = 0.5
HEADING_MARK = {"title": "#", "section": "##", "subsection": "###"}
CALLOUT_MARK = {"note": "NOTE", "tip": "TIP", "warning": "WARNING"}


def to_markdown(blocks: list[dict]) -> str:
    groups = []
    for b in blocks:
        if b["type"] in ("list_item", "code") and groups and groups[-1][0] == b["type"]:
            groups[-1][1].append(b)
        else:
            groups.append((b["type"], [b]))
    parts = []
    for kind, items in groups:
        if kind == "list_item":
            ordered = sum(b["step"] for b in items) / len(items) >= STEP_THRESHOLD
            parts.append("\n".join(
                f"{n + 1}. {b['text']}" if ordered else f"- {b['text']}"
                for n, b in enumerate(items)
            ))
        elif kind == "code":
            parts.append("```\n" + "\n".join(b["text"] for b in items) + "\n```")
        elif kind == "heading":
            parts.append(f"{HEADING_MARK[items[0]['hlevel']]} {items[0]['text']}")
        elif kind == "quote":
            parts.append(f"> {items[0]['text']}")
        elif kind == "callout":
            parts.append(f"> [!{CALLOUT_MARK[items[0]['callout']]}]\n> {items[0]['text']}")
        else:
            parts.append(items[0]["text"])
    return "\n\n".join(parts) + "\n"


markdown = to_markdown(blocks)
print(markdown)
````

````text expandable theme={null}
# Migration to the new build system

Hi everyone, quick heads up about the build system migration that is happening next week. We have been running the new pipeline in shadow mode for three weeks and the results look solid, so it is time to make the switch for real.

## What changes for you

The old make targets keep working until the end of the month. The new entrypoint is a single command that wraps everything, including the docs build that used to be separate.

```
bun run build
```

Generated artifacts no longer need to be committed. The new pipeline uploads them to the registry automatically, and checking them in just creates merge conflicts.

The cutover touches three teams, so check whether you are on this list before you plan anything for Monday:

- The platform team
- The web client team
- Whoever still owns the release tooling

## Things to do before Monday

1. Update your local toolchain to version 2.4 or later
2. Delete the old build cache directory
3. Run the doctor script and fix anything it flags

> [!WARNING]
> If the doctor script reports a red result on the toolchain check, do not proceed with the migration. Ping the infra channel first and we will sort it out together.

> As Dana put it in the kickoff, "a migration nobody notices is the only kind worth shipping."

Thanks, and shout if anything looks off.
````

上面的每个字都来自输入。流水线只选择了边界、类型和标记。

## 在 Playground 中打开

这条分享链接包含拼接后的块和完整的第 2 遍问题集。打开它即可实时重新运行分类。

```python theme={null}
playground_link = make_playground_link(
    tag(blocks, "B"),
    classify_questions([b["text"] for b in blocks]),
    models=[TYPESAFE_MODEL],
)
display(Markdown(f"🔗 [Open the stitched memo + questions in the TypeSafe playground]({playground_link})"))
```

<a href="https://console.typesafe.ai/playground#share/N4IgJg9gxgrgtgUwHYBcAqCAeKQC4AEIAQgAxkA++AsgJYDmATgIYo0RL4oScAWC+SBAHd8AIxg0ANmHwBnAJ6yUCOAB0k60iQCMlABI18CAG4IG89ggA0+AI4SoAa3x8mYWfhgAHfE1EQYFF5+cSkZBSUVfDh6ZlZ2XhZ8Gg8eJi8vZBokOgEsIKEEBEcAOnwAdX400zEijgYYJCRs3JQ+PJEvGkzJbP5suTTIETgIMH4AMwgGXgYi-ELijyYkGTb+OdkYSRQPSQgIZ1kIXrAbY+SglM4aRE5uOCZHfnW5IRoUKB58KZm5pkkJXUmjIACZKOU0kEvis6AgPL98BYYMCkFoAMyUNDtE4yR7PThMBhw3b4Z4IHxCaaOFqeVBSYJGVb4CATRmjVA8MrY-iCETIFDmLwQbJXZZyFqSfhQCBwR7MtpJITMLweExmeRtFo2bJQSQwMC016QKAeULSRJBGCyBBrbiifg2rxElgIIEaNFkAAslHE9UaYgk0lRWgArJQAOLIMyumRE1gTJhQUlIbj7HJmPK2+61fAyuUfZRgbntPn4Lo9PqeLz7NwedZwHOvOZ0FKC+S+QKylg0KAAyTyGwrGRfBBOI18RsDABW1uh-2UHkQxOl7AmvWTsndIJIADYse1YFxTDMuDBR-WeHMXggmHBZOduKOnAs+OsZsjfHMWRwtXs27Uvz8J+NYrL4SCajwtKIlQ7BgEw8i4DuADsB78KBKC-I2yh3juAAcaELAgoh5r0AqcLeaieiQACcEI8BA6ozEoUiSCyQhIJeGwIFKTA2vcJwtCGOgkAeLT1twkCAdM-CwasCHCdouj4AAql48HKEiAQzPsfZsVwJwwgMXD4CeshsBwoIlF6LI6a6DAgto4L4AAIjxCCaa8uKBmEeZJu0hpzMm0zyI5mL4AASgGxrQFwzFQAw3RBMOPw0Jg4GQbSHw-JITB0LIik+vgACSbIxcF8WJV4QRzMKDCkkw+BzDImzbEECSvAZkhGRwz6ODYUmpkEXgMNARQyO8bTsrEPbsGUAAKE79EgEzMHmaRNDxqUMEo4ETfw7ySGxxz1ZcLKBPcJJ8Aw26eto4b4AAgh4LkrI1XgXdlxntDSTishMNiqCAjUxIws0cKm-hgB2Q29vCyRcT+A5ktkE3TFNshQRkLRAiAin7vg2IrI4D57YMARXGyKyZTk+D7IcHj-SUIA2CAI2ytVsgYNgeCEMAQMoPImQAPpaCQQMEPzICC5kEv4EDXwilACBA4DIDZEoDTJhZBW80DkJJDSzKsnm7DKKgCNiLpzhiwA-Kr8sgAlHxmDQTBy1LriGjkctA495OnblDpsdMNwoFKloCHe8PlfA5Gh68Nrax1UI-Cc+xCB42UALQCBAyU-Nsx0CsgyssmyMqoAKDtA86zBg14PC+yAUVNLS7M2gQli2dEMmm3ANYeY6JdIMrjNslgoFICwIU99PDBxDQNTKNgNcgL0SjCy7ah6yAADyghMu2yQcI1G-tWydf9lt28eLnYEtM1NACkOPy3igMBzK-KB8f14G+Cgc24wEAAG4mq3ncL4Rmh8TY2hPACCUohei0wFIleEa97D5xVrvco0xIEsEFDQcQRYczvTMMcDgodjifzLrnTBJDZCZDHDwV+UAPjgyHBwLAysGDVTkLKBA3ceL8WVFgteMpxjNwAMIc0CJmCR1hfCDB4mxfM8ozgUQYDEaeIdAgfRQDYUOjVK4THoHIZoGQPLRFvBbEyDpwFuFMmYUQPYd5qz0vsQIzd-ZCCJM0HINhWBeEMTMW4dUf4WyGi8VOoozANE5oydcEARAmXXHlfhiAtS02bBAzMcA5x5yCDEWQusAC+pS1Y8ClKYSQosyDi15lLGW2CCAKwYnDNeGtBTnniJxbx4ovbalfEkapW0qTbBkEg6ANt6ksigLALwHZvrXBNHHVAAByDwmsemfwQPbFmjtnbKESu7RpAsPhSmbjyMOEcTavCEAxCOqzECoDXknXp3johMGnFQscvSXAQNpJNKCv4ArQDWSgN5MBRDvIsp87RodBm00EJEGQjRxgzEarC9gQNylq0iF4OpZAPYCyFi0x2qZtidM4t05OfTd7FTNNbfAYt-5dK1v8gYWKED2FLgda60T+B4MzHc9ot8vmAPIfs9xiVjluxJdLBo5KgbFTFD+R0ygfAm3eqNZWYBdn4Fzq8cVRIAjMmyvk3aaRLEcAGMKhyBygaJkkDaZue8GAYstjQBe7ljArCCLnL64p6b8RlEdP5FkQmFKUefS4UQkj9lxRUw5-YKZEoaZLUlstd6Kw6Y69WNKOU62bgbIIRsZDavMuMS2UyXx23EbK12pzM0gCic3AAcggQIzA2L5DWtkLC4NGT-E9ZjAIFp7FMF8d+Vka8gmfL4JILwExthyBgHQOELEEhUIYvVI8kd8QxxBflIwfFn4OrVtO-xdBPl9kCBZXw-gLrHEyceyOfYOB0G4KI2moc738TSFopNatmlEu0Aq5pzdc3K2pdsulutWkgFLSjY2FczbkWuLWmZOhpWHMbSchVSKb2739mOwOfgtoJwudEpI09ECI2efHU87RsWgqSFMI6ySs4BujY1FdR05AjzLibSu5tIX5qvg3Juu9W7XvLKNTu6qe6jG-PmQemkbRV1HvDE2k9crTzih2UO89F7L3yGvc+W9lA70QwffgqClmnzpgBE2V9w1sXFffW1OQn4vyURMd+uzv6-04QAoBRQwEjuWNAoVbI4ExmOkQ5BuRUHP11mrehyqkN4OWIAxKxDswmTITtbdzFtK0LsDALB4QmFfFYew3poXuFmD4S+wRh9hEHVGsocRYwssyIHnImYCjX6YxUf3dRgSzDaIQRTfRUbjFrjMbICxmQik2KCHY7ijiTwuNYG4lNnGvEkYWH4oZQSo1hPRv6wpNGrhVwXt4UkrwkkpO4Gk3IbWsmtHaCOvJBShrRBSGU5NQMCVgYg2S5ulLJCwdpb0hDjtGVW2mSysg2g2WFp6Q+rlgneXadfGYQVtlPWiv6NZpcBCpUNpdgRs5iqYBZdVZbbuBLy5KPZnqg1RqxUU6-GamQFqCnWsyN5knZg17Otdbvd1nrrjermNUm7ga1VnwOKG9OEb2BRsB2fAC28AG+COsBw7niUAQ-p5BnN7SYP5vZdj9giP9ap3Lezs91bMPMq0NoXDCt8Pyvp223enbu0IL7Y1Ad0xHj-JyW4TMY6Jm5inUSWLc7ugLp4su1dWwN3wn+Tu9G+7FRFKeEe8Sp7zIS-zVeoSJ273-L8BTDJHk33F78p+79o1f3DaYNaKoRId54sdqBrQoJIfZsQ9B7Bat7fwZLS71G7PRMYaZaj0fvunb++bfgT2gKfYnbI0EIOlHTzUcjnRo9-BGMWwTixrXbGggcYztxw1vHC4Cc0+bYTaGtPibVpJlUaTRDWTduBTBALuGBGYFTVcAeKUDTITHTCeTAKeGecwOeIkUzG8VefNSzbeN1DrVANA3HWNVzF0dzONe8V-B+HzW0Z+VAV+ALFgILJRH+WQP+MCKnVYCLBxfBGLdneLHtRBZLI+NBdLR2TLEtHLMLfLORO0DnchUrfhGhfgOhKrBhWrFhJRNhH+Rrf+ZrXhIINrIRF1LrMRfNBRaRWRY5U2cYUbRdVRWUSbTRGbXRFAebHuRbFaZbVbKxRAG7LbHgpxBgPbW4cRVNY7RDHxM7AJG4YJHuK7eqG7KJSOWJR7BJF7DOHMD7Zvb7YdXJKAgHfOIHEpE3IGKpdUWpUfcfLLKfOHItR3fpJRIjGwB5EZCohYcdSZL3MEOZBZRzXgFZcFF5FATZOQeHXZDfI5JtCDajK5doVgcOWLRkB5E4K-IY6ufNVjeFb5X5OlAFNwIFD4EFRka-P-R2LYGFe-eFbIRFPfXIFFEhdFTMblOlUokAcHKoy3KHXeGHOoh3elRDZHLDNHEgUETHODTlJzG0fHMuB5InRke1dnY1PnaPY5WQSYrfCDJVZuZna4VnTVN3eTMafVb8HncnFQZYUadFM6S1IIEXZAE+cXC9R2KXLLWXTMeXH1JXC2FXS2NXCADXcNOlHXIovXXaA3BNY3EAIfBWcI83T4ltK3SfG3afR2WfBHefQ2RfStGgD3VfOtMEDE2nAPFtIPRDEPQUMPbAftFaKPIdWPUdBiRPSdadVPfNedE7RdLPY6ddTdfPZiXdT4C6NvQ9S8cvW8SvZkoGGvffSIvye9BIRvZ9ARXItvD9fAL9BYLvXIP9XvADAfN4kfMgdEaoqDFUv4ufHBBfVDU2X-GtbokgdEI0uVbfXfA42Mx2UjQMumCjEOU-RY8-aOBjdYm-ZjYePYtvJ-LjM6XOXXd-YuLTb-WssTNeAA9IIAx2EA2mDucApTUOaA-udTYeRcxAowZA-TVAozGYEzHsMzbAtWXA6zfA+zQg-osUi+csMgqUDzPnLzE+RgWgvzPjQLL+FgkLf+Tg4BSLCBaLPcuLJiBBcyJBWkVLdBfNCQnBKQghGQkhIrcsBQyhMrZQ1-TLGrIoOrLQhrSNPQzAHhVrARYwkRbrVUhWPrSwwbawkbJRMbATNRYcKbLRbIWbPRQIBbWs0xT7Hw9bfw+0bbGQXbVxMIo7cTOMmMugQJboS7Aea7SJLBFIh7eJZ7doV7LI3KT7FM1vX7fI6IQoopYHN4j44s0sn48dCsjUhlfU7DdEcE+HHHKEnlRnAnOE78LyD1EVMqXnCkiVNE5s6Yy3bEhlNVfEikQkznW0bnRkE1Kk81IpYXdIUXRk+1SXAEaXWzMK0JLOLkkwZXM6a4fkwUqUYUueUU5zcU6zQ3RNaU0HJ2OUolEsr4ifQ5csu3LHSsxDZDV3HUvUlHA0xs2KunU0sw80rtS03ta0iPW0rRe0qyuPAMzopPV08uNPLwDPJdfjNdXPLdQigOIMzbVOUMgYnINUM9KvS9aI4jOM+vB9JMwwiyicJIdMzMn9HMnvPvFwAsrqkDMlIlL0Zy5UpWFigtCE4tKsrUms5fC2T3Nfb0eak0nfMou4z5Q-Hs4OHuBYiONvC-Yc2AYYsmu-Cc1OKczOGct-fjBcr-JYjGs42uF0KTZuLc3IHciAoVKAvuNTOA48jm8eM8lAwzdAheW8rA7m9eNsKzFQZ8kQt81qj8tzb8igu+THACw0ICt+Jg0CxqVg9g0+SVLg0BHg2C7uWBBCxLZClBQgtLDBNQrLXBD1XLQhArOQ4rChHuahBgCrUiuQDQ+rHQ6isCfQ+ixARi0wnrcwti3eAbfReRPrOw8bPi1YASlw86Nw0Sjw8S7w7oNbaxGS3MEdIIkIg7WU5Sz5NSjSuI0OBIiJIIZItvVIwyxGEy1JMynIyyuS-7XaQHYpEHSpUZSo70OGoahGtylGyIgZO4lo1OGejo50hsmyaAPoxkv8fAU40YiEiYmnFsmYxYuYl4M-MnV8VYo+kc5WrYk7R4H5Zie-fY72XIYFb6NYmmjY-FaFF+uMhFGYIjPIVFOkT1F4j5SG84zVGG+eoGX4ka5Ghojyma7DGyag9BsXblGE-leE0K0nCK8kyg1E6ncwzE+KxnHEpKw+NnbVIkrnUkzKvnU1akoXK1fKhku1cq4qkwt1cqr1Kqv1Hk2q4NdXVcIU3Q4zFq2NCU5KKUmUnq5SpBgamo4amfUa9y8a6sitKmKtfoTykEr0XG1slBpax2C0wQ8PE+QdGPHax0-al0lPI6909PT0zPc6nPP0h9AvPdYM+60vMMp6ivc9NeNS29XvBvJ9X619f66EMCIG7Mnuf9fvIDeBrNBAIlUMZBp2bRtU3R5ex2Ca7Un-MTes7GkgUMCxwjQmg-bs4-Psm5O7KOejE4p+um8cpx9jdOacnOVmouQTE8pfdDV5CTXmwA-mxoOTIWvc0W1TDmCW0ZqW9nPTN6OW4zDAxWiie8x2R89WmXAg4+YglzS+L8m+X8w23zeg-zECxRC28Cjgm2qC+2qBOCwTeBF24Q1CsQoGDC8arCvLIhWQ0hfCkra60O8Or2si5haOjhGiuihJ9rezEwrMsw9xNOxDDOobGwp55RXixw-i5woS1w9woxMuySiu3wjbHMexWuhS-bJSs3Zu961urS8JJIvSnugyp7fuzIwe9JL7EengseruooyehyxBsMAp1BnRvBp3EAIEhs0MHy+o-BvHQK2EgVBEkRu+8VShnaep2hpnBhjVFK5htKkklQ9hqKzhnKmynhm1QqgR-NVk4RuXSqxXaqiRoNGNaR02WR6i+RguRR9qyU2HbJtRs3PJgp2otB3yjB-RtGwxqBXUkxrBkEup8+uKxalO5a0PNay0hxu0px0eva50-gZPGdCYY60670i6-xxQw-IvEJ54MJk9CMyJ6vd6mJhM0+eJ4epJ9vDMzvdgEG+M-MrJ1RosvcBNopoGdU0p53NN8ZusrG2a3cU1ltIjIm5p3ssms-SmocrpgB0cxkVjSOJml-WclqtmtZvlDdlcqZ+uGZmTOZ0AgU3cx2pZmAo8p97TaWzZgzWeHZhW1gO85Wo5mzR2OzTWxk989nXW65qKv8x+QC+54Cs2wly20LSC7gqLT5x2+Cn5oQlC92tCjLL2yQ326QsF3C7gIO1t8rO1iOxhcizQ4xKi7XZFlrVFpOzFlO7FyRdOqwrO2w7i+wibUl45QuubEuqlkxcuyxaS2xWSwI5l0I8wuU9lhga9Tl+I7SxI3SzyGJfl9I4yoV97Ie0VpacVgo8eqV+ymNxyhdzR6HVypNzV5V1Vmp3cDV-4pD7V594K4nREw1lEqnE1vNha-Ghnc1lnRhgk613VdKth5Eh17KwXXKl1gq-hjFQR0q+DkRzk318RnjAN+qmRxquR68hR-XSN5R6N1RjxNNLQXcRdxenz-45V8pms93LN4Ezr3dhLs0mxlaux9astraitxz8mat3wQ62dTxk67xs67PX0vPAJvaoJu6pIB677Z6yMqJ-tuvWJ764d+z7JVOQGid7vadzJwfbq+d5CbrvNRV5NgEspgxl9lfbNrQZCMbts7+g99GEmk-Npwczp2OWm2-Xph9ScgZ5moZucx9z-Z9kTCZ5WtcxuWZtubcsA4W5TMWlZoeIDseDZ88rZ8D683ZqDpWizVWvAk5l8s5pzEgy5ntPWzzW5rDgxB53D4LNggjt5ojmCkjmBMjhLCjt2whaj8Q2jzC+j7CxjwrZjyF4OqhNjkiuFyOrjxF3QuO2igT5vIT0RETw5HFx2PFzi7O6T3Okl-OslnRIuylzFal8xWl9TzbTTpl5xRS3Tpuk7Fu2IrlnSyV8zpIXugVxJGznKEVv627yt51qP4oqex2compIld7zz63Hrr73zxoxqZo4ZI-do8ZCdBs5CXo7wfow+4+rZcYuYEH85K+3ea5cmpY+5R5f+iFN5K41+nYj+vYiB3+0Ffv4YqFS4141+m48Bu4yBx4rgz3l+1R9zvPxU74xDBV4ppVnE0xoHoLvY3HaEnVohkKnEA1sh-W6KqhmVY0yxxL+h5Ly1rVKmFhjLu1rLygx13LtPuDVdaFdXqLJEqmyTK4+tfUNVarnTCDZho6uobBruGya7xoWubxdroEFz4fdbcRfPrpqTLQVMM201EbmQGB5xc8aUsCbkDFsZWlS2keObkj2cbx4nSE6Gtit3rZrdG2vjbbldRDqBl22h3UJo9W7YvUoyIAaJhd0HaPom8N3H7ADRSYPcp2GTcGrO1e7Q0tAeEHAYjRXYptfu67bHpuyP5kA8IbfEAPuyaYQ8Wmx7Acqe1h5goL27UMcoJgZr9NOMqPHjOjxGaY8Cchg19v-mmbrkCe8zYnos17jLNYCFPHwVT10w08wOaBCDpgX2YwcWeT5Nnoh3Oa7RSCPPNDpQQw40Fja2HU2h-HNqEhReEFcXnbWI58QvmAhRCklko4K8AWIAIFmUxBb+1wWeFTIFCxDq69VC1WA3gi0oox0+OJvFFubw6wYtLeiNCwuJw4qSdCWPFBwnKDk7TZyW7vJTp7xU40s1OVdDTjXQgR10g+7iPTqHw5bh9jO3LMzu01j5WdJgCfbInILyK7VABE9Vzqo2z48QiUWg-PvDU+779vuyrZ6E0TXrl86YlfVxg2Twh19FkB9KCB4Cb5jEOUZ9ahk-0vqXJO+8xW+rfxWJPIn6g-OfqAxH4uD-k4-I4n-UfqOCZ+IDTskDlTCL92y9xPPNmCeJr8h+G-WViYPlbec8BY1JHMYJIDQjcG33ELufzC56sSG4Ve1hQxi7okKBz-bpElzxIpcrWn-G1hlV-6UkBcNJPKsAMIpFcPW4Ar1hySgHckququOAT+2DaIC+OYbGNKgMbBRsMBvVTQdoKXp6C12hAwbsY2qazVTB8ohVNQJAC0CS2NpRxkwNT4J42By3dxqtxAxeM4yXpHgZdX9I3VBBJeTtiIJO69s3qBnWvJ9Uu6JlruyfeQckw7yYtHuKgwDC9yhoiwtANEN0b1z5GeiUM6bLmr6Oww0QzBFguMsTWsFUZbBqcKmuewhQ9MSRTAtwc-hZpeCP8CBf7pMwCHvsghn7QnoLVCF-twhAHVZtENPKgdLy8tJISvBSGbxWetmU5kQU54XNPyOQn8uh356FDBeOHEoXhxebW1wsVQyXjUNI7fNZeSFP5lR2aGtD9Y7QnChr3kI9CdexFfoeoUN7DCkWYws3kYUmFMUsW1vMTriwk7DYHeWKGTnnQ0Tyd1hinQXspyWw7DK6fhfYYy0OHacG6sbCmPp0M4XD26JnTurdn0rHI+68fZJKZST6JMU+C3WktGmlYxtPhs9WiI2N5F6NOyq9RkevTaI1It61fGpjRBhEN94RlIiFCfRb57IAxluWYpiJvoDk76uIqfoA3OJD8iR79ccQkDJFZIRx0-TYsAwsm0iwGX9WkA8RZGr9uK7I7qu5wbG-CKUPIgEcX0wakDaIJ-SEt5MIaE4r+ItUhtKMpySpYuqIi+ma1f7Kj3+qVdLra1fyaj+cXDPLnSV4Zi4iqhooRjLkgHJAxGMAi0SGlq734RSKAtqmgKNytduqmA+UmQH8nb9BqbSQvsFPwGo0vR6bIbh2JBJdjdJBbLLCGLPL0DNq0eCMQtyjGTJ2BsYzgfGPW6JifGW3FMbtzTHBMhBmY47hE1AHRlzuBY6QT9RHa3cFB5Y4GukzzLPdCyGgkSBJIGnNikMf3PwQD1IHaASA3Yxpr2MPak0BxFNIcWezh5MYr2n9ZHu4LvbDNZxYzb6QuMdh48NyQMAWkSUUwbiDy4tKIQgRA5xD9xiQvZkeOZ4ni0hZ49nhePtFZDue18W8XkPvF0FHxxQ5gs83KGvN3x0FOsFLyWJ1DfmjQ0Qp7WsbATVeoLAOhC26Ha8iKYddjvr045DCeOIwpAE1lN4GEJh6LFCVb1YroTbemEgljnWJYrCXeBEt3kRLErbDveuwiiX7wOE7ZA+LLYPmyzOF5iYiF2S4ZHzYl8sOJcfDItxOFbmU+JP2VPoJLeElERJM9OpH9LenLsSmHokAMCNL6gjWiFfBSVXy6LY0-pqkuEYMUcFaTkRrfSaQl277X1oexkvvhpIcn4pnJfsL5FZOva2TjikMlGWDicmEiXJC-NycimZFoovJsDOFG505ExyApVjKlE2KkkqpjB2c4UZq1FEBVxRxDa-vFLynGs5RKU-NiXISqAkLWYxVURzmykajIqf-HLjqPy58N9Rp0kAJ6wqnesqpFXGqXyUtENUGpzVJqVcGa6tTnR6jUgCPJ6laN+pccg-kNNbFu4fRW7GZH9LMFBiZp9jBgQtJTiRjWBK0mMXWwbYbcm2fjHbq2wEEHSMxZecJj2yvmSCLpcTWQSWPfSKCKxygx6aoJrHD4XpSkWOUjUBEEDQFyMtVL9J9zFzQe+Y2kX2KPagz2mw4luU4OhmuDH8KPeGTOPZpY9KmZknmkuPx4riQhP7EnvuTJ6RD4CJ5QmbLTp5RxIOS8JnjgVSHHMqZGQy8XTOvEMy7++Qo2izIYKPMReVtMLMgHebVC+CTtcjn+KFke10KyvYFuLI6FMdwJMspQnLL14DDFZFFZWfBK4TqyE6aLIwFMOYq9Y9ZQMO3gsKNnLCnCZs4SsXWIlbDSJ1s8ifSwCIB9gixw03PRNdmMSPZzEq4VHxuGWcjK9wgObZ14kt4HOf2Jzun2EkfCo5v88DKPMKaAKWFIUleiCNklgjN6GcwHjoAxx716+uchEU-QLk7Ii5G8+Lk0n0mIYu+2I5YpXNOIEi4Glk3YqSKX4T97JCi94u3NOWdz6R3cpkVA1ZHeS5+HIikNHOGX-yvO48ySauxVbTyMcs84LmfwXlBUJRy8qUavNlFmDFR6UvgkwzVGHzMux8rUQVMAH0kSp7rNWDfLKp3yFc0A-1rVPgGa4mqdo5Dkoy-kxsOpXy5hboJ+4tjJqRjTNmNKGXQLRZwYqbnQLDHltFpPSxbtGNrZukNp3AnaS22ha4KDu+CrttmOIXnTaRX1IseQuDmUK7paTXMmDWrHPS6xOgMfCMsTb-KE5A3NsTjzZV6qAZjI8HuRhBn9kwZtGCGQ4NHEI9rJD+NOHDOnEPtvBc4jhauUCHKLgCX7InmorCG4zye2i9ZrEL0UJD6ehi6DuTPNynj4O54rWlz2sXkE+e1BexSbUYLPjnFYvbmR8y-HS8fxghHxfL2Fn+LOVPtfBBLM6Ga9pZrHKCZViiVR04JxveJeMKQlazk6Mwm3hkoNlcUcJTvE2fhLWHmyRKhSrQsUpWw+89hdsqiQ7MqVOyThIfVSucPqWhIWJPLaPvdl9l3Cco7SxPkHK6X8SBVYclzhHIGUVFo5+qn5QX3+FALWFJGGSd-TklpyxkkIrOWCSWWwjlkqy-Oc30Lk6StllA9vhiL2VYijJOIo5fiM2K1zE59c85Q+ibkUjjljk2fvcrrmuSIGHkvuTA1dUytPlv8u9SXJ36BS-l70yeYCvmVOQIpflKKRfxikRcb+CU+-slMf6pTFS28pHLvKRUHziSR88huiqdaCSsVbrA0biqNG3yTR98oleaKfl1TrRr8ildrQoIdUVG7Ul0XqvpXxzGVn0gwSypIHdEnIHKwtpN2LazTeVjAxBUtOQUHU1p6CraZtx9K7ScFhePBV8iOnHo5V4gkhYqsLFDsVVp60sWO1SaTsHpWqiGnO0YX9V71fw3AVRoBUmr5xnCkzU2R4UE0rVlgm1VD274w9L8VcqGYnBhmM0pFnqguBjx9XyLW5bMf1ejJbhBq1xIanGZosA47jdFF5bZrGsPHmYTFFMsxcmupmpqrxqHRmQbSzV3NWZua9mWUJcWEcPxvM4tfzOdpy8UsAEkWeZrFm1rglYEljtCz6EtqYJSsvMLx1Vn8cNZ3a5JdrL7XpKQAmSrCVJ2HXGzcl46-JR72nVeEyJdLauouvkqOydOq6l2eurdnqUmJW6xpd7Is77rWlh6t7MeuukhyBJtlDPm8VEnRy4tZG3qaMsfXjLBpky5OdMtTngj05X6g0toG8q-q1JeczSUBo2UgbONm8nZR30g2GTbkMGh+uhprkdzsNxIxuZcvJGT8ittWi4jSOw1dzcNvc6Bs8UI1DziNOgTHU0nI1jzo2Rq-Tf53J3eUQVp-fytFPC76sV5aK9jevMZ3bKBYPGlVHxtS7IrBNqK4TflNE26iCul88QXitK4ErqpxKxTaSpDa2jkBtMj+S1M6ptdtNFO3TcAtTbDSwFrKiBWjgp1mbpp3K0MRtXDG2aBVy0hzWgq4EYLkxEq-gR5ulVeaCFog07n21B0DsyFyZVVWmSoX3TNVM7ehTk2jmw0DVS7PHR9JS0cLzV2gcxplvMGAz+FwMvLSe3Bn2DTJl7ErRIvdVTi0eXqxGRzVS1+qlFDWzGQs1a0RD2tBM6ntGqvIGLetBzIGLBw1oOYQuaasbbYuZk5qnFYFTmW+LcUS8ltnimXmWoaEVq-FNHatSBPV6B0teTaiJdBOzDRLuOp2lWWrK7UMVkJvatJf1kHXYSiWOS1YYJQnUFLLZM6qSvOoZZyUjhK66pREVpFh9N1yQbddcPYlxI-Z1nI9Y8IoUOkJWQk94b5OHkt74tFG1XUloTka7IFODbzHg3nl67IVcU6FUbrXlwqLdKrK3fvJ1S26f+Ru--mfKKl6imSxXCAR7ofle66qz8+qeSv92UrP5werTT-J0BMGsdAC3HQyv65fSjNw3Ezb3tA3P8YFSeqzSnr5Vp7rKGetxlntFU57xV2CyVQXoPTCDjpRCvzQqrrlKqgtVekLWqvHbULItDenVbk1-n5NW9Yysw2wuZXLkfpJm3NrYYabZagZVgwRXauEWOrx9YiyfX00kUerZ9lW71UjJq2496twQ79tjMgKbjDy24rfVGq636KbyjPZIQmrVpwcgYCHE-ZkJ1pXNxtVBbzNmqKEzbSh+HCoYWo8W1DVt5a9bU0M23e0v9ksroQRV6HNqOOba2JR2rPLgHE6kB4TrdpgPzDHtiw3Cc7zHVIH3tmwz7RJRKU-bKJWBmiayxqUg66lmlT2aZyaWkG0isOgeh0pPWplmBvSug1eoYPy77o3IyjU+omX8jaN6rbXZFIIZMb9dkomYFFyirCG+98KxKm-z3kf8BNrDaQ-btkPcN5DzuxQ2VJK7DHKphKs0a-lgFKaEBKm7Q2pqpV6GgdHXHQEkeYN9TTDem8w4ZuIFWGs52R03WBtbScrYFM3eBdtSQWuNVpHh4fAmNpFJjvDfAwJrdX8PebwyYgs7uXqkGV7UWUJ26dEbr2g04jMbIstoC67JHxTEe-QVHq72x7f5O7PvT2MH0FHbV0POwYVtOJjjr2sMmfZ4Ln2yLfB9RpfXlA-aBrVxWM39q0bDVaLJafKTrbTxjV77SZfWh8qYqGP7wU1p+0bRMYv2TaBeji4Xjfvm2VCeZvBFY94tf3rHK1H+rbdliCWgSf9jag7QcYVlHGQDcS044hIgM9rLj0B9ipnVuPZLZOpst7RSxeOeE3js6m2WUv97USAdtEjqQxPOwAmGlXs7utDrIMHrwTCOp4TQZhPhzM+ZRQZToFdOimcdiWlE-juklTK31MyiEdvSzmBcqdKy4XSMTp3JgUR8phUbssdj7LoNhyznXBu51YbENb9ZDTZIF12TRF1IhDf7Bw1L88N0utke8vhOEpfTSJ1g++Y+kcG49gXTEwxuxOLzYpTJJEkIdhXEnRDuJRFdbspPf9cpMh0+XSaAEMnSpUm8qfitk1sm-WCm9Q1ybJX1c38EbIPZpsFNYDSLbpt8+3uo2d7LD3ev0zkcDxKmHDcC+aWqbs0anUFIq7U5tN1PbTXNeew0+mKL2yqTpwRi06Qqu7BabTZYu0xqodNPSuqpSA5MDC6AAA1chBZF5ggBjA2gQKzaDq62hYI4wF1LzAADaIAacCYGzjaASgTkEAAAF1SkQAA" target="_blank" rel="noreferrer" className="text-primary">在 TypeSafe Playground 中打开拼接后的备忘录 + 问题 →</a>

***

# 附录

## 成本与延迟

```python theme={null}
tokens = [result["usage"], classified["usage"]]
total_in, total_out = sum(t[0] for t in tokens), sum(t[1] for t in tokens)
cost = total_in / 1e6 * PRICE[0] + total_out / 1e6 * PRICE[1]
n_joins = sum(1 for l in LINES if not l["gap"]) - 1
print(f"pass 1  {n_joins} questions  {result['seconds']}s")
print(f"pass 2  {classified['n_questions']} questions  {classified['seconds']}s")
print(f"total   {total_in + total_out:,} tokens  "
      f"{result['seconds'] + classified['seconds']:.1f}s  ${cost:.4f}")
```

```
pass 1  16 questions  0.32s
pass 2  62 questions  0.51s
total   10,211 tokens  0.8s  $0.0003
```

两趟往返，10,211 个 token，0.8 秒，\$0.0015。

## 拼接阈值从何而来

第 1 遍得到的逐行拼接概率：

```python theme={null}
print("join  line")
for i, line in enumerate(LINES[:18]):
    join = "    " if i == 0 or line["gap"] else f"{result['joins'][i]:.2f}"
    print(f"{join}  {line_id(i)}| {line['text'][:66]}")
```

```
join  line
      L000| Migration to the new build system
      L001| Hi everyone, quick heads up about the build system migration that 
0.77  L002| happening next week. We have been running the new pipeline in shad
0.62  L003| mode for three weeks and the results look solid, so it is time to
0.39  L004| make the switch for real.
      L005| What changes for you
      L006| The old make targets keep working until the end of the month. The 
0.42  L007| entrypoint is a single command that wraps everything, including th
0.59  L008| docs build that used to be separate.
      L009| bun run build
      L010| Generated artifacts no longer need to be committed. The new pipeli
0.48  L011| uploads them to the registry automatically, and checking them in
0.40  L012| just creates merge conflicts.
      L013| The cutover touches three teams, so check whether you are on this
0.50  L014| list before you plan anything for Monday:
0.22  L015| The platform team
0.11  L016| The web client team
0.12  L017| Whoever still owns the release tooling
```

这些概率落在两个分离的区间：拆分句子的换行得分在 0.39 及以上，作者本意的换行得分接近零。但两个区间之间的截断点放在哪里，取决于**上一行如何结束**——这是代码可以直接读取的事实：

* 在*悬空*行（没有句末标点的行）之后，0.2 及以上的任何值都算作接续。这里真正的接续得分低至 0.39（`L004| make the switch for real.`），因此单一而保守的 0.5 截断会拆散原本健康的段落。
* 在*终结性*标点（结束句子或分句的字符：`.` `!` `?` `:` `;`）之后，截断提高到 0.5。备忘录中的团队列表说明了原因：`L015| The platform team` 跟在冒号之后，得分 0.22。这是一个低但非零的"这句话在接续上文"信号，它会越过 0.2 截断，把列表并入引入它的那个句子。没有任何单一阈值能同时适用于两种情况；一旦代码先检查标点，两个区间便分开了。

## 为什么问题是"从句子中间接续"而不是"同一段落"

这个流水线的第一个版本问了那个显而易见的问题："这两行是否属于同一段落？"它以一种特定的方式失败了。标题下的一串短行（录入时没打列表符号的列表）在宽泛意义上*确实*是一个段落：这些行挨在一起、共享一个主题。被问到段落时，模型对每一对都回答"是"，拼接遍便把整个列表合并成一个长块。

同一份文档，同样的请求结构，只有措辞变了：

```python theme={null}
def naive_join_question(i: int) -> Noul:
    return Noul(
        instructions=f"Are lines {line_id(i - 1)} and {line_id(i)} part of the same paragraph?",
        criteria=NoulCriteria(
            true="The two lines belong to the same paragraph of running text",
            false="The two lines belong to different paragraphs or different pieces of content",
        ),
    )


naive = stitch("same-paragraph")
print(f"{'':14}{'mid-sentence':>13}{'same paragraph':>16}")
for i in (15, 16, 17, 20, 21):
    print(f"{line_id(i)}{'':2}{LINES[i]['text'][:36]:<38}"
          f"{result['joins'][i]:>7.2f}{naive['joins'][i]:>13.2f}")
print(f"\nblocks after merge: {len(blocks)} (mid-sentence) vs "
      f"{len(merge(naive['joins']))} (same paragraph)")
```

```
               mid-sentence  same paragraph
L015  The platform team                        0.22         0.77
L016  The web client team                      0.11         0.81
L017  Whoever still owns the release tooli     0.12         0.78
L020  Delete the old build cache directory     0.08         0.88
L021  Run the doctor script and fix anythi     0.05         0.91

blocks after merge: 17 (mid-sentence) vs 12 (same paragraph)
```

采用段落措辞时，每个未标记的列表项得分都高于 0.75，两个列表都塌缩了，备忘录合并成几个连绵不断的块。"同一段落"让模型判断主题是否延续，而在列表项之间主题确实延续。"从句子中间接续"问的是文本本身。当一个主观判断要喂给阈值时，问题就应该指明决定它的那个最狭窄的事实。在这里，措辞就是 17 个块与 12 个块之间的差别。

## 置信度最低的块

```python theme={null}
uncertain = min(blocks, key=lambda b: b["confidence"])
print(f'"{uncertain["text"]}"')
print(f"confidence {uncertain['confidence']:.2f}: ", end="")
print(", ".join(f"{k} {v:.2f}" for k, v in
                sorted(uncertain["probabilities"].items(), key=lambda kv: -kv[1])[:3]))
```

```
"The cutover touches three teams, so check whether you are on this list before you plan anything for Monday:"
confidence 0.43: paragraph 0.53, list_item 0.24, callout 0.19
```

引入团队列表的那句话确实存在歧义——它命名了接下来的内容（像标题），本身又是完整的句子（像段落），而且所处的位置正是标注可能出现的地方。概率也相应地分散开来（paragraph 0.53、list\_item 0.24、callout 0.19），UI 可以把这一点呈现出来——例如，对类型置信度（获胜选项背后的概率）低于 0.55 的任何块加下划线以供复核。
