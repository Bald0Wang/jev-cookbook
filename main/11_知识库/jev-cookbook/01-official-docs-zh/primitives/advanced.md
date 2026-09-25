# 进阶：结构

> `instructions`、Choice 选项、Score 级别和 Noul 的 `criteria` 都接受 JSON 结构。

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

System One 模型经过训练，能够理解结构。

## 允许结构的位置

上述每个字段都是一个 [`EntryType`](/sdk/javascript/api/type-aliases/EntryType)。

| 字段                                    | 适用于              | 接受的形状                             |
| --------------------------------------- | ------------------- | -------------------------------------- |
| `instructions`                          | Choice, Score, Noul | `string`, `object`, `array`, or `null` |
| `criteria` values（选项描述）           | Choice              | `string`, `object`, `array`, or `null` |
| `criteria` entries（级别描述）          | Score               | `string`, `object`, `array`, or `null` |
| `criteria.true` 和 `criteria.false`     | Noul                | `string`, `object`, `array`, or `null` |

## 何时对问题使用结构

* **当结构有助于清晰性时。**当一个问题有多个部分时，用 JSON 的形式表达它们有助于清晰，因为键自带标签。
* **当问题需要支撑数据时。**schema、分类体系或数据库行本身就是 JSON。直接使用完整的 JSON，或传入相关的子字段，而不要把它们序列化成字符串模板。

## 结构化的 instructions

一个 `field` 对象描述被检查的字段，每个问题通过键引用它。同一个结构可以驱动一个验证取值的 Noul、一个从候选中挑选的 Choice，以及两个在量级上定位取值的 Score。

<TypesafeExample
  display="request"
  example={{
state: {
  source_text:
    'Invoice #4471 issued March 3, 2026 to Beaver Dam Logistics for $12,840.00, net 30.',
},
selectedModels: ['jev-latest'],
questions: {
  invoice_number_is_correct: {
    type: 'noul',
    instructions: {
      field: {
        name: 'invoice_number',
        type: 'string',
        description: 'The identifier printed on the invoice.',
      },
      extracted_value: '4471',
      question: 'Does `extracted_value` match the `field` as it appears in `source_text`?',
    },
  },
  customer_name: {
    type: 'choice',
    instructions: {
      field: {
        name: 'customer_name',
        type: 'string',
        description: 'The organization the invoice was issued to.',
      },
      question: 'Which option is the value of `field` in `source_text`?',
    },
    criteria: {
      'Beaver Logistics': null,
      'Dam Logistics': null,
      'Beaver Dam Logistics': null,
      'Beaver': null,
      'Dam': null,
    },
  },
  amount_due: {
    type: 'score',
    instructions: {
      field: {
        name: 'amount_due',
        type: 'number',
        unit: 'USD',
        description: 'The total the invoice asks to be paid.',
      },
      question: 'How large is the `field` value in `source_text`?',
    },
    criteria: [
      'Under $1,000',
      '$1,000 to $10,000',
      '$10,000 to $100,000',
      '$100,000 to $1,000,000',
      'Over $1,000,000',
    ],
  },
  payment_terms: {
    type: 'score',
    instructions: {
      field: {
        name: 'payment_terms',
        type: 'integer',
        unit: 'days',
        description: 'Days allowed for payment, from terms such as "net 30".',
      },
      question: 'How many days does the `field` in `source_text` allow for payment?',
    },
    criteria: [
      'Due on receipt',
      'Net 10',
      'Net 30',
      'Net 60',
      'Net 90',
    ],
  },
},
}}
/>

在代码中，你可以遍历潜在记录，为每个字段构建一个这样的问题，并在单次调用中全部发送。[SDE 级联实战指南](/cookbooks/sde_cascade)做了与此类似的事情。

数组也可以。当指令是要检查或比较的事项列表时，可以使用数组：

```json theme={null}
"instructions": {
  "question": "Does the claimed sender identity conflict with the sending domain?",
  "compare": ["ticket.sender.display_name", "ticket.sender.email"],
  "focus": "Compare the named organization with the email domain."
}
```

## 结构化的 Choice 选项

Choice 选项的描述也可以是结构化对象。

### 用于边界澄清的 JSON 评分准则

<TypesafeExample
  display="request"
  example={{
state:
  'I ordered the standing desk two weeks ago and tracking still says label created. Was I even charged?',
selectedModels: ['jev-latest'],
questions: {
  department: {
    type: 'choice',
    instructions: {
      question: 'Which team should handle this message?',
      focus: "Classify the customer's primary request, not every topic mentioned.",
    },
    criteria: {
      billing: {
        what: 'Charges, invoices, refunds, or subscriptions',
        not_for: 'Order tracking or account access',
        examples: ['I was charged twice', 'Where is my refund?'],
      },
      orders: {
        what: 'Order status, delivery, cancellation, or returns',
        not_for: 'Charges or account access',
        examples: ['Where is my package?', 'Cancel my order'],
      },
      account: {
        what: 'Login, password, profile, or security',
        not_for: 'Charges or delivery',
        examples: ["I can't log in", 'Change my email'],
      },
    },
  },
},
}}
/>

这个例子告诉模型每个选项覆盖什么、*不*覆盖什么。它使选项之间的边界更加清晰。

### 遍历分类树

要在一个深层分类体系中分类，可以每一层问一个 Choice，并在代码中遍历这棵树。每一步的选项是当前节点的子节点，每个选项的值是该子节点的子树。这样做让模型在选定某个分支之前先看到该分支下有什么，当条目所属的叶子节点无法仅凭分支名称判断时，这一点尤为重要。

这里的状态是一条商品清单，第一个问题挑选一个顶级部门。

<TypesafeExample
  display="request"
  example={{
state:
  "32oz plastic bottle with a flip straw lid. Fits most bike cages.",
selectedModels: ['jev-latest'],
questions: {
  department: {
    type: 'choice',
    instructions: 'Which top-level department does this product belong to?',
    criteria: {
      'Sporting Goods': {
        Cycling: ['Bike Bottles & Cages', 'Bike Lights', 'Helmets'],
        Fitness: ['Yoga Mats', 'Resistance Bands'],
        Outdoor: ['Tents', 'Sleeping Bags', 'Hydration Packs'],
      },
      'Home & Kitchen': {
        Drinkware: ['Water Bottles', 'Travel Mugs', 'Tumblers'],
        Cookware: ['Pots & Pans', 'Bakeware'],
      },
      'Baby & Toddler': ['Sippy Cups', 'Bottle Warmers', 'Bibs'],
    },
  },
},
}}
/>

这个瓶子看起来能归入两个部门。展示子树让模型看到 `Sporting Goods > Cycling > Bike Bottles & Cages` 和 `Home & Kitchen > Drinkware > Water Bottles` 都存在，并权衡清单对自行车水壶架的侧重与日常饮水器具。这个答案上的 `probabilities` 会告诉你两者的接近程度是否值得同时探索两个分支。

选定部门后，用该部门的子节点作为选项、它们的子树作为值来问下一个 Choice，如此重复直到到达叶子节点。在代码中，这可以是对嵌套字典的循环，每个问题的 `criteria` 就是当前节点。[层级分类实战指南](/cookbooks/hierarchical_classification)给出了一个类似的遍历树的例子，其中包括束搜索，当概率接近时保留多条候选路径。

<Note>
  子树可能很大。如果某个分支过大，把值裁剪到它的直接子节点和一部分叶子样本。
</Note>

## 结构化的 Score 级别

Score 的 `criteria` 数组中的每一项都可以是一个对象。

<TypesafeExample
  display="request"
  example={{
state:
  'Fixed the null check in the payment handler. Also refactored the retry loop while I was in there, and bumped the SDK version since the old one had that timeout bug.',
selectedModels: ['jev-latest'],
questions: {
  pr_scope: {
    type: 'score',
    instructions: {
      question: 'How focused is this pull request description on a single change?',
      note: 'Judge the number of independent changes, not the size of any one change.',
    },
    criteria: [
      {
        summary: 'One change, clearly stated',
        signals: ['A single fix or feature', 'Nothing described as "also" or "while I was in there"'],
      },
      {
        summary: 'One main change plus a small related tweak',
        signals: ['A primary change and one minor adjacent edit', 'The tweak supports the main change'],
      },
      {
        summary: 'Several independent changes bundled together',
        signals: ['Two or more unrelated fixes or features', 'Changes that could each be their own PR'],
      },
    ],
  },
},
}}
/>

## 结构化的 Noul criteria

Noul 的 `criteria` 是可选的，当"是/否"的边界很微妙时，结构化的 `true` 和 `false` 描述让你可以用两侧各自的定义和示例把它确定下来。

<TypesafeExample
  display="request"
  example={{
state: {
  sender: { display_name: 'Beaver Dam Builders Ltd.', email: 'donotreply@payroll.example' },
  message:
    'Your Q3 bonus is ready. Reply with your login password so we can verify your identity and release the funds.',
},
selectedModels: ['jev-latest'],
questions: {
  requests_credentials: {
    type: 'noul',
    instructions: {
      question: 'Does the `message` ask the recipient to disclose a sensitive credential?',
      inspect: 'message',
      focus: 'Look for a request to send the credential itself, not a request to change or reset it.',
    },
    criteria: {
      true: {
        what: 'Asks the recipient to reply with, type, or send a password, PIN, one-time code, or other security sensitive answer',
        examples: ['Reply with your password', 'Send us the 6-digit code you just received'],
      },
      false: {
        what: 'No sensitive credential is requested',
        examples: ['Reset your password from the settings page', 'Your statement is ready'],
      },
    },
  },
},
}}
/>
