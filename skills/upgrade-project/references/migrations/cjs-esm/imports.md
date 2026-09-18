以下以编译后运行 JavaScript 的 Node.js ESM 项目为例，使用 `.js` 相对导入扩展名；已有源码执行方式按实际解析规则调整，不因这些示例切换运行方式。

只作为类型使用时：

```ts
import type { UserDto } from './user.dto.js'
```

默认导入只作为类型使用时：

```ts
import type UserConfig from './user-config.js'
```

命名空间类型导入：

```ts
import type * as PrismaTypes from './generated.js'
```

同一个模块同时导入类型和值时，可使用内联 `type`：

```ts
import { createUser, type UserDto } from './user.js'
```

如果周围代码习惯拆分导入，也可以拆成两条：

```ts
import { createUser } from './user.js'
import type { UserDto } from './user.js'
```
