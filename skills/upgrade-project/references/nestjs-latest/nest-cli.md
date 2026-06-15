# nest-cli.json 模板

NestJS latest 项目要求构建前清理旧输出目录：

```json
{
  "$schema": "https://json.schemastore.org/nest-cli",
  "collection": "@nestjs/schematics",
  "sourceRoot": "src",
  "compilerOptions": {
    "deleteOutDir": true,
    "assets": ["assets/*", "setting/*"],
    "watchAssets": true,
    "typeCheck": true,
    "builder": {
      "type": "swc",
      "options": {
        "swcrcPath": ".swcrc"
      }
    }
  }
}
```

迁移时只强制 `compilerOptions.deleteOutDir: true`。其他字段按项目事实保留，不为了套模板重排或重写。
