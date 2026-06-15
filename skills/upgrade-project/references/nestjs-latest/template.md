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

## `x86-debian.Dockerfile` 模板

当用户明确要求 NestJS latest 同步 Dockerfile 模板时，以当前项目的 `x86-debian.Dockerfile` 为模板内容：

```dockerfile
FROM --platform=linux/amd64 node:24.15.0-slim AS base
WORKDIR /app
RUN echo "deb http://mirrors.aliyun.com/debian/ bookworm main" > /etc/apt/sources.list && \
   echo "deb http://mirrors.aliyun.com/debian/ bookworm-updates main" >> /etc/apt/sources.list && \
   echo "deb http://mirrors.aliyun.com/debian-security/ bookworm-security main" >> /etc/apt/sources.list && \
   rm -rf /etc/apt/sources.list.d/*
RUN apt-get update && apt-get install -y openssl build-essential python3 && apt-get clean && apt-get autoclean && apt-get autoremove -y && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*
RUN npm i -g pnpm && npm cache clean -f

FROM base AS install
COPY package.json .
RUN npm pkg delete scripts.prepare
COPY .npmrc .
COPY patches patches
COPY pnpm-lock.yaml .
COPY pnpm-workspace.yaml .
COPY vendor vendor
RUN pnpm install --frozen-lockfile && pnpm store prune
COPY prisma.config.ts .
COPY env env
COPY prisma prisma
RUN pnpm prisma:generate
COPY . .

FROM install AS format
RUN pnpm format

FROM install AS lint
RUN pnpm lint

FROM install AS test
RUN pnpm test

FROM scratch AS coverage-report
COPY --from=test /app/coverage/ /

FROM install AS build
RUN pnpm build

FROM --platform=linux/amd64 node:24.15.0-slim AS production
WORKDIR /app
RUN echo "deb http://mirrors.aliyun.com/debian/ bookworm main" > /etc/apt/sources.list && \
   echo "deb http://mirrors.aliyun.com/debian/ bookworm-updates main" >> /etc/apt/sources.list && \
   echo "deb http://mirrors.aliyun.com/debian-security/ bookworm-security main" >> /etc/apt/sources.list && \
   rm -rf /etc/apt/sources.list.d/*
RUN apt-get update && apt-get install -y openssl build-essential python3 bash vim curl ffmpeg && apt-get clean && apt-get autoclean && apt-get autoremove -y && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*
ENV NODE_ENV=production
RUN npm install -g pm2 pnpm && npm cache clean -f
RUN pm2 install pm2-logrotate && pm2 set pm2-logrotate:max_size 200M && pm2 set pm2-logrotate:retain 7
COPY --from=build /app/package.json .
RUN npm pkg delete scripts.prepare
COPY --from=build /app/.npmrc .
COPY --from=build /app/pnpm-lock.yaml .
COPY --from=build /app/patches patches
COPY --from=build /app/pnpm-workspace.yaml .
COPY --from=build /app/vendor vendor
RUN pnpm install --prod --frozen-lockfile && pnpm store prune
COPY --from=build /app/pm2.config.js .
COPY --from=build /app/dist dist

EXPOSE 3000
CMD ["pm2-runtime", "pm2.config.js"]
```

处理规则：

- 模板文件名使用 `x86-debian.Dockerfile`。
- `RUN npm pkg delete scripts.prepare` 保留，用于避免容器内安装依赖时触发本地 prepare 钩子。
- `format`、`lint`、`test`、`coverage-report`、`build`、`production` 阶段按模板保留；删除某个阶段前先确认用户要求和项目事实。
- 如果项目没有 `patches`、`vendor`、`prisma.config.ts`、`env`、`prisma` 或 `pm2.config.js`，迁移到其他项目时按真实目录调整，并在汇报中说明偏差。
- Docker 构建入口、镜像 tag、registry 推送仍读取 `references/docker-build/index.md`。

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
- 如用户要求同步 Dockerfile，`x86-debian.Dockerfile` 已按模板更新；如未要求，说明未处理 Dockerfile。

验证：
- 已运行 `<实际类型检查命令>`：<结果>。
- 已运行 `<实际构建命令>`：<结果>。
- 已运行 `<实际测试命令或说明未运行>`：<结果>。

注意：
- 未迁移 lint、format、ESM 或业务逻辑；Dockerfile 只在用户明确要求时按 `x86-debian.Dockerfile` 模板同步。
- 如有命令失败，说明失败原因和是否属于本次迁移范围。
- 保留未处理的既有无关工作区改动。
```
