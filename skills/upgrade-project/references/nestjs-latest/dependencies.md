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
