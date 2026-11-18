---
name: codex-images-gen
description: Generate or edit images through the active Codex provider's OpenAI-compatible Images API using gpt-6.2-sol.
---

# Codex provider 图片生成与编辑

用户要求使用当前 Codex provider 生图或改图时，使用本技能。确认当前会话实际启用的 provider，调用 Images API 时统一发送 `model=gpt-6.2-sol`。Profile、启动参数或运行时设置可能覆盖 `config.toml` 的顶层配置。无法确认 provider 时，询问用户。`wire_api = "responses"` 不代表该 provider 支持 Images API。

使用 Python 3.11+ 运行 `scripts/images.py`，`--provider` 填实际 provider 名。脚本从 `${CODEX_HOME:-~/.codex}/config.toml` 的对应 `model_providers` 读取 `base_url`、`env_key`、`experimental_bearer_token`、`http_headers`、`env_http_headers`、`query_params`，支持普通 Bearer 和配置的请求头。若实际配置经过覆盖、使用 OAuth、凭据助手或其他认证方式，先确认有效地址和认证，再按下文的接口和模型发送请求。脚本不解析 profile 或运行时覆盖。

```bash
python3 scripts/images.py --provider PROVIDER \
  --prompt '图片描述' --output-dir /绝对路径/输出目录 --n 3

python3 scripts/images.py --provider PROVIDER \
  --prompt '编辑要求' --image /绝对路径/原图.png \
  --output-dir /绝对路径/输出目录 --quality high
```

- 生成图片时向 `POST /v1/images/generations` 发送 JSON。
- 指定 `--image` 时向 `POST /v1/images/edits` 发送 multipart 表单，原图放在 `image` 字段。

脚本会在需要时为 `base_url` 补上 `/v1`，并输出最终文件和实际张数。服务端拒绝请求时，报告错误并保留已选的 provider 和模型。避免把密钥写入命令行、日志或文件，也不要直接展示服务端错误原文。

## 常用参数

- `--n`：一次请求的最终图片数，用户有多张需求时优先一次请求。检查实际返回数量；不足时说明，并按原需求补足。
- `--quality`：`low`、`medium`、`high`、`auto`，支持情况取决于模型和 provider。`high` 通常增加成本和耗时，具体以服务商为准；接口成功不证明参数已生效。
- `--size`：如 `1024x1024`、`1536x1024`、`1024x1536` 或 `auto`；支持的值依模型及 provider 而定。检查返回文件的实际尺寸。
- `--output-format`：`png`、`jpeg` 或 `webp`，支持情况取决于模型和 provider；脚本按实际图片内容决定文件扩展名。
- 流式请求的 `stream` 和 `partial_images` 用于中间预览；`partial_images` 是预览数，不是最终图片数 `n`。本脚本处理非流式响应；需要流式时按实际 provider 协议实现并检查事件。

2026-11-18 实测，一个自定义 provider 接受了两个接口的 `model=gpt-6.2-sol` 请求，各返回一张图片。网关实际调用的生图模型尚未确认。

向用户展示结果时，使用绝对路径 Markdown 图片嵌入；显示最终图片、实际张数和关键限制。不承诺客户端支持轮播。
