# v11 到 v12 验证命令

按项目实际脚本取舍，不虚报没有执行的检查。pnpm 项目至少检查：

```bash
pnpm install --frozen-lockfile
pnpm peers check
pnpm typecheck
pnpm build
pnpm test
pnpm test:e2e
```

涉及 Prisma 时追加项目已有的 validate / generate 命令；涉及格式、lint 和 Docker 时执行项目约定的完整命令。最后搜索旧校验体系残留：

```bash
rg "class-validator|class-transformer|@nestjs/mapped-types|ValidationPipe|plainToInstance|validateSync" src test
```

若选择 Standard Schema，确认所有原本需要校验的 Controller 参数都带 schema metadata，并单独验证环境变量缺失时启动失败和响应 serializer 行为。
