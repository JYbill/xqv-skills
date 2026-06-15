# SWC 配置模板

## NestJS `.swcrc` 模板

当前 `rag-server` 项目的目标文件是 `/Users/xiaoqinvar/workspace/project/rag-server/.swcrc`。迁移到其他项目时，写到对应项目根目录的 `.swcrc`。

```json
{
  "$schema": "https://swc.rs/schema.json",
  "jsc": {
    "target": "esnext",
    "baseUrl": ".",
    "externalHelpers": true,
    "parser": {
      "syntax": "typescript",
      "decorators": true,
      "dynamicImport": true
    },
    "transform": {
      "decoratorMetadata": true,
      "legacyDecorator": true
    },
    "keepClassNames": true
  },
  "module": {
    "type": "nodenext"
  },
  "sourceMaps": true,
  "minify": false,
  "exclude": [".*\\.d\\.[cm]?ts$"]
}
```

处理规则：

- 文件名必须是 `.swcrc`，不要写成 `swc.config.*` 或 `.swcrc.json`。
- `decorators`、`legacyDecorator`、`decoratorMetadata` 是 NestJS 依赖注入和装饰器元数据所需配置，不要删除。
- `externalHelpers: true` 需要运行时可用的 `@swc/helpers`。
- `module.type: "nodenext"` 适合 ESM / NodeNext 项目；非 NodeNext 项目要先核对 `tsconfig` 和 `package.json.type`，不要借 SWC 配置整理顺手迁移模块系统。
- `exclude` 排除声明文件，避免 SWC 尝试编译 `.d.ts`、`.d.cts`、`.d.mts`。

## NestJS `nest-cli.json` 片段

只补齐或修正 `builder`，保留项目已有的 `deleteOutDir`、`assets`、`watchAssets`、`typeCheck` 等配置。

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

不要把 `/Users/xiaoqinvar/workspace/project/rag-server/.swcrc` 这类本机绝对路径写入 `nest-cli.json`。Nest CLI 配置用相对路径，目标文件仍然落在项目根目录 `.swcrc`。

## 依赖命令模板

以 pnpm 为例。先读取项目已有依赖，再按缺什么补什么，不要盲目重复安装。

```bash
pnpm add -D @swc/core @swc/cli
```

如果 `.swcrc` 使用 `externalHelpers: true`，服务端运行时通常需要：

```bash
pnpm add @swc/helpers
```

如果项目只在测试转换中使用 SWC，或已有构建工具间接提供 helper，先按项目事实判断依赖分区，并在汇报中说明。

## 验证命令模板

优先运行：

```bash
pnpm typecheck
pnpm build
```

如果本次影响了 Vitest / Vite 的 SWC 转换配置，再运行相关测试文件或 project：

```bash
pnpm exec vitest run path/to/file.spec.ts
pnpm exec vitest run --project test
```

没有对应测试或命令失败时，不要虚报通过；保留关键失败信息并说明是否属于本次 SWC 配置范围。

## 汇报模板

```markdown
已完成 SWC 配置整理。

变更：
- SWC 配置文件已统一为项目根目录 `.swcrc`。
- NestJS 项目的 `nest-cli.json` 已使用 `builder.type: "swc"`，并通过 `swcrcPath: ".swcrc"` 指向配置。
- `.swcrc` 已保留 TypeScript parser、装饰器元数据、NodeNext 模块、source map 和声明文件排除配置。
- `@swc/helpers` 依赖已确认，或说明不需要调整。

验证：
- 已运行 `<实际类型检查命令>`：<结果>。
- 已运行 `<实际构建命令>`：<结果>。
- 已运行 `<实际测试命令或说明未运行>`：<结果>。

注意：
- 当前 `rag-server` 项目的 `.swcrc` 路径是 `/Users/xiaoqinvar/workspace/project/rag-server/.swcrc`。
- 未迁移 NestJS 版本、测试框架、ESM、lint / format 或业务逻辑。
- 保留未处理的既有无关工作区改动。
```
