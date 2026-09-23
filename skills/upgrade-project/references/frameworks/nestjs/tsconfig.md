```json
{
  "compilerOptions": {
    "tsBuildInfoFile": ".cache/.tsbuildinfo",
    "module": "NodeNext",
    "declaration": true,
    "removeComments": false,
    "emitDecoratorMetadata": true,
    "experimentalDecorators": true,
    "allowSyntheticDefaultImports": true,
    "target": "ESNext",
    "lib": ["ESNext"],
    "sourceMap": true,
    "outDir": "./dist",
    "noEmit": true,
    "types": ["node"],
    "incremental": true,
    "skipLibCheck": true,
    "strict": true,
    "strictNullChecks": true,
    "verbatimModuleSyntax": true,
    "paths": {
      "@/*": ["./src/*"],
      "@test/*": ["./test/*"]
    },
    "isolatedModules": true,
    "esModuleInterop": true
  },
  "include": ["src/**/*", "test/**/*", "prisma.config.ts"]
}
```

Node.js 服务端显式指定 `lib: ["ESNext"]`，避免 TypeScript 默认加载 DOM 类型。仅设置 `types: ["node"]` 不会排除 DOM；目标 Node.js 版本提供全局 `WebSocket` 时，其类型由对应版本的 `@types/node` 声明提供。包含浏览器代码的项目应分别配置浏览器和服务端的 TypeScript 项目。
