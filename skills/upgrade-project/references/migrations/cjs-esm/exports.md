以下以编译后运行 JavaScript 的 Node.js ESM 项目为例，使用 `.js` 相对导入扩展名；已有源码执行方式按实际解析规则调整，不因这些示例切换运行方式。

只导出类型时：

```ts
export type { UserDto } from './user.dto.js'
```

同时导出类型和值时：

```ts
export { createUser, type UserDto } from './user.js'
```
