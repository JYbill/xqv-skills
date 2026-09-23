# package.json 模板

`name` 是占位值，落地到项目时必须替换成目标项目自己的包名。不要复制来源项目的业务包名、技能同步脚本、commitlint 配置或业务专用依赖。

```json
{
  "name": "<replace-with-project-name>",
  "version": "0.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "pnpm typecheck && vite build",
    "preview": "vite preview",
    "typecheck": "tsc --noEmit",
    "lint": "oxlint --deny-warnings --config oxlint.config.ts",
    "format": "oxfmt --config oxfmt.config.ts",
    "test": "vitest run",
    "test:watch": "vitest",
    "prepare": "husky"
  },
  "dependencies": {
    "react": "^19.3.0",
    "react-dom": "^19.3.0"
  },
  "devDependencies": {
    "@tailwindcss/vite": "^4.3.3",
    "@testing-library/dom": "^10.4.2",
    "@testing-library/jest-dom": "^7.0.1",
    "@testing-library/react": "^16.3.3",
    "@types/node": "^26.6.2",
    "@types/react": "^19.3.0",
    "@types/react-dom": "^19.3.0",
    "@vitejs/plugin-react": "^6.1.1",
    "husky": "^9.1.7",
    "jsdom": "^30.1.1",
    "lint-staged": "^17.5.1",
    "oxfmt": "^0.70.0",
    "oxlint": "^1.85.0",
    "oxlint-tsgolint": "^7.0.2002",
    "tailwindcss": "^4.3.3",
    "typescript": "^7.0.2",
    "vite": "^8.3.0",
    "vitest": "^5.0.1"
  },
  "engines": {
    "node": ">=26"
  }
}
```
