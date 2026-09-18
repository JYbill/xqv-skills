# vitest.config.ts 模板

基础 React 测试使用 jsdom，并通过 `test/setup/vitest.setup.ts` 加载 Testing Library matcher。`oxc.target` 与配套 package 模板的最低 Node.js 版本 26 对齐，落地时按目标项目支持的最低版本调整。

```ts
import { fileURLToPath, URL } from 'node:url'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  oxc: {
    target: 'node26',
  },
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./test/setup/vitest.setup.ts'],
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    passWithNoTests: true,
  },
})
```
