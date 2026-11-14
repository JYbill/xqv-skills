---
name: codex-images-gen
description: Generate or edit images through the active Codex model provider's OpenAI-compatible Images API, using the current conversation's model.
---

# Codex provider 图片生成与编辑

用户要求使用当前 Codex provider 生图或改图时，使用本技能。先确认当前会话实际启用的 provider 和模型；`config.toml` 顶层值可能被 profile、启动参数或运行时设置覆盖。无法确认实际值时，询问用户，不静默改用其他模型或 provider。`wire_api = "responses"` 不代表该 provider 支持 Images API。

使用 Python 3.11+ 运行 `scripts/images.py`。`--provider` 填实际 provider 名，`--model` 填当前会话模型；示例中的值均为占位符。脚本从 `${CODEX_HOME:-~/.codex}/config.toml` 的对应 `model_providers` 读取 `base_url`、`env_key`、`experimental_bearer_token`、`http_headers`、`env_http_headers`、`query_params`，支持普通 Bearer 和配置的请求头。若实际配置经过覆盖、使用 OAuth、凭据助手或其他认证方式，先确认其有效地址和认证，再用适配该 provider 的方式请求；不要猜测、泄露或写出凭据。脚本不解析 profile 或运行时覆盖。

```bash
python3 scripts/images.py --provider PROVIDER --model CURRENT_MODEL \
  --prompt '图片描述' --output-dir /绝对路径/输出目录 --n 3

python3 scripts/images.py --provider PROVIDER --model CURRENT_MODEL \
  --prompt '编辑要求' --image /绝对路径/原图.png \
  --output-dir /绝对路径/输出目录 --quality high
```

脚本分别向 provider 的 `/images/generations` 发送 JSON 或向 `/images/edits` 发送 multipart；最终文件及实际返回数量显示在输出中。避免把密钥写入命令行、日志或文件；不要把服务端错误原文直接展示给用户。服务端不支持该接口或模型时报告错误，不擅自切换服务。

## 常用参数

- `--n`：一次请求的最终图片数，用户有多张需求时优先一次请求。检查实际返回数量；不足时说明，并按原需求补足。
- `--quality`：`low`、`medium`、`high`、`auto`，支持情况取决于模型和 provider。`high` 通常增加成本和耗时，具体以服务商为准；接口成功不证明参数已生效。
- `--size`：如 `1024x1024`、`1536x1024`、`1024x1536` 或 `auto`；支持的值依模型及 provider 而定。检查返回文件的实际尺寸。
- `--output-format`：`png`、`jpeg` 或 `webp`，支持情况取决于模型和 provider；脚本按实际图片内容决定文件扩展名。
- 流式请求的 `stream` 和 `partial_images` 用于中间预览；`partial_images` 是预览数，不是最终图片数 `n`。本脚本处理非流式响应；需要流式时按实际 provider 协议实现并检查事件。

2026-11-14 对一个自定义 provider 的实测：`gpt-6.1-terra` 的生成、编辑及 `quality=low/high` 请求均返回图片；编辑请求 `n=3` 曾只返回一张，请求尺寸与实际图片尺寸也曾不一致。流式请求曾只收到完成事件，没有中间预览。这些只说明该次链路的表现，不能证明实际生图模型、品质参数生效或其他 provider 的行为。

向用户展示结果时，使用绝对路径 Markdown 图片嵌入；显示最终图片、实际张数和关键限制。不承诺客户端支持轮播。
