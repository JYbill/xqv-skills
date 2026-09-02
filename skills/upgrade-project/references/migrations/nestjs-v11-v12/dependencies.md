# v11 到 v12 依赖处理

- 将项目已有的 `@nestjs/common`、`@nestjs/core`、HTTP platform、`@nestjs/config`、`@nestjs/testing`、CLI 和 schematics 升到相互兼容的 v12 稳定版本，保持原有 dependencies / devDependencies 分区。
- NestJS 12 核心包是 ESM-only。升级前确认项目运行时和构建产物支持 ESM；若项目仍是 CommonJS，先把它列为独立迁移风险，不在依赖报错后临时混改模块系统。
- 检查 Redis、CLS、Prisma、Swagger 等 Nest 扩展包的 peer 范围。只有确认包没有消费者时才移除；存在消费者时应升级、替换或适配。
- TypeScript 主版本必须通过 Nest CLI 的真实 build 验证；最新稳定版若未暴露 CLI 所需的编程式编译 API，应保留 Nest CLI 明确支持的最新稳定主版本并报告原因。
- 只有用户确认迁移 Standard Schema + Zod 后，才新增 Zod，并在无引用后移除 `class-validator`、`class-transformer`、`@nestjs/mapped-types`。
- 预发布版不算默认目标。Prisma CLI、Client 和 adapter 等成组包必须保持同一稳定版本。
- 升级全部直接依赖的命令、稳定版本和锁文件规则由 `../../workflows/dependencies-latest/index.md` 维护。
