# SWC 配置参考

## 适用场景

当用户要求整理、改造或新增 TypeScript / NestJS 项目的 SWC 配置时，使用这份参考。

常见触发信号：

- 用户提到 `swc`、`.swcrc`、`@swc/core`、`@swc/cli`、`@swc/helpers`、`unplugin-swc`。
- NestJS 项目中出现 `compilerOptions.builder.type: "swc"`、`swcrcPath`、`nest build` 使用 SWC 编译。
- 用户要求把 SWC 配置文件改名、统一命名或沉淀为可复用配置。

这份参考默认只处理 SWC 配置文件、Nest CLI 的 SWC builder 配置，以及与 `externalHelpers` 直接相关的 SWC 依赖。不顺手升级 NestJS、迁移测试框架、迁移 ESM、改 lint / format 或重写业务代码。

## 命名和落地位置

SWC 配置文件统一命名为项目根目录的 `.swcrc`。

- 当前 `rag-server` NestJS 项目的目标路径是 `/Users/xiaoqinvar/workspace/project/rag-server/.swcrc`。
- 迁移到其他项目时，把路径替换为对应项目的 `<project-root>/.swcrc`。
- 不要新增 `swc.config.*`、`.swcrc.json`、`swc.json` 等替代命名；如果项目已有这些文件，先读取并迁移到 `.swcrc`，再删除或停用旧入口。
- NestJS 的 `nest-cli.json` 中使用相对路径 `swcrcPath: ".swcrc"`，避免把本机绝对路径写进可复用配置。

## 默认迁移边界

默认要做：

- 检查 `package.json`、锁文件、`.swcrc` / 旧 SWC 配置、`nest-cli.json`、`tsconfig*.json`。
- 将 SWC 配置落到项目根目录 `.swcrc`。
- NestJS 项目使用 `compilerOptions.builder.type: "swc"`，并设置 `options.swcrcPath: ".swcrc"`。
- 如果 `.swcrc` 启用了 `jsc.externalHelpers: true`，确认项目有 `@swc/helpers` 运行时依赖。
- 运行 `typecheck`、`build` 或项目已有的最小验证命令。

默认不要做：

- 不把 NestJS latest 升级混入 SWC 配置整理；NestJS 升级读取 `references/nestjs-latest/index.md`。
- 不把 Jest 到 Vitest、CJS 到 ESM、ESLint 到 Oxlint、Prettier 到 Oxfmt 混入本次改动。
- 不为了通过编译修改业务逻辑或用 `any`、`unknown`、类型断言掩盖类型问题。

## 推荐执行流程

以 pnpm 项目为例，其他包管理器按锁文件替换命令。

```text
读取 package.json / 锁文件 / nest-cli.json / tsconfig / SWC 配置
        │
        ▼
确认是否为 NestJS 项目，以及是否使用 SWC builder
        │
        ▼
是否已有非标准 SWC 配置文件名？
        │
        ├─ 是：迁移内容到项目根目录 `.swcrc`，并停用旧入口
        └─ 否：创建或更新项目根目录 `.swcrc`
        │
        ▼
写入 NestJS 适用的 SWC 配置
        │
        ▼
NestJS 项目同步 `nest-cli.json` 的 `swcrcPath: ".swcrc"`
        │
        ▼
检查 `externalHelpers` 对应依赖
        │
        ▼
运行 typecheck / build / 必要测试
```

具体步骤：

1. 检查当前项目状态：
   - `package.json` 的 `dependencies` / `devDependencies` 中是否有 `@swc/core`、`@swc/cli`、`@swc/helpers`、`unplugin-swc`。
   - 根目录是否已有 `.swcrc`、`swc.config.*`、`.swcrc.json` 或其他 SWC 配置。
   - NestJS 项目读取 `nest-cli.json` 的 `compilerOptions.builder`。
   - 读取 `tsconfig.json` / `tsconfig.build.json` 的 `module`、`target`、`experimentalDecorators`、`emitDecoratorMetadata` 等语义。
   - 当前工作区是否已有未提交改动。
2. 将 SWC 配置文件统一为项目根目录 `.swcrc`。当前 `rag-server` 项目落地到 `/Users/xiaoqinvar/workspace/project/rag-server/.swcrc`。
3. 使用同目录 `template.md` 中的 NestJS `.swcrc` 模板。它包含 TypeScript parser、装饰器元数据、NodeNext 模块、source map、排除声明文件等设置。
4. NestJS 项目更新 `nest-cli.json`，保留原有 `deleteOutDir`、`assets`、`watchAssets`、`typeCheck` 等配置，只补齐或修正 SWC builder：
   ```json
   {
     "compilerOptions": {
       "builder": {
         "type": "swc",
         "options": {
           "swcrcPath": ".swcrc"
         }
       }
     }
   }
   ```
5. 如果 `.swcrc` 使用 `"externalHelpers": true`，确认 `@swc/helpers` 在运行时可用。服务端项目通常放在 `dependencies`；如果只用于测试或构建，先按项目事实判断，不要盲目移动依赖分区。
6. 运行验证命令，优先：
   ```bash
   pnpm typecheck
   pnpm build
   ```
   如果本次影响了测试转换配置，再运行相关测试。

## NestJS 配置说明

NestJS 依赖装饰器和元数据完成依赖注入，因此 `.swcrc` 必须保留：

- `parser.syntax: "typescript"`；
- `parser.decorators: true`；
- `transform.legacyDecorator: true`；
- `transform.decoratorMetadata: true`。

`module.type: "nodenext"` 适合当前 ESM / NodeNext 风格的 NestJS 项目。迁移到非 NodeNext 项目时，先读取 `tsconfig` 和 `package.json.type`；如果项目仍是 CommonJS，不要因为套用模板顺手做 ESM 迁移。

## 验收标准

迁移完成后至少确认：

- SWC 配置文件位于项目根目录，文件名是 `.swcrc`。
- 当前 `rag-server` 项目对应路径为 `/Users/xiaoqinvar/workspace/project/rag-server/.swcrc`。
- NestJS 项目的 `nest-cli.json` 使用 SWC builder，并通过 `swcrcPath: ".swcrc"` 指向配置。
- `.swcrc` 保留 NestJS 所需的 TypeScript 装饰器和元数据设置。
- 如果使用 `externalHelpers`，`@swc/helpers` 的依赖分区符合项目运行方式。
- 已运行 `typecheck`、`build` 或说明跳过 / 失败原因。
- 未混入 NestJS 版本升级、测试框架迁移、ESM 迁移、lint / format 迁移或业务逻辑改动。

## 模板文件

`.swcrc`、`nest-cli.json` 片段、依赖命令和汇报模板见同目录 `template.md`。
