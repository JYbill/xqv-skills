# tsconfig.json 模板

CSR React + Vite 项目默认使用一个 `tsconfig.json`。如果目标项目拆分 app/node/test 多个配置，按项目事实裁剪，不要机械复制。

`vite/client` 为浏览器源码提供静态资源导入、`import.meta.env` 和 HMR 的全局类型；`node` 供同一配置下的 `vite.config.ts`、`vitest.config.ts` 使用。Vite 配置文件需要调用的 API 仍在文件中显式导入，不能用这些导入替代 `vite/client`。如果拆分 TypeScript 配置，只在包含浏览器源码的配置中保留 `vite/client`。

```json
{
  "compilerOptions": {
    "tsBuildInfoFile": "./.cache/tsconfig.tsbuildinfo",
    "target": "esnext",
    "lib": ["esnext", "DOM"],
    "module": "esnext",
    "types": ["vite/client", "node"],
    "skipLibCheck": true,

    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "verbatimModuleSyntax": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",

    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "erasableSyntaxOnly": true,
    "noFallthroughCasesInSwitch": true,
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": [
    "src",
    "vite.config.ts",
    "vitest.config.ts",
    "test",
    "oxlint.config.ts",
    "oxfmt.config.ts"
  ]
}
```
