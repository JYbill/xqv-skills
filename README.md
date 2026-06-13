# xqv-skills

这是一个 skills 收集仓库。`skills/opencode/` 目录存放 opencode + oh-my-opencode 专属 skill，其余目录为通用 skill。

## skill 总览

### claude-init

用于创建、迁移、清理仓库级 `CLAUDE.md`。适合把 Cursor、Copilot、`AGENTS.md` 一类协作说明收敛成 Claude Code 可直接执行的高信号规则。

### ddt-packaging

用于识别和纠正过度封装。适合用户指出代码拆得太碎、helper 太薄、类型拆分过度、主流程阅读路径过长时，帮助内联单一调用方的小函数，合并没有独立复用价值的薄类型。

### node

用于 Node.js 日常开发实践。覆盖原生 TypeScript type stripping、异步模式、模块系统、测试、性能、缓存、日志、环境变量管理和优雅退出等通用场景。

### nodejs-core

用于 Node.js 底层问题排查。适合处理 V8、libuv、N-API、`node-gyp`、C++ addon、原生崩溃、内存泄漏和引擎级性能分析。

### search

用于按问题场景使用 GitHub MCP、Context7 MCP、Exa WebSearch MCP 搜索并回答。适合用户要求联网检索、查 GitHub 项目和源码、核对框架或 SDK 文档、查 API 用法，以及查官网、博客、产品信息、新闻和对比资料时使用。

使用原则：GitHub 仓库内的源码、README、issue、PR、commit、release、workflow 等事实优先走 GitHub MCP；库、框架、SDK、API 参数、配置项、迁移说明和最佳实践优先走 Context7 MCP；全网资料、官网页面、博客、新闻和产品对比优先走 Exa WebSearch MCP。一个问题同时涉及多种来源时可以组合使用，但回答里必须标明来源。

补充约束：这个 skill 禁止用 Bash、subagent、Agent、Glob、Grep、Read 一类常规工具替代外部搜索；只有用户明确要求处理本地文件，或提供了本地输入文件时，才读取本地文件。查不到的信息必须直接说明未查到，不能猜。

### typescript-magician

用于 TypeScript 类型问题处理。适合修复编译错误、消除 `any`、编写泛型、条件类型、类型守卫，以及提升类型推导和 IntelliSense 质量。

### upgrade-project

用于项目升级、工具链现代化和迁移。适合把旧 JavaScript/TypeScript 工具迁移到新工具，例如 Prettier 到 Oxfmt、ESLint 到 Oxlint、Jest 到 Vitest、CJS 到 ESM、旧 Node 版本到新 Node 版本。

使用原则：先确认源技术、目标技术和本次范围，再检查脚本、依赖、锁文件、配置、lint-staged 和未提交改动；已有引用资料时先读取对应 `references/<迁移名>/index.md`，再做最小必要改动，并使用项目已有命令验证结果。

补充约束：保持迁移差异窄，不把格式化、lint、测试框架、模块系统、CI、业务代码等非本次范围改动混进同一次迁移；命令、包名或计划和项目事实不匹配时，必须说明偏差，不能临时编造绕法。

## opencode skill

### github

用于 GitHub 只读检索。适合查询仓库文件、提交记录、release、issue、label 等内容。

使用前提：需要准备 GitHub PAT，并设置为 `GITHUB_PAT_TOKEN` 环境变量。

补充约束：当回答基于 GitHub 源码内容时，默认给源码链接即可，除非用户明确要求，否则不直接贴大段代码。

### codebase

用于本地代码库语义搜索。基于 Milvus 混合检索能力提升本地代码查询效率，适合在本地仓库中按自然语言检索实现、定位上下文。

使用前提：需要准备环境变量。

环境变量来源于：[claude-context mcp](https://github.com/zilliztech/claude-context/blob/master/docs/getting-started/environment-variables.md#-required-environment-variables)

将 `codebase/.env` 中对应配置放入 `~/.context/` 目录即可。

```bash
# embedding 提供商接口格式，默认为 OpenAI 接口格式
EMBEDDING_PROVIDER
# OpenAI 地址，一般是私有化地址
CODEBASE_OPENAI_BASE_URL
# OpenAI 密钥
CODEBASE_OPENAI_API_KEY
# embedding 模型名称
CODEBASE_EMBEDDING_MODEL
# milvus 向量数据库地址
CODEBASE_MILVUS_ADDRESS
# embedding 过程忽略的文件表达式
CUSTOM_IGNORE_PATTERNS
```

补充约束：`index_codebase` 和 `clear_index` 都需要先征得用户同意，尤其是仓库还没做 embedding 时，不能直接发起全库索引。

### context7

用于查询最新技术文档和库文档。适合 node.js、nx、nest.js、express、koa、react、vue、go、python、rust、c++ 等技术栈的最新资料检索。

常见用法：先通过 `resolve-library-id` 解析库 ID，再用 `query-docs` 根据具体问题拉取文档内容。

### web-search

用于非 GitHub 场景的网络搜索和代码搜索。适合查网页资料、编程示例、公司信息，以及通过 Grep 类能力搜索公开代码片段。

常见能力包括 `web_search_exa`、`get_code_context_exa`、`company_research_exa` 和公开代码搜索。
