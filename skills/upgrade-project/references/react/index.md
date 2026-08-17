# CSR React 基础工程参考

## 适用场景

当用户要求初始化、统一或迁移 CSR React 基础工程时，使用这份参考。

常见触发信号：

- React CSR、Vite React、React 单页应用、前端基础工程；
- `tsconfig.json`、`vite.config.ts`、`vitest.config.ts`、`oxlint.config.ts`、`oxfmt.config.ts`；
- `vitest.setup.ts`、`lint-staged.config.js`、Vitest、Oxlint、Oxfmt、Tailwind CSS、tsgo。

这份参考只覆盖 CSR React 项目的基础工具链和基础 Vitest 测试环境，不包含业务打包模式、组件实现、路由、状态管理、接口封装、部署流程或复杂测试分层。Jest 到 Vitest 的迁移仍使用 `references/jest-vitest/index.md`。

## 模板文件

- `package.md`：`package.json` 基础脚本和直接依赖模板。
- `tsconfig.md`：React CSR + Vite + tsgo 类型检查模板。
- `vite-config.md`：`vite.config.ts` 的 Vite React + Tailwind CSS + `@` alias 模板。
- `vitest-config.md`：`vitest.config.ts` 的 React + jsdom 测试配置模板。
- `vitest-setup.md`：`test/setup/vitest.setup.ts` 的 Testing Library matcher 初始化模板。
- `oxlint-config.md`：`oxlint.config.ts` 的 React + TypeScript + import 规则模板。
- `oxfmt-config.md`：`oxfmt.config.ts` 的格式化配置模板。
- `lint-staged.md`：`lint-staged.config.js` 的提交前 Oxlint/Oxfmt 配置模板。
- `dependencies.md`：依赖分组和安装命令。

## 抽取原则

1. **屏蔽业务属性。** 不保留原项目名、版本常量、库模式打包入口、库名、文件名前缀、全局业务变量或私有脚本。
2. **只保留基础工程链路。** 保留 React、Vite、Vitest、Testing Library、Tailwind CSS、TypeScript、tsgo、Oxlint、Oxfmt、lint-staged、Husky 相关内容。
3. **按目标项目裁剪。** 如果目标项目不用 Vitest、Testing Library、Tailwind CSS、Husky 或路径别名，移除对应依赖、插件、脚本和配置，不要留下空配置。
4. **包名必须替换。** `package.json` 中的 `name` 是占位值，落地到项目时必须替换成目标项目自己的包名。
5. **不要复制业务构建。** 默认使用 Vite 应用构建，不复制 `build.lib`、`formats`、`fileName`、`cssFileName`、业务入口文件或业务全局变量。

## 推荐执行流程

```text
确认目标是 CSR React 项目
        │
        ▼
检查包管理器、React/Vite/Vitest/Tailwind/TypeScript 现状
        │
        ▼
读取 package.md、dependencies.md、vitest-config.md 和 vitest-setup.md
        │
        ▼
按目标项目替换包名、依赖版本和脚本
        │
        ▼
同步 tsconfig、vite、vitest、测试 setup、oxlint、oxfmt、lint-staged 配置
        │
        ▼
运行安装命令更新锁文件
        │
        ▼
运行 pnpm typecheck、pnpm test、pnpm lint、pnpm format --check 或项目等价命令
```

## 验收标准

- `package.json` 不包含来源项目的业务包名、技能同步脚本、库打包字段或业务常量。
- `vite.config.ts` 是普通 CSR 应用配置，不包含来源项目的 `build.lib` 配置。
- `vitest.config.ts` 使用 jsdom，并加载 `test/setup/vitest.setup.ts`。
- `package.json` 同时包含 Vitest 测试脚本和所需测试依赖。
- `oxlint.config.ts` 不包含来源项目的全局变量白名单。
- `tsconfig.json`、`vite.config.ts`、`vitest.config.ts` 和源码路径别名一致。
- lint-staged 同步调用 Oxlint 和 Oxfmt，且命令指向当前项目配置文件。
