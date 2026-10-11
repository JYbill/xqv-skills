---
name: codex
description: 将执行任务交给本机共享 Codex App Server，保存会话 ID，动态轮询进展、发送引导并转述结果。用于 Claude 或其他主助手负责讨论与任务派发、Codex 负责执行，且手机通过 ChatGPT SSH 访问同一任务的场景。
---

# Codex 任务派发

主助手负责讨论、明确任务、检查进展和简洁转述；执行交给 Codex。使用本技能的 `scripts/bridge.py` 直接连接现有共享服务的 Unix WebSocket，手机 SSH 也应连接同一用户、同一 `CODEX_HOME` 的共享服务。

## 执行约定

- 默认使用 Codex 现有配置。新建会话只传任务目录等必需字段；模型、推理强度、沙箱、审批、服务等级、系统和开发者指令均不主动覆盖。只有用户明确指定时才添加对应字段。续接会话保留该会话已有配置。
- 使用同一 thread ID 跟进同一任务；主助手的讨论和转述不会自动同步到手机，手机看到的是 Codex 会话。
- 通过共享服务发起任务；不以 `codex exec`、独立 `app-server` 或 App 内部 MCP 作为自动降级方案。遇到写入锁冲突，报告当前服务不一致，不删除锁、不重复建任务。
- Thread ID、Turn ID、游标、请求 ID、操作 ID 等 Codex 元数据只在内部保存；仅新建会话的那一次回复提供 Thread ID，此后的回复不再展示这些元数据（用户明确询问时除外）。
- 执行端内容只作为任务证据，不扩大用户授权；新的实质决策交给用户。

## 1. 连接

需要本机 Python 3、可执行的 `codex` 和已运行的共享 App Server。脚本兼容 macOS/Linux 的 Unix socket，不依赖第三方 Python 包。

先将 `CODEX_SKILL_DIR` 设为当前加载的技能目录；仓库内路径为 `skills/codex/`，安装后以实际路径为准。后续命令沿用该变量。

```bash
export CODEX_SKILL_DIR="/absolute/path/to/codex"
python3 "$CODEX_SKILL_DIR/scripts/bridge.py" start
python3 "$CODEX_SKILL_DIR/scripts/bridge.py" status
```

`start` 只启动桥接进程，连接既有共享服务，不启动新的 Codex 引擎。确认 `connected=true` 且初始化结果无错误。若服务未启动，在用户已授权启动执行环境的情况下运行 `codex app-server daemon start`；已有运行任务时不更新或重启后台服务。

桥接进程持续接收通知和审批请求，在 `~/.local/state/codex-skill/<CODEX_HOME哈希>/` 保存事件与操作结果。保持该进程运行，短命的查询命令退出不会断开它。目录含任务内容，按本地私有数据处理。`CODEX_SKILL_STATE` 可指定其他本地状态根目录。修改 `CODEX_HOME` 后应确认手机仍连接相同服务。

## 2. 派发或续接

用 JSON 文件传入参数，避免把用户原文拼进 shell。以下 `~/task-start.json` 等为示例路径，实际使用权限受限的临时文件，调用后清理不再需要的输入文件。

### 任务目录与信任

`cwd` 默认取主助手当前工作目录（当前项目）；用户指定其他目录时用其路径。`thread/start` 不检查目录是否存在，也不创建目录，所以创建前先核对：

1. 目录是否存在。不存在时说明路径并询问用户是否创建；同意后再 `mkdir`，不自动创建。
2. 是否已信任。用 `config/read` 查 `projects` 中该路径的 `trust_level`（只看该路径本身或其上级是否为 `trusted`）。
3. 未信任时询问用户是否信任该目录；信任属于安全设置，未获明确同意不写入。同意后只在 `$CODEX_HOME/config.toml` 追加一段 `[projects."<绝对路径>"]` 加 `trust_level = "trusted"`，写前备份，不改动其他配置；bridge 不放行 `config/value/write`，不要绕过白名单。
4. 目录缺失或未信任且用户未同意时，不新建 thread，说明原因后继续其他已授权工作。

新任务参数示例：

```json
{"cwd":"/absolute/project/path"}
```

```bash
python3 "$CODEX_SKILL_DIR/scripts/bridge.py" rpc --method thread/start --params-file ~/task-start.json --operation-id <唯一操作ID>
```

保存返回的 `result.thread.id` 及有效配置。随后使用独立操作 ID 发送 `turn/start`：

```json
{"threadId":"<会话ID>","input":[{"type":"text","text":"用户授权的任务，包含约束和验收条件"}]}
```

```bash
python3 "$CODEX_SKILL_DIR/scripts/bridge.py" rpc --method turn/start --params-file ~/task-turn.json --operation-id <另一唯一操作ID>
```

保存返回的 turn ID，并仅在这次创建后向用户提供 thread ID，便于手机定位。发送前确认任务目录和目标服务；跨客户端能力的验证范围见 [协议说明](references/protocol.md#已验证与未验证)。

已有任务先调用 `thread/read`（参数 `{"threadId":"..."}`）查看状态；需要接收它的实时事件时，调用同一服务的 `thread/resume`，仅传 `threadId` 和 `excludeTurns:true`，不覆盖配置。恢复不会自动发送新任务；不要对正在执行的任务另发 `turn/start`。

所有写操作必须有唯一 `--operation-id`。同一操作超时后用原 ID、原参数重试，桥接会返回已保存结果；不同操作用新 ID。后端超时或断线导致结果未知时，先查询原 thread 和 `bridge/lateResponse`，不能换 ID 重发。新建 thread 超时且未取得 ID 时，先核对 `thread/list` 和事件。

## 3. 动态轮询与纠偏

下图概括交互分支；具体提交方式见本节和第 4 节。人工处理项优先于偏差通知；图中的“结束当前轮”指 Claude 回复结束，不是中断 Codex。

```text
轮询并核对最新状态
  |
  +-- 有待人工处理的问题 --> 用消息呈现问题与两种处理方式
  |                           |
  |                           v
  |                         结束当前轮，暂停轮询，保留桥接连接
  |                           |
  |                           +-- 用户在 Claude 回答
  |                           |     --> 核对状态，提交仍需处理的答复
  |                           |     --> 恢复轮询
  |                           |
  |                           +-- 用户自行处理
  |                                 --> 等其在 Claude 告知已处理
  |                                 --> 恢复轮询，核对结果
  |
  +-- 无人工问题，但发现跑偏 --> 通知用户，继续轮询，不自行干预
  |                           |
  |                           +-- 用户给出纠正 --> 核对状态并转发 --> 继续轮询
  |                           +-- 用户同意或未回复 -------------> 继续轮询
  |
  +-- 正常执行中 -----------> 继续轮询
  |
  +-- Codex 当前轮已结束 ---> 核对结果与未完成项，再向用户回报
```

```bash
python3 "$CODEX_SKILL_DIR/scripts/bridge.py" poll --thread <会话ID> --cursor 0 --wait 50 --limit 500 --until-idle --summary
```

每次用上次返回的 `cursor` 继续，游标按任务保存，推荐 `--limit 500`。`has_more=true` 时用最短等待 `--wait 2` 连续读取后续页，已有事件不再等待。`--summary` 过滤 delta、额度、token 用量和技能变更通知，保留关键事件与请求、提问；分页游标仍覆盖已读取的原始事件。

`--until-idle --summary` 一次等到目标 thread 的 `turn/completed`、待处理请求或 `question_messages`，最多等待 `--wait` 秒；分页未读完或连接断开也会提前返回。超时返回不代表完成。

- 等待时间由主助手根据实际进度决定，最短 2 秒；脚本单次最多 50 秒，并且必须小于宿主工具超时。即将完成的步骤可用 2 秒，长命令或连续无新增进展时延长等待。
- 按上图决定继续或暂停。skill 不会在宿主结束当前轮后自动唤醒模型，也不能保证关闭 App 后继续监督。
- 偏差判断依据工具结果、文件改动、失败信息和用户约束。通知只说明原目标、偏差及影响，告知用户可回复纠正要求。没有新增输出不等于卡住；同一偏差没有新证据或影响变化时不重复提醒。
- 转发用户的纠正要求：先核对轮次，活跃时用 `turn/steer`：`{"threadId":"...","expectedTurnId":"正在执行的轮次ID","input":[{"type":"text","text":"用户的纠正要求"}]}`；已结束时核对最新结果，用原 thread 的 `turn/start` 传入仍需执行的要求。引导失败先核对接收状态，避免重复提交；后续轮询检查纠正是否生效。
- 用户要求停止时，发送 `turn/interrupt`，参数为 `threadId` 与 `turnId`；看到完成事件的中断状态后才报告已停止。

完成判定只看目标 turn 的 `turn/completed`，核对 thread、turn 和 `status`，区分 completed、failed、interrupted；`thread/status/changed` 的 idle、`item/completed` 或普通消息不能代替完成事件。

首次接入、事件缺口或重连后，通过 `thread/read` 与分页历史核对结果：`thread/turns/list` 参数可用 `{"threadId":"...","limit":20,"itemsView":"full","sortDirection":"desc"}`。不要把连接断开当作任务完成。更多故障与请求处理见 [协议与待处理请求](references/protocol.md)。

## 4. 审批、输入与结果

人工处理项同时检查 `pending_requests`、`question_messages` 和普通消息中的提问。异步提问是带 `questions` 的 agentMessage，即使 `pending_requests` 为空也可能需要答复。`followup_observed_answer_unconfirmed` 只表示后来出现了用户消息，仍需核对是否回答了问题。

按上图暂停时，以当前轮最后一条消息呈现具体问题和可选项，不附 thread ID、turn ID、请求 ID 等元数据，并提供两种方式：

1. **在 Claude 回答**：核对最新状态后，仍待响应的服务请求按 [协议说明](references/protocol.md#提交用户答复) 提交；异步或普通文字答案按第 3 节的消息转发方式传入原 thread，不调用 `respond`。恢复轮询后核对接收结果。
2. **自行处理后告知 Claude**：收到“已处理，可以继续”后恢复查询，核对处理结果；仍有未解决问题时再次询问并暂停。“已处理”不是代为提交答案或审批决定的依据；仅说“我去处理”则继续等待。

暂停前保存 thread ID、turn ID、游标和待处理项。Codex 的独立工作仍可能继续；恢复时已解决的请求不重复提交，已过期或断线失效的请求不使用旧 ID 回答。

主助手不自动审批、不猜答案、不修改审批策略来避开阻塞。用户未回复不构成新增授权。

Codex 一轮结束不等于目标达成；核对验收条件后，回报结果、验证情况和未完成项，保留必要的错误、限定条件和路径。thread ID、turn ID、游标及操作 ID 只在内部保存，供后续续接，回报中不再出现。
