# CSR React 基础依赖

## dependencies

```sh
pnpm add react react-dom
```

## devDependencies

```sh
pnpm add -D @tailwindcss/vite @types/node @types/react @types/react-dom @typescript/native-preview @vitejs/plugin-react husky lint-staged oxfmt oxlint oxlint-tsgolint tailwindcss vite
```

## 说明

- `@typescript/native-preview` 提供 `tsgo`，对应 `scripts.typecheck`。
- `oxlint-tsgolint` 服务于 `oxlint.config.ts` 中的 type-aware 检查。
- `@tailwindcss/vite` 和 `tailwindcss` 只在目标项目使用 Tailwind CSS 时保留。
- `husky` 和 `lint-staged` 只在目标项目需要提交前检查时保留。
- 不要复制来源项目的 `skills`、`commitlint` 或业务专用依赖，除非目标项目已经明确需要。
