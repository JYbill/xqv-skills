---
name: search
description: 按问题场景使用 Context7 CLI 和 Exa WebSearch MCP 检索并回答。用户要求查询库、框架、SDK、CLI、云服务或 API 文档时，先完整读取 find-docs skill，再按其说明调用 Context7 CLI；用户要求联网搜索官网、博客、新闻、产品信息、对比资料或其他开放网页资料时使用 Exa；find-docs、Context7 CLI 或 Exa WebSearch 不可用时，回退到 Agent 官方 Web Search 工具。这个 skill 不处理本地文件检索或代码托管仓库任务。
---

# search

这个 skill 只负责两类外部信息源：

- Context7 CLI：查库、框架、SDK、API、CLI、云服务文档和版本用法；具体查询流程以 `find-docs` skill 为准。
- Exa WebSearch MCP：查开放网页资料，例如官网、博客、新闻、产品页、对比资料和非文档型资料。

GitHub 仓库、issue、PR、commit、release、workflow、源码核对等任务交给专门的 GitHub skill，不在这里处理。

## 逻辑流程

```text
用户问题
  |
  v
GitHub 仓库、issue、PR、commit、release、workflow 或源码核对？
  |-- 是 --> 使用 GitHub skill，停止本 skill
  |
  v
本地文件、当前仓库代码、日志或配置检索？
  |-- 是 --> 不使用本 skill，按本地任务处理
  |
  v
库、框架、SDK、CLI、云服务或 API 文档？
  |-- 是 --> 完整读取 find-docs skill，按其说明使用 Context7 CLI；不可用时回退到 Agent 官方 Web Search
  |
  v
官网、博客、新闻、产品信息、价格规格、对比资料或最新网页？
  |-- 是 --> 使用 Exa WebSearch MCP；不可用时回退到 Agent 官方 Web Search
  |
  v
无法判断来源 --> 先澄清；能合理默认时说明默认后继续
```

## 基本规则

- 先判断用户要的是“技术文档”还是“开放网页资料”。
- 能用 Context7 查到的库文档，不用 Exa 代替。
- 需要最新网页、官方公告、博客、产品信息或跨来源对比时，用 Exa。
- `find-docs`、Context7 CLI 或 Exa WebSearch 不可用、缺失或调用失败时，回退到 Agent 官方 Web Search 工具，不凭已有知识补全时效性或版本敏感事实。
- 全部检索在当前上下文中完成，不把检索任务委派给 subagent 或 Agent。
- 本地文件工具只用于定位并读取 `find-docs` skill，不用来替代外部检索。
- 查不到就说明未查到，不把猜测写成事实。
- 回答要标明信息来源；如果是自己的整理判断，要和检索事实分开。

## Context7 CLI

使用场景：

- 库、框架、SDK、CLI、云服务、API 的接口、参数、配置、示例、迁移、版本行为。
- 用户问“怎么用”“某配置是什么意思”“某版本是否支持”“报错和官方用法是否一致”。

使用步骤：

1. 先确认库名和具体问题。
2. 定位当前环境可用的 `find-docs` skill，并完整读取它的 `SKILL.md`。
3. 严格按 `find-docs` 的流程调用 Context7 CLI，完成库解析和文档查询。
4. 用查到的文档事实回答，并标明来自哪个库或文档主题。

`find-docs` 是 Context7 CLI 查询流程的单一事实源。本 skill 不复制它的命令、参数和认证细节。找不到 `find-docs`、Context7 CLI 不可用或调用失败时，回退到 Agent 官方 Web Search 工具，并优先检索该技术的官方文档；不要改用 Context7 MCP 或 Exa 猜测技术文档答案。

不要用 Context7 查新闻、博客、产品宣传页、社区讨论或仓库内部实现细节。

## Exa WebSearch MCP

使用场景：

- 开放网页、官网、博客、新闻、产品信息、价格/规格、横向对比、组织或项目公开资料。
- Context7 不覆盖，或问题明确要求联网、全网、官网、最新资料。

使用步骤：

1. 优先搜索官方来源和一手来源。
2. 需要对比时，再补充高可信第三方来源。
3. 打开能支持结论的页面，不只依赖搜索摘要。
4. 回答保留可回溯链接，并区分事实、网页说法和自己的判断。

Exa WebSearch MCP 不可用、缺失或调用失败时，回退到 Agent 官方 Web Search 工具，并继续遵守上述来源优先级和页面核验要求。

不要用 Exa 代替 Context7 查询库 API 细节；除非官方文档不在 Context7 或用户明确要求网页来源。

## 组合使用

- API 或配置事实按 `find-docs` skill 使用 Context7 CLI。
- 官方公告、产品边界、市场信息、新闻和跨来源对比用 Exa。
- 同一问题用到两个来源时，分别标明来源，不把不同来源混成一个未标注结论。
