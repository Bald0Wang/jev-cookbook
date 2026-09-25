# 更新日志

> TypeSafe AI API 的 Python 客户端

<a id="changelog" />

<h2 id="v071-2026-09-21">
  v0.7.1 (2026-09-21)
</h2>

<h3 id="bug-fixes">
  Bug fixes
</h3>

* 提前校验 API key，并确保其值不会出现在异常日志中

<h3 id="documentation">
  Documentation
</h3>

* 为 AI 网关的使用方式补充示例

<h2 id="v070-2026-09-18">
  v0.7.0 (2026-09-18)
</h2>

<h3 id="breaking-changes">
  破坏性变更
</h3>

* 序列化/反序列化（ser/de）库已从 `msgspec` 更改为 `pydantic`

<h3 id="bug-fixes">
  错误修复
</h3>

* `str` 子类现在会正确地序列化为字符串，而不是字符列表

<h3 id="features">
  新特性
</h3>

* `system_one` 方法现在接受新的 `response_model` 参数，可将其设置为所需的 `pydantic` 模型，从而获得额外的 *类型安全* 保障

<h2 id="v060-2026-09-15">
  v0.6.0 (2026-09-15)
</h2>

<h3 id="breaking-changes_1">
  破坏性变更
</h3>

* `Score.criteria` 现在接受有序序列，而不是以整数为键的字典

<h3 id="features_1">
  新特性
</h3>

* 改进 SDK 输入的类型注解，使其接受 `Mapping` 和 `Sequence` 等抽象类型
* 改进错误消息，包含 http 详细信息与元数据

<h3 id="bug-fixes_1">
  错误修复
</h3>

* 处理 `RetryPolicy` 中的无效值
* 使异常与响应支持 pickle 序列化

<h3 id="documentation">
  文档
</h3>

* 在主[文档](https://docs.typesafe.ai/)中链接了更多概念

<h2 id="v057-2026-09-14">
  v0.5.7 (2026-09-14)
</h2>

这是 TypeSafe Python SDK 的首次公开发布。更多信息请参阅[文档](https://docs.typesafe.ai/sdk/python)。
