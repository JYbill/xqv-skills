# NestJS 升级到 latest 模板

## `package.json` 脚本模板

目标脚本：

```json
{
  "scripts": {
    "start": "node --enable-source-maps dist/src/main.js",
    "typecheck": "tsc --noEmit"
  }
}
```

处理规则：

- `start` 必须启用 Node.js 原生 source map。
- `typecheck` 必须精确使用 `tsc --noEmit`。
- 如果原脚本不同，在汇报里说明原值和新值。

## 依赖升级命令模板

以 pnpm 为例。先从 `package.json` 读取项目已有的 NestJS 直接依赖，再按原分区升级，不要盲目复制下面的完整列表。

生产依赖示例：

```bash
pnpm add @nestjs/common@latest @nestjs/core@latest @nestjs/platform-express@latest
```

开发依赖示例：

```bash
pnpm add -D @nestjs/cli@latest @nestjs/schematics@latest @nestjs/testing@latest
```

如果项目使用 npm、yarn 或 bun，按锁文件替换为对应命令，并保持 dependencies / devDependencies 分区。

## 移除依赖命令模板

pnpm：

```bash
pnpm remove source-map-support @types/source-map-support
```

Vitest 项目还需要移除：

```bash
pnpm remove tsconfig-paths
```

npm：

```bash
npm uninstall source-map-support @types/source-map-support
npm uninstall tsconfig-paths
```

yarn：

```bash
yarn remove source-map-support @types/source-map-support
yarn remove tsconfig-paths
```

bun：

```bash
bun remove source-map-support @types/source-map-support
bun remove tsconfig-paths
```

只运行和当前项目事实匹配的命令。没有安装的包不要强行移除；已由其他包传递依赖带入的包不需要从锁文件里手工删除。

## source-map-support 注册代码清理模板

删除这些形式：

```ts
import "source-map-support/register";
```

```ts
import sourceMapSupport from "source-map-support";

sourceMapSupport.install();
```

```ts
require("source-map-support/register");
```

如果周围代码是 CommonJS 或其他写法，按实际语法删除等价注册逻辑，不要改无关启动逻辑。

## tsconfig-paths 搜索模式

Vitest 项目移除 `tsconfig-paths` 前后，检查这些残留：

```text
tsconfig-paths
-tsconfig-paths/register
-r tsconfig-paths/register
require("tsconfig-paths")
require("tsconfig-paths/register")
```

如果残留位于 Jest 配置、`ts-jest` 配置或旧 `test:e2e` Jest 命令中，应随本次清理删除或同步到 Vitest 配置。

如果残留位于非测试启动脚本，例如 `ts-node -r tsconfig-paths/register ...`，先说明这已经超出“Vitest 项目清理 Jest 插件”的默认范围，需要同步处理该脚本后再删除依赖。

## 复杂判断表达模板

当需要解释为什么删除或保留某个依赖时，使用 ASCII 图 + 描述。

```text
发现 tsconfig-paths
        │
        ▼
项目是否是 Vitest？
        │
        ├─ 否：本次不处理
        │
        └─ 是
            │
            ▼
           是否仍有非测试脚本引用？
            │
            ├─ 否：移除依赖
            └─ 是：先同步对应脚本，再移除或说明冲突
```

描述示例：

```markdown
当前项目已经使用 Vitest，`tsconfig-paths` 只在旧 Jest/ts-node 测试链路中出现，所以本次随 NestJS latest 升级移除该直接依赖。未做测试框架迁移，因为项目已经完成 Vitest 切换。
```

## 验证命令模板

优先运行：

```bash
pnpm typecheck
pnpm build
```

如果本次影响了测试配置或测试依赖，再运行相关测试：

```bash
pnpm exec vitest run path/to/file.spec.ts
pnpm exec vitest run --project test
```

没有 Vitest 或没有对应测试时，不要虚报执行。命令失败时保留关键错误输出，并说明是否属于本次 NestJS latest 迁移范围。

## 汇报模板

```markdown
已完成 NestJS latest 升级相关整理。

变更：
- 已将项目现有 `@nestjs/*` 直接依赖升级到 latest，并保持原 dependencies / devDependencies 分区。
- 已移除 `source-map-support` / `@types/source-map-support` 及注册代码。
- `package.json` 的 `start` 已改为 `node --enable-source-maps dist/src/main.js`。
- `package.json` 的 `typecheck` 已设置为 `tsc --noEmit`。
- 当前项目使用 Vitest，已移除 `tsconfig-paths` 直接依赖及相关旧测试链路残留。

验证：
- 已运行 `<实际类型检查命令>`：<结果>。
- 已运行 `<实际构建命令>`：<结果>。
- 已运行 `<实际测试命令或说明未运行>`：<结果>。

注意：
- 未迁移 lint、format、ESM、Docker 或业务逻辑。
- 如有命令失败，说明失败原因和是否属于本次迁移范围。
- 保留未处理的既有无关工作区改动。
```
