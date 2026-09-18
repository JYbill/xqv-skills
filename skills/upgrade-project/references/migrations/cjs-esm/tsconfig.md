# tsconfig.json 模板

按项目已有运行方式和当前 TypeScript 版本，只调整 ESM 相关选项。以下是 Node.js 模块解析的合并示例，不是完整配置；使用前确认本地编译器支持这些选项。不适用于直接覆盖打包器专用配置。

```json
{
  "compilerOptions": {
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "verbatimModuleSyntax": true
  }
}
```

保留现有 `target`、`rootDir`、`outDir`、`include`、`exclude`、路径别名和检查严格程度，不调整构建产物与入口。

不因 ESM 迁移增加 `noEmit`、`allowImportingTsExtensions` 或 `erasableSyntaxOnly`，也不要求切换到 Node.js 原生执行 TypeScript。相对导入扩展名按实际运行模块选择：编译后运行 JavaScript 时通常使用 `.js`；已有源码执行方式按其现有规则保留。

当前编译器不支持所需选项时，记录兼容性问题并确定适用配置，不在本参考内自动升级工具链。
