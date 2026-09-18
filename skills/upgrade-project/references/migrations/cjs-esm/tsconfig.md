# tsconfig.json 模板

默认保留目标项目的运行时、编译器版本和构建方式，仅调整兼容的 ESM 选项。下面是已明确采用 Node.js 26 原生运行 TypeScript、TypeScript 7 只做类型检查时的可选示例，不要求其他项目升级到这些版本。仍编译到 `dist/` 的项目应保留输出配置与 `.js` 导入扩展名，不套用 `noEmit`、`allowImportingTsExtensions` 或 `erasableSyntaxOnly`。

对于该原生执行示例，`noEmit` 与 `allowImportingTsExtensions` 配套，因此源码中的相对导入可以显式写 `.ts` 扩展名。

`customConditions`、路径别名和宽松检查项属于具体项目配置，不放进通用模板；迁移时按目标项目事实保留。

```json
{
  "compilerOptions": {
    "rootDir": ".",
    "incremental": true,
    "tsBuildInfoFile": ".cache/.tsbuildinfo",
    "strict": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "target": "ESNext",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "allowImportingTsExtensions": true,
    "noEmit": true,
    "types": ["node"],
    "erasableSyntaxOnly": true,
    "verbatimModuleSyntax": true
  },
  "include": ["./src/**/*.ts", "./test/**/*.ts"],
  "exclude": ["node_modules"]
}
```
