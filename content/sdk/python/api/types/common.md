# 通用类型

> TypeSafe API SDK 的通用类型。

export function SdkSignature({children}) {
  async function copy(event) {
    const button = event.currentTarget;
    const code = button.parentElement.querySelector("pre code");
    try {
      await navigator.clipboard.writeText(code.textContent);
      button.setAttribute("aria-label", "Signature copied");
      button.dataset.copied = "true";
    } catch {
      button.setAttribute("aria-label", "Copy failed; select the signature to copy");
    }
    setTimeout(() => {
      button.setAttribute("aria-label", "Copy signature");
      delete button.dataset.copied;
    }, 2000);
  }
  return <div className="sdk-signature not-prose">
      <button type="button" className="sdk-signature-copy" aria-label="Copy signature" onClick={copy}>
        <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <rect x="8" y="8" width="12" height="12" rx="2" />
          <path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3" />
        </svg>
      </button>
      <pre tabIndex={0} aria-label="SDK signature"><code>{children}</code></pre>
    </div>;
}

<a id="common-types" />

<h2 id="typesafe_sdk.JSONValue">
  typesafe\_sdk.JSONValue
</h2>

`module-attribute`

<SdkSignature>
  <span className="n">{"JSONValue"}</span>{" "}<span className="o">{"="}</span>{" "}<span className="n"><a href="https://typing-extensions.readthedocs.io/en/latest/index.html#typing_extensions.TypeAliasType">{"TypeAliasType"}</a></span><span className="p">{"("}</span>{"\n"}{"    "}<span className="s2">{"\"JSONValue\""}</span><span className="p">{","}</span>{"\n"}{"    "}<span className="s2">{"\"str | int | float | bool | Sequence[JSONValue | None] | Mapping[str, JSONValue | None]\""}</span><span className="p">{","}</span>{"\n"}<span className="p">{")"}</span>{"\n"}
</SdkSignature>

类似 JSON 的值。可以嵌套，并可包含 `None`。

<h2 id="typesafe_sdk.JSONContent">
  typesafe\_sdk.JSONContent
</h2>

`module-attribute`

<SdkSignature>
  <span className="n">{"JSONContent"}</span>{" "}<span className="o">{"="}</span>{" "}<span className="n"><a href="https://typing-extensions.readthedocs.io/en/latest/index.html#typing_extensions.TypeAliasType">{"TypeAliasType"}</a></span><span className="p">{"("}</span>{"\n"}{"    "}<span className="s2">{"\"JSONContent\""}</span><span className="p">{","}</span>{"\n"}{"    "}<span className="s2">{"\"str | Mapping[str, JSONValue | None] | Sequence[JSONValue | None]\""}</span><span className="p">{","}</span>{"\n"}<span className="p">{")"}</span>{"\n"}
</SdkSignature>

可以是纯字符串，也可以是 [`JSONValue`](/sdk/python/api/types/common#typesafe_sdk.JSONValue) 条目构成的映射/序列。
