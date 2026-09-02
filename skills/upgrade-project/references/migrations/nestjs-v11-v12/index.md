# NestJS v11 升级到 v12

## 适用范围

从 NestJS 11 升级到 12 时，由 `../nestjs-latest/index.md` 路由到这里。先完成该入口规定的全局 `ValidationPipe` 盘点和用户确认；Standard Schema + Zod 是可选迁移，不是升级到 v12 的强制条件。

通用的全部直接依赖升级读取 `../../workflows/dependencies-latest/index.md`。ESM、SWC、Vitest、Oxlint 和 Oxfmt 仍读取各自已有专题，不在本目录重复维护。

## 执行顺序

1. 查阅 NestJS v12 官方迁移指南，确认 Node.js、ESM、HTTP adapter 和项目所用扩展包的兼容要求。
2. 按 `dependencies.md` 升级 NestJS 包并解决真实 peer dependency 冲突，不使用 `--force`。
3. 搜索废弃 API、旧导入路径和框架行为变化，按项目事实修改。
4. 用户确认迁移校验体系后，按 `standard-schema.md` 同步请求、环境变量、响应和测试；选择保留时维持 `ValidationPipe` 与 class DTO。
5. 按 `commands.md` 运行依赖、类型、构建、测试和锁文件验证。

## 官方依据

- [NestJS migration guide](https://docs.nestjs.com/migration-guide)
- [NestJS validation](https://docs.nestjs.com/techniques/validation)
- [NestJS configuration](https://docs.nestjs.com/techniques/configuration)
- [Zod API](https://zod.dev/api)
