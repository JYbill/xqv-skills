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
