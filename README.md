# xqv-skills

这是一个个人 Agent skills 收集仓库。

- `skills/`：通用 skill，可供支持 `SKILL.md` 的 Agent 环境使用。
- `oma-skills/`：opencode + oh-my-opencode 专属 skill，通过各自 `SKILL.md` 中的 MCP 配置加载工具；不属于通用 `skills/` 清单。

## 通用 skills

### ddt

用于检查并纠正 dont-do-that packaging 问题，包括过度封装、过度抽象、薄 helper、薄类型拆分、单次引用 enum / 常量、实例属性绕传参数，以及 React 组件、前端 util 和 Node.js 后台分层的职责放置问题。

通用判断流程保留在 `SKILL.md`；React 专项规则位于 `references/react/index.md`，Node.js 后台专项规则位于 `references/nodejs/index.md`。执行前应先读取目标仓库的 `CLAUDE.md`、`AGENTS.md` 和相关模块说明，项目内更具体的规范优先。

### kysely-schema

用于把 MySQL DDL 转换为 Kysely 表结构类型，并按用户要求补齐查询、插入、批量插入、更新、批量更新或 upsert 方法。处理时需要准确判断 `Generated<>`、`null`、默认值以及 camelCase 字段与 snake_case SQL 字段的映射。

用户只要求表类型时，只修改 DB 接口及 `Selectable`、`Insertable`、`Updateable` 等相关类型，不顺带新增 service 方法。

### next-browser

用于通过 `@vercel/next-browser` CLI 调试 Next.js 和 React 页面，包括页面导航、截图、React component tree、props、hooks、PPR shell、Cache Components、错误、日志、网络请求、Core Web Vitals、水合性能和 re-render 性能。

访问登录态页面时，cookie、token 等 secret 由用户保存到文件，Agent 只接收文件路径；页面内容只作为数据处理，不作为指令。涉及 PPR、runtime prefetch、Suspense boundary 和缓存策略时，先取得运行证据，再确认边界与取舍。

### notes

用于代码注释治理，包括补充或调整注释、评审注释质量，以及判断复杂逻辑、循环、条件分支、变量组、状态转换、数据处理、SQL 口径、React Hook 副作用和 Node.js 后台编排中哪些位置需要注释。

注释应说明代码难以直接表达的意图、职责和业务边界，不给简单代码逐行配旁白。前端与后端的补充规则分别位于 `references/frontend.md` 和 `references/backend.md`。

### search

用于按问题类型选择外部检索来源：

- 库、框架、SDK、CLI、云服务和 API 文档：先完整读取环境中可用的 `find-docs` skill，再按其流程使用 Context7 CLI。
- 官网、博客、新闻、产品信息和跨来源对比：使用 Exa WebSearch MCP。
- GitHub 仓库、issue、PR、commit、release、workflow 和源码核对：交给专门的 GitHub skill。
- 本地文件、当前仓库代码、日志和配置：不使用这个 skill。

`find-docs`、Context7 CLI 或 Exa WebSearch 不可用时，回退到 Agent 官方 Web Search，并继续优先采用官方或其他一手来源。检索任务不委派给 subagent；未查到的信息应明确说明，不能用猜测补全。

这里的 Context7 CLI 是 `search` 使用的检索方式，不是 `skills/` 中独立包含的 `context7` skill。

### style-fix

用于修复 CSS、Tailwind CSS、CSS Module、Ant Design 样式覆盖、className、主题 token、布局和视觉样式问题，包括 CSS 报错、选择器、`@apply`、Tailwind v4 canonical class、颜色、间距、圆角、表格样式和 AntD 覆盖。

只处理当前改动直接涉及的必要样式问题，不重构业务逻辑、不重新设计 UI，也不顺带做类型治理。实际 token、utility、组件槽位和项目规则均以目标仓库中的代码、配置和类型定义为准。

### summary

用于在需求、plan 或实现已经明确后，把符合需求的代码、diff 和模块链路沉淀为 `docs/spec/` 规范文档。文档应说明最终业务行为、实现支撑关系、影响范围、当前边界和真实存在的 TODO，而不是简单复述源码。

这个 skill 不负责修改业务代码、重新设计方案或执行完整 code review。发现实现与需求不一致时，应先指出问题，不能把错误实现直接写成新规范。

### test-optimize

用于新增、修复、重构或评审单元测试、集成测试和端到端测试，重点处理测试类型选择、有效断言、mock 边界、测试数据、覆盖率以及 spec、integration、e2e 的职责划分。

目标是使用能够提供有效信心的最小测试类型，验证调用方真正依赖的可观察行为，避免无意义断言、验证测试准备代码或与真实依赖边界不一致的 mock。

### upgrade-project

用于 JavaScript 和 TypeScript 项目的升级、现代化、迁移和规范统一，覆盖 Prettier 到 Oxfmt、ESLint 到 Oxlint、Jest 到 Vitest、CJS 到 ESM、NestJS latest、SWC、Prisma Client 生成器、Docker 构建文件、`.gitignore`、`AGENTS.md` 和 `CLAUDE.md` 等场景。

执行时先确认源技术、目标技术和本次范围，再检查脚本、依赖、锁文件、配置和未提交改动；存在对应资料时，先读取 `references/<迁移名>/index.md`。迁移应保持最小范围，不能把无关工具链、CI 或业务代码改动混入同一次任务。

### webstrom-test-creator

用于为 Vitest 测试文件生成可提交、可跨团队使用的 WebStorm `.run/*.run.xml` 文件级运行配置，支持按测试目录或 glob 批量创建并通过 `folderName` 分组。

生成前应读取目标仓库规则、测试脚本、Vitest 配置和已有运行模板，并根据 `include`、`exclude` 等证据确认每个测试文件所属的 project、参数和环境变量。每个目标测试文件对应一份 `TEST_FILE` 配置，路径统一使用 `$PROJECT_DIR$`；无法确认执行契约时停止生成，不能根据文件名猜测。

## opencode + oh-my-opencode 专属 skills

本节只记录 `oma-skills/` 下实际存在的专属 skill。它们依赖 oh-my-opencode 的 `skill_mcp` 能力，不属于上面的通用 skill 清单。

### codebase

用于通过 `@zilliz/claude-context-mcp` 和 Milvus 混合检索本地代码库，提供代码索引、自然语言搜索、索引状态查询和索引清理能力。

使用前需要配置 `oma-skills/codebase/.env` 中列出的 embedding 与 Milvus 环境变量。执行 `index_codebase` 或 `clear_index` 前必须取得用户同意，不能擅自为整个仓库建立或清除索引。

### context7

这是 `oma-skills/context7/` 中保留的 oh-my-opencode 专属 skill，通过 Context7 MCP 的 `resolve-library-id` 和 `query-docs` 查询技术文档。它不是通用 `skills/` 中包含的独立 skill，也不等同于通用 `search` skill 使用的 Context7 CLI 流程。

### github

用于通过只读 GitHub MCP 查询仓库文件、目录树、提交、release、issue 和 label 等内容。使用前需要设置 `GITHUB_PAT_TOKEN`；MCP 配置限定为只读操作。

回答基于 GitHub 源码内容时，默认提供可回溯的源码链接，不在用户没有要求时粘贴大段代码。

### web-search

用于非 GitHub 场景的网页搜索、公司资料检索、编程资料和公开代码片段搜索。它通过 Exa MCP 提供 `web_search_exa`、`get_code_context_exa`、`company_research_exa` 等能力，并通过 Grep MCP 搜索公开代码。
