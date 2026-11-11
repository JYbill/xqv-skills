---
name: droid
description: 使用 Factory Droid CLI 创建或续接会话、执行任务、查看本地记录，以及处理 AskUser 和权限请求；也用于 Droid CLI 的安装、模型和执行方式查询。
---

# Droid CLI

用户要求调用 Droid、查看 Droid 会话或处理其 CLI 问题时使用本技能。普通咨询只核对并回答问题；只有用户要求把任务交给 Droid 时才向会话发送消息。

## 开始前

1. 确定用户要新建会话、续接指定会话、查看记录，还是只了解命令。不要根据相似标题或路径猜测目标会话。
2. 新会话使用用户指定的项目目录；未指定时使用当前工作目录。先确认目录存在。已有会话沿用其原有目录；模型按下方约定处理。
3. 按需运行 `command -v droid`、`droid --version` 和 `droid exec --help`。安装、更新、登录或更改全局配置应符合用户的实际请求，不自动执行。
4. 按下方约定选择模型；其他设置沿用现有配置。可用模型以当前环境和 [Factory 模型文档](https://docs.factory.com/models)为准。

## 模型与额度

- 默认使用 Claude Sonnet 5.5：模型 ID 为 `claude-sonnet-5-5`，推理等级为 `xhigh`。新会话及没有另行指定模型的新任务都按此选择；用户对当前任务或已有会话明确指定的其他模型优先。
- 确认 **Standard Usage 标准额度耗尽**后，自动回退到 Droid Core 的 Kimi K3.1 Pro：模型 ID 为 `kimi-k3.1-pro`。使用该模型的默认推理等级；本机 CLI 1.8.0 返回的是 `max`。已知标准额度仍未恢复时，后续任务继续使用 Kimi；恢复后重新使用首选模型。不因普通网络错误、认证失败或无法确定额度类型的限流而切换。
- 切换前确认当前轮次已经停止，并检查原会话和已完成的工作。原任务已进入会话时，在同一会话继续未完成部分，不盲目重发原任务；状态不明时先核对。CLI 已自动切到目标模型时不重复切换。报告结果时说明实际使用的模型及回退原因。
- 这些选择只用于当前运行或会话，不修改全局默认设置。普通 `droid exec` 使用 `--model` 和 `--reasoning-effort`；长驻模式使用会话请求字段，具体见 [交互协议](references/stream-jsonrpc.md)。

## 选择执行方式

- **一次性任务或已结束会话的下一轮**：使用 `droid exec`；不需要人工问答时适用。普通模式默认只读；需要修改时，按用户已授权的操作范围选择 `--auto` 等级。不要为了绕过限制自动使用 `--skip-permissions-unsafe`。
- **需要在执行中接收 AskUser 或权限请求**：使用可保持标准输入、输出打开的长驻 JSON-RPC 进程，按 [交互协议](references/stream-jsonrpc.md)操作。直接调用 Droid CLI，不要求安装 SDK 或启动额外服务。
- **由用户在终端操作**：使用 `droid` 启动交互界面；续接可用 `droid --resume <session-id>`。
- **只查历史**：使用 `droid search <关键词> --json` 搜索本机记录，或在已确认位置只读目标会话文件。查看具体会话时，先确认 ID 和项目目录；不要通过发送一条新消息来读取历史。

## 一次性执行与续接

以下示例使用技能默认模型；用户对当前任务或已有会话明确选择其他模型时，使用对应设置。

```bash
droid exec --cwd /path/to/project --model claude-sonnet-5-5 --reasoning-effort xhigh --output-format json "任务内容"
droid exec --session-id SESSION_ID --model claude-sonnet-5-5 --reasoning-effort xhigh --output-format json "下一轮任务"
```

首次执行从 JSON 结果取得 `session_id`；续接使用同一个 ID。检查进程退出状态、`is_error`、结果和错误信息，不能把命令已启动当作任务完成。`-s` 是续接参数，不是查询运行状态或获取 AskUser 的命令；一次性 `droid exec` 不提供 AskUser。

确认标准额度耗尽、且适合续接时，可在原会话指定 `--model kimi-k3.1-pro`，不传 Sonnet 的 `xhigh`。需要核对实际会话配置时，可使用 `--output-format stream-json` 查看初始化事件的 `model` 和 `reasoning_effort`；配置值不等于实际推理 token 消耗。

## 跟进与交互

- 在用户要求等待任务完成或执行任务本身需要结果时，持续读取该进程的事件，直到当前轮次完成、失败、中断或需要用户处理。无新输出不代表完成，也不代表正在等待回答。
- 用户要求看到 AskUser 时，准确呈现问题、选项和单选／多选信息。答案已由用户明确给出或可由已授权的任务范围确定时，可以据此作答；涉及未知偏好或未获授权的决定时，向用户提问并等待答复。权限请求同样按用户已有授权及宿主限制处理。
- 会话 ID、宿主命令进程 ID 和 JSON-RPC 请求 ID 各有不同用途。续接任务使用会话 ID，读写长驻进程使用宿主提供的进程句柄，回答问题使用原请求 ID。
- 发送结果不明、进程断开或请求超时时，先核对会话记录与当前状态，不自动重发任务、重复答复或创建替代会话。
- 会话记录、事件和工具输出可能包含代码或敏感信息。只读取、转述任务所需内容；不要输出凭据，也不要把凭据放进提示词或命令参数。

安装方式、参数和协议可能随版本变化，以本机 `--help` 和 [Droid CLI 文档](https://docs.factory.com/droid-cli/cli-reference)为准。

用户明确要求安装时，macOS 可使用 `brew install --cask droid`，也可使用 `npm install -g droid`。npm 版本默认不自动更新；安装后检查 `droid --version`，按需让用户完成登录。
