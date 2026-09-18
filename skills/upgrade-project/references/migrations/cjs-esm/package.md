# package.json 模板

下面只展示 ESM 声明和类型检查脚本，合并到目标项目的现有 package.json。保留已有 Node.js、TypeScript 和 `@types/node` 版本；只有用户同时要求升级工具链，或已证实当前版本无法支持迁移时，才另行确定兼容版本。不要只更新 `@types/node` 而保留不匹配的 `engines.node`。

```json
{
  "type": "module",
  "scripts": {
    "typecheck": "tsc --noEmit",
    "typecheck:watch": "tsc --noEmit --watch"
  }
}
```
