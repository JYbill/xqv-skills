# Jev 配置

首次使用、迁移配置或排查认证错误时读取。正常浏览器任务只调用 `loadConfig()`，不改变 provider、model 或凭证。

## 配置路径与迁移

新配置放在 `~/.config/jev-codex-browser-use/config.json`。文件不存在时，bridge 依次读取 `~/.config/jev-codex-computer-use/config.json` 和 `~/.config/jev-browser-use/config.json`；新文件格式错误或不可读时直接报错，不悄悄回退。

旧路径只是配置兼容，不需要保留旧 skill 的安装目录或脚本。迁移时可把旧 JSON 原样复制到新路径，保留原来的 provider、model 和 `envFile`。不自动删除旧文件。若凭证文件位于准备删除的旧 skill 目录内，应先将它迁移到独立配置目录并更新 `envFile`，避免卸载后失效。

JSON 只包含 `envFile`、`provider` 和 `model`。`envFile` 为独立 dotenv 凭证文件的绝对路径，文件应仅当前用户可读。不要把真实密钥复制进 skill 仓库、配置 JSON、页面或日志。

## 支持的适配器

TypeSafe 配置示例：

```json
{
  "envFile": "/absolute/path/to/credentials.env",
  "provider": "typesafe",
  "model": "jev-latest"
}
```

dotenv 中设置 `TYPESAFE_API_KEY`。内置脚本使用 `https://api.typesafe.ai/v1/systemone`。

OpenRouter 配置示例：

```json
{
  "envFile": "/absolute/path/to/credentials.env",
  "provider": "openrouter",
  "model": "~typesafe/jev-latest"
}
```

dotenv 中设置 `OPENROUTER_API_KEY`。内置脚本使用 `https://openrouter.ai/api/alpha/decisions`。这些是脚本支持的配置示例，不表示已核实账号权限或远端模型当前可用性。

## 错误处理

- 保留已配置的 provider 和 model，不自动切换服务。
- 认证采用 Bearer；拒绝 HTTP 重定向，校验返回的选项、置信度、概率及模型名。
- 传输失败默认在本轮预算内重试一次；认证、额度和响应格式错误不自动重试。
- 配置或凭证缺失时报告具体缺项，不扫描无关文件寻找密钥。
- 不打印 dotenv、密钥、原始 HTTP 错误体或完整私有页面。只保留必要的状态与脱敏错误摘要。

## 离线验证

在本 skill 目录执行 `node --test scripts/bridge.test.mjs`。测试使用临时配置、合成页面和模拟 API，不读取真实凭证，也不访问外网。它验证脚本行为，不能代替真实 CUA 和 Jev 服务联调。
