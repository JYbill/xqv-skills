# 运行环境与工具链

- 运行时：Node.js <版本>；Docker 构建使用 <Node.js 基础镜像，如适用>。
- 包管理器：<pnpm / npm / yarn / bun>，以对应锁文件为准，不新增其他包管理器的锁文件。
- 服务框架：NestJS <版本>、TypeScript <版本>、<ESM / CommonJS 模块模式>。
- 编译构建：Nest CLI + <SWC / TypeScript 编译器>，生产入口为 <实际编译产物入口>。
- 数据与基础设施：<Prisma / 数据库 / Redis / 队列等，按项目事实填写>。
- 代码质量工具：<Oxlint / ESLint>、<Oxfmt / Prettier>、<Vitest / Jest>、<提交前检查工具>。

# 常用命令

```bash
# 代码检查 / 格式化
# 编辑代码后，优先只对本次修改的几个文件执行检查。
<包管理器命令> exec <lint 工具> src/path/to/file.ts test/path/to/file.ts --fix

# 编辑代码后，优先只对本次修改的几个文件执行格式化。
<包管理器命令> exec <format 工具> "src/path/to/file.ts" "test/path/to/file.ts"

# 类型检查 / 构建
<包管理器命令> exec tsc --noEmit
<包管理器命令> exec nest build

# 测试
# 编辑代码后，优先只运行本次修改相关的几个测试文件。
<包管理器命令> exec vitest run --project test src/path/to/file.spec.ts src/path/to/file.integration-spec.ts
<包管理器命令> exec vitest run --project e2e test/app.e2e-spec.ts

# Prisma；项目没有使用 Prisma 时删除。
<包管理器命令> prisma:validate
<包管理器命令> prisma:generate
```

需要全量验证时，再运行项目已有的类型检查、构建、代码检查、格式检查、单元测试、e2e 和覆盖率脚本。修改代码检查、格式化或测试工具时，同步维护 lint-staged、Husky、CI 和 Docker 中的实际调用方。

# Schema 校验

- 请求校验默认使用 Zod Schema 和全局 `StandardSchemaValidationPipe`。需要校验的 `@Body()`、`@Query()`、`@Param()`、`@RawBody()` 参数必须显式传入 `schema`。
- Schema 放在对应模块的 `*.schema.ts`；输入和输出类型使用 `z.infer<typeof schema>` 推导，不重复维护 class DTO 或 interface。
- 输入转换使用 `z.coerce.*` 或 `z.preprocess()` 显式表达，不依赖隐式类型转换。
- 默认使用 `z.object()` 剔除未知字段；必须拒绝未知字段时使用 `z.strictObject()`，并覆盖 400 响应测试。
- 环境变量使用 Zod 和 `ConfigModule.forRoot({ validationSchema })` 在启动阶段校验。
- 不新增 `class-validator` DTO、`class-transformer` DTO 或 `@nestjs/mapped-types`。只有接口响应需要运行时裁剪或校验时，才使用 `StandardSchemaSerializerInterceptor` 和 `@SerializeOptions({ schema })`。

# 测试要求

## 通用约束

- 所有测试文件的辅助函数统一放在文件最底部，位于全部测试用例和 `describe` 块之后；不要放在测试代码之前或穿插其中。
- 每个用例和断言都应保护明确的业务规则、调用方依赖的输出、状态变化或错误处理；禁止只验证测试准备数据、复述实现、无意义存在性检查和重复防御逻辑，不为占位代码补空测试。
- 新增、修改或运行测试前，沿用例、生命周期钩子、公共 fixture、setup 和被测代码核对实际连接、请求及副作用，再按所属测试通道判断是否允许；整组测试和覆盖率命令同样适用。无法确认时停止相关测试，改为无外部写入的验证，不能以运行后清理作为安全依据。
- mock 用于隔离协作者，不替代正在验证的行为；模拟增删改前须确认不会透传到真实连接，仍须断言被测行为。开发者指定某个测试使用 mock 后，后续修改保持该风格，除非开发者明确撤销。
- 测试文件及辅助代码应在测试进程内导入并调用被测模块；不得使用 `exec`、`execFile`、`spawn`、`fork` 及其同步版本或其他命令执行工具，另起 Node.js、Shell、CLI 或应用进程执行被测代码。正常通过包管理器、测试运行器运行测试及运行器自身的进程管理不受此限制。
- 按实际验证的行为和依赖协同选择测试类型；使用数据库 mock 的 Service 分支测试仍可属于单元测试，验证真实数据库、Redis、网络、文件系统、队列或框架协同时使用集成测试。
- 明确各测试通道允许的真实外部服务副作用，并与实际测试配置和脚本保持一致；没有配置的 LLM、遥测或 E2E 通道及命令不写成既有能力。
- 对声明为只读的测试通道，限制覆盖 setup、fixture、辅助代码及被测流程：真实数据库和其他真实外部服务只允许无副作用的查询，禁止增删改、DDL、投递任务等操作。隔离实例、事务回滚、随机库名、先造数后删除均不构成例外，不得为覆盖率批量造数。
- 只读通道中的变更逻辑使用进程内 mock、内存数据库或不连接真实服务的驱动替身验证；真实持久化、事务和约束须在项目明确允许写入的测试通道中，使用隔离资源验证。

Vitest 的 `test` project 覆盖 `src/**/*.spec.ts` 和 `src/**/*.integration-spec.ts`，`e2e` project 覆盖 `test/**/*.e2e-spec.ts`。如果项目使用其他测试运行器，按相同测试职责调整实际命令和收集范围。

## `*.spec.ts`

- 单元测试。
- 只测试纯代码逻辑、Schema、工具函数和 Service 分支。
- 不访问真实数据库，不访问外部服务。

## `*.integration-spec.ts`

- 集成测试。
- 允许依赖环境变量访问真实外部服务。
- 真实外部服务默认只读；需要真实写入时，必须由项目明确允许对应测试通道写入，并使用隔离资源。
- 适合测试数据库、Redis、网络请求等。
- 不用 mock 替代正在验证的依赖；只验证本地业务分支时改用单元测试，不以 mock 交互冒充真实集成验证。

## `*.e2e-spec.ts`

- 端到端测试，仅为开发者明确指定需要完整链路验证的模块编写。
- 通过 HTTP 接口测试完整链路。
- 使用专门的测试数据库或测试 schema。
- 每轮测试前准备 seed 数据，测试后清理或重建。
- 可以测试 CRUD，但重点是关键业务流程，而不是所有 CRUD 细节。
- 运行前核对实际目标环境；在隔离资源中允许链路所需的真实读写、认证副作用及测试数据准备与清理，不用 mock 替代核心依赖。
- e2e 测试文件专门放在 `test/` 目录内。

如果当前项目还没有可复用的 e2e seed 基础设施，不要新增会污染共享环境的 e2e 用例；新增模块是否必须同时补单元测试和集成测试，按项目真实约定写清楚。

# 标准文档

`docs/spec/` 用于存放项目标准文档。新增或调整标准文档时，需要同步维护 `docs/spec/index.md`。如果当前项目还没有该目录，第一次新增标准文档时一并创建目录和索引。

# 整体架构

```text
<project>/
├── docs/                 # 项目文档与标准文档；没有文档时可以不存在
├── env/                  # 环境变量配置文件；没有时删除
├── prisma/               # Prisma 数据模型与迁移；没有时删除
├── src/                  # 应用源码
│   ├── app.d.ts          # 项目全局类型声明
│   ├── main.ts           # 应用启动入口
│   ├── config/           # 配置装配
│   ├── exception/        # 全局异常过滤与异常响应
│   ├── library/          # 数据库、锁、ID 等基础设施封装
│   ├── middleware/       # Nest/Express 中间件
│   ├── modules/          # 业务模块；项目按模块组织时保留
│   └── util/             # 通用工具函数
├── test/                 # e2e 测试
└── package.json          # 脚本、依赖与包管理器声明
```

# 类型声明

- 全局声明统一放在 `src/app.d.ts`，包括 Express、Nest 或第三方库的 module augmentation；不要新增根目录 `types/` 或其他重复的集中类型目录。
- 手写的 `type` / `interface` 等类型声明与 `.ts` 逻辑分开，放在对应源码同级同名的 `.d.ts` 中，例如 `auth.service.ts` 对应 `auth.service.d.ts`。
- 跨多个源码文件复用、但不属于全局声明的类型，优先放在对应业务模块或基础设施目录内，并用正常 ESM 导入导出，不要挂到 global。
- 不使用 `*.types.d.ts` 这类额外命名；类型文件名直接跟随对应源码文件名。
- 只作为类型使用的导入使用 `import type` 或内联 `type`；ESM 项目的相对导入保留运行时后缀。

# 反模式

后续修改代码时保持下面的组织方式，避免把不同职责混在同一处：

- 查询操作优先放在 `*-query.ts`。
- 新增、更新、删除操作优先放在 `*-modify.ts`。
- 项目已有统一响应工具时，接口返回优先使用统一结构，不在各处手写不一致的返回格式。
- Controller 只处理路由、参数解析、鉴权装饰器和响应入口，不写业务流程。
- Service 承载业务逻辑、事务编排和外部依赖调用，不直接把数据库错误原样暴露给客户端。
- 状态值、类型值、任务值和开关值不要散落魔法字符串或魔法数字，先抽到合适的枚举或业务模块。
- 不使用 `any`、`unknown`、`as any`、`as unknown as ...` 规避 TypeScript 类型问题。
- ESM 项目的相对导入写运行时后缀；只作为类型使用的导入必须使用 `import type` 或内联 `type`。
- 配置通过 `@nestjs/config` 和项目环境文件集中管理，不在业务代码中散落读取 `process.env`。
- 不提交密钥、token、数据库连接串、个人环境配置或会污染共享环境的测试数据。
