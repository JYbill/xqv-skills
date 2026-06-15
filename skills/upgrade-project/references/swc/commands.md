优先运行：

```bash
pnpm typecheck
pnpm build
```

如果本次影响了 Vitest / Vite 的 SWC 转换配置，再运行相关测试文件或 project：

```bash
pnpm exec vitest run path/to/file.spec.ts
pnpm exec vitest run --project test
```

没有对应测试或命令失败时，不要虚报通过；保留关键失败信息并说明是否属于本次 SWC 配置范围。
