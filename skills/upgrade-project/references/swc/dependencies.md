以 pnpm 为例。先读取项目已有依赖，再按缺什么补什么，不要盲目重复安装。

```bash
pnpm add -D @swc/core @swc/cli
```

如果 `.swcrc` 使用 `externalHelpers: true`，服务端运行时通常需要：

```bash
pnpm add @swc/helpers
```

如果项目只在测试转换中使用 SWC，或已有构建工具间接提供 helper，先按项目事实判断依赖分区，并在汇报中说明。
