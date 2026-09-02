---
name: search
description: 按问题类型选择外部检索工具。代码、库、框架、SDK、CLI、API 和云服务等技术问题优先使用 find-docs skill；其他开放网页检索优先使用 Exa WebSearch；打开或读取具体 URL 时使用 OpenAI 官方 Web Search。首选工具额度不足或不可用时静默切换来源。这个 skill 不处理本地文件检索或代码托管仓库任务。
---

# search

这个 skill 负责选择外部信息源，不负责本地文件或当前仓库检索：

- 代码与技术文档问题：优先使用 `find-docs` skill，通过 Context7 CLI 查询。
- 其他开放网页问题：优先使用 Exa WebSearch MCP 搜索。
- 已有具体 URL，需要打开、读取或核验页面正文：使用当前环境提供的 OpenAI 官方 Web Search。

GitHub 仓库、issue、PR、commit、release、workflow 和源码核对等任务交给专门的 GitHub skill。

## 检索路由

```text
用户问题
  |
  v
本地文件、当前仓库代码、日志或配置检索？
  |-- 是 --> 不使用本 skill，按本地任务处理
  |
  v
GitHub 仓库、issue、PR、commit、release、workflow 或源码核对？
  |-- 是 --> 使用 GitHub skill，停止本 skill
  |
  v
用户提供了具体 URL，或需要打开某个 URL 查看正文？
  |-- 是 --> 使用 OpenAI 官方 Web Search 打开并读取页面
  |
  v
代码、库、框架、SDK、CLI、云服务、API 或其他技术文档问题？
  |-- 是 --> 使用 find-docs skill；不可用时静默切换到 OpenAI 官方 Web Search
  |
  v
其他官网、博客、新闻、产品信息、价格规格或对比资料？
  |-- 是 --> 使用 Exa WebSearch MCP；不可用时静默切换到 OpenAI 官方 Web Search
  |
  v
无法判断来源 --> 能合理默认时说明默认后继续，否则再澄清
```

## 基本规则

- 代码相关的外部资料问题优先走 `find-docs`；非代码类开放网页检索优先走 Exa。
- Exa 主要用于发现网页。取得具体 URL 后，如需查看或核验正文，使用 OpenAI 官方 Web Search 打开该 URL。
- 优先采用官方来源和一手来源；需要比较或交叉核验时，再补充高可信第三方来源。
- 必须打开能支持结论的页面，不只依赖搜索摘要。
- 回答保留可回溯链接，并区分检索事实、网页说法和自己的判断。
- 全部检索在当前上下文中完成，不把检索任务委派给 subagent 或 Agent。
- 查不到就说明未查到，不把猜测写成事实。

## 代码与技术文档问题

1. 定位当前环境可用的 `find-docs` skill，并完整读取它的 `SKILL.md`。
2. 按 `find-docs` 的流程使用 Context7 CLI，查询库、框架、SDK、CLI、云服务或 API 的接口、参数、配置、示例、迁移和版本行为。
3. `find-docs` 只作为 Context7 CLI 命令和查询流程的事实源；检索来源选择、失败切换和错误呈现以本 skill 为准。
4. Context7 CLI 未覆盖问题、额度不足、不可用或调用失败时，立即改用 OpenAI 官方 Web Search，并优先检索该技术的官方文档。

不要用 Exa 代替 Context7 查询 API 或配置细节。不要用 Context7 查询新闻、博客、产品宣传页、社区讨论或仓库内部实现。

## 其他开放网页问题

1. 使用 Exa WebSearch MCP 搜索官网、博客、新闻、产品信息、价格、规格、横向对比或其他公开资料。
2. 先寻找官方来源和一手来源；需要对比时，再搜索高可信第三方来源。
3. 需要读取某个搜索结果的页面正文时，把 URL 交给 OpenAI 官方 Web Search 打开和核验。
4. Exa 不可用、额度不足或调用失败时，立即改用 OpenAI 官方 Web Search 完成搜索和页面读取。

## 静默切换

- Context7 CLI、Exa 或其他首选检索工具出现额度不足、限流、缺失或不可用时，不向用户输出“额度已达到”“配额耗尽”、登录、充值或等待额度恢复等中间提示。
- 不对已确认额度不足的同一工具反复重试；直接使用上述备用来源继续完成任务。
- 最终回答只说明实际采用的来源。只有所有可用来源都无法支持结论时，才说明未能核验，不展开内部工具失败过程。
