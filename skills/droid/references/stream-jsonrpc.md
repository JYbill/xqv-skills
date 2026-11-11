# Droid CLI 长驻会话与 AskUser

需要多轮交互，或需要捕获并回答 Droid 执行中的问题、权限请求时读取本文件。普通一次性 `droid exec` 的 `json` 和 `stream-json` 输出不提供这套双向交互。

## 启动与协议版本

在目标项目目录启动一个进程，并通过宿主工具保持它的标准输入、输出打开：

```bash
droid exec --input-format stream-jsonrpc --output-format stream-jsonrpc
```

使用宿主提供的长运行命令句柄分次读取输出和写入输入。若宿主的非交互命令会立刻关闭 stdin，使用它支持的持久交互进程或 PTY；PTY 可能回显输入，解析时按 JSON-RPC 的 `type` 和 `method` 区分输入与输出。每条消息写成一行 JSON，并以换行结束。

CLI 的输出中可能有通知、响应、Droid 发起的请求或非 JSON 诊断信息。不要把整段输出当作单个 JSON 对象，也不要把 `droid.session_notification` 都当成最终答复。

本机 Droid CLI 1.8.0 实测要求请求和响应包含 `jsonrpc`、`type`、`factoryApiVersion` 和 `factoryProtocolVersion`。从当前进程发出的通知或错误响应读取两个版本字段，并原样用于该连接；不要固定使用某次测试的版本号。如果进程没有先输出通知，1.8.0 可发送下面的无副作用探测，之后从错误响应读取版本字段：

```json
{"jsonrpc":"2.0","type":"request","id":"version-probe","method":"droid.protocol_probe","params":{}}
```

该探测缺少版本字段，可能返回 `-32700`、`id: null`；它没有创建会话或发送任务。若当前版本的行为不同，以实际输出及官方协议为准。

## 创建、加载与发送

以下示例中的 `API_VERSION` 和 `PROTOCOL_VERSION` 要替换为当前连接返回的值。每个客户端请求使用不同的 `id`。

新建会话：

```json
{"jsonrpc":"2.0","type":"request","factoryApiVersion":"API_VERSION","factoryProtocolVersion":"PROTOCOL_VERSION","id":"create-1","method":"droid.initialize_session","params":{"machineId":"local","cwd":"/absolute/project/path","modelId":"claude-sonnet-5-5","reasoningEffort":"xhigh"}}
```

从成功响应的 `result.sessionId` 保存会话 ID。示例使用技能默认模型；用户明确指定其他模型时按其要求设置。自主权限也在 `params` 中按当前版本的协议设置；不要把启动命令中的 `--model`、`--reasoning-effort` 或 `--auto` 当成此模式的会话设置。检查响应中的 `settings`，不要假设长驻模式默认只读。

加载用户指定的已有会话：

```json
{"jsonrpc":"2.0","type":"request","factoryApiVersion":"API_VERSION","factoryProtocolVersion":"PROTOCOL_VERSION","id":"load-1","method":"droid.load_session","params":{"sessionId":"SESSION_ID"}}
```

确认加载响应成功、目标会话与目录正确，再发送用户授权的任务。加载结果可能包含历史消息和设置，读取及展示时只保留必要信息。先处理恢复后重新收到的待处理请求；不要对正在由其他客户端执行的会话重复派发。

开始新轮次前检查 `result.settings` 中的模型；按 [模型与额度](../SKILL.md#模型与额度)确定是否更新。CLI 1.8.0 支持在会话空闲时用以下请求切换模型：

```json
{"jsonrpc":"2.0","type":"request","factoryApiVersion":"API_VERSION","factoryProtocolVersion":"PROTOCOL_VERSION","id":"settings-1","method":"droid.update_session_settings","params":{"modelId":"kimi-k3.1-pro"}}
```

只指定 Kimi 模型时，本机 CLI 1.8.0 会将原先的 Sonnet `xhigh` 切换为 Kimi 默认的 `max`。更新成功后重新加载空闲会话，并检查返回的 `settings.modelId` 和 `settings.reasoningEffort`；以当前版本的实际返回为准。确认标准额度耗尽后，按技能的回退规则在原会话继续未完成的工作，不重复派发已经执行的动作。

```json
{"jsonrpc":"2.0","type":"request","factoryApiVersion":"API_VERSION","factoryProtocolVersion":"PROTOCOL_VERSION","id":"send-1","method":"droid.add_user_message","params":{"text":"用户授权的任务内容"}}
```

请求成功只表示消息已被接收。持续读取 `droid.session_notification`，直到匹配会话的 `agent_turn_completed`；检查其 `reason`、错误和最终消息。事件中的文本增量可用于展示进度，但不能代替轮次结果。

## AskUser 与权限请求

收到 `method: droid.ask_user` 时，`params.questions` 包含问题的 `index`、`question`、`options` 以及可选的 `multiSelect`；请求本身的 `id` 用于答复。按技能的交互规则转达问题或使用已有明确答案；向用户展示时保留自定义输入与多选能力，不猜测用户意图。

确定答案后，向同一进程写入响应；`id`、问题序号和问题原文使用收到的值，每个问题对应一项答案。多选答案按官方格式以逗号和空格连接：

```json
{"jsonrpc":"2.0","type":"response","factoryApiVersion":"API_VERSION","factoryProtocolVersion":"PROTOCOL_VERSION","id":"ASK_REQUEST_ID","result":{"answers":[{"index":1,"question":"收到的问题原文","answer":"用户的答案"}]}}
```

用户明确取消问卷时，可按同一响应格式返回 `{"cancelled":true,"answers":[]}`；这会中断当前轮次。答复后继续读事件，确认 Droid 已继续或报告错误。

`droid.request_permission` 是独立的服务端请求。展示其待执行动作和实际可选结果，按用户已有授权及宿主权限处理；不要把 AskUser 的答案格式用于权限请求。权限响应的字段和选项以当前版本及 [Factory 文档](https://docs.factory.com/sdk/typescript)为准。

## 保持连接和恢复

- 同一连接中的待处理请求要用该连接收到的请求 ID 回答。保存会话 ID、进程句柄和待处理问题；宿主进程退出后，这个句柄可能失效。
- 断线后先加载原会话并检查当前状态及是否重新收到待处理请求。未重新收到请求时，不要假定旧请求仍有效，也不要把普通新消息当成已经提交的工具答复。重连恢复待处理问题的具体行为取决于 CLI 版本和运行环境。
- 只能证明进程仍在运行时报告其在线；未收到结束事件、进程退出或连接断开，都不足以证明任务成功。结果不明时先查会话记录，避免重复执行。

来源：[Droid Exec](https://docs.factory.com/droid-exec/overview)、[AskUser 工具参考](https://github.com/Factory-AI/factory/blob/main/docs/reference/ask-user-tool.mdx)。协议版本字段及创建会话、提问、回答和轮次结束已用本机 CLI 1.8.0 验证。
