# 协议与待处理请求

## 两种入口

模式选择与完整流程见 [SKILL.md](../SKILL.md#先选择模式)，每个新任务由用户明确选择，不设默认模式。

| 模式 | 入口 | 连接与存储 | 提交后的行为 |
|---|---|---|---|
| 1. 持续追踪 | `bridge.py` | 桥接连接共享服务，事件写入临时 SQLite | 主助手通过 `poll` 跟进；轮次完成后桥接退出，SQLite 保留 |
| 2. 仅派发 | 原生 `codex queue` | 新会话短连接创建；CLI `codex queue` 提交，不启动桥接、不写桥接 SQLite | CLI 确认提交后结束回复，不接管审批或继续查询 |

新会话先保存 `thread/start` 返回的 ID，再调用 CLI。`Queued message ...` 是提交成功，不是执行完成；超时或非零退出码均不能据此自动重发。仅派发不经过桥接操作去重表，不使用 `--operation-id`。CLI 不覆盖的会话创建使用一次性连接，模板见 [仅派发示例](cli-examples.md#仅派发新会话或已有会话)。

CLI 已覆盖的派发和归档分别使用 `codex queue`、`codex archive`；桥接 RPC 不再开放 `turn/start`、`thread/archive`。持续追踪必须先通过桥接创建或恢复会话、确认订阅，再从 CLI 派发。保存事件中的 `turn/started` 用于核对实际 turn ID；排队消息 ID 不能替代轮次 ID。

新会话的显式模型、推理强度或服务等级随 `thread/start` 传入并核对响应；已有会话通过 `settings.py` 短连接调用 `thread/settings/update`，回读核对后再使用 CLI 派发；Fast 为 `serviceTier:"priority"`，普通模式为 `serviceTier:null`，省略则不改。脚本只接受这些设置，不修改审批或沙箱，也不启动桥接。调用与失败处理见 [设置模板](cli-examples.md#显式修改模型推理强度或服务等级)。

以下桥接连接、轮询和答复说明适用于模式 1；模式 2 的故障应先核对 CLI 返回和原会话，不自动切换成持续追踪。

## 脚本结构

外部命令仍由 `bridge.py` 提供，拆分不改变子命令、参数和返回格式。安装时复制整个技能目录，不单独复制入口文件。

```text
scripts/
  bridge.py     命令行参数、输出和退出码
  client.py     连接后台、启动检查、离线读取事件
  daemon.py     接收 Codex 事件、处理请求、管理进程退出
  store.py      SQLite、分页、提问状态和批量等待
  settings.py   显式模型、推理强度和服务等级的短连接更新及回读
  transport.py  App Server 的 Unix WebSocket 通信
  config.py     共享路径、超时、接口白名单和 JSON 编码
```

客户端的离线查询直接使用存储模块，不加载后台服务；短连接创建会话只引用 `config.py` 和 `transport.py`。仅执行 `bridge.py serve` 才加载后台服务入口。

## 连接和配置

`start` 仅打印 `{connected, epoch}`，失败时附带 `error`；`status` 保持完整输出。`start` 仍仅在 `connected=true` 且不存在 `error` 时返回退出码 0。

桥接直接连接 `$CODEX_HOME/app-server-control/app-server-control.sock`，使用 Unix socket 上的 WebSocket（HTTP Upgrade，客户端掩码帧，支持分片与 ping/pong）。手机 SSH 的 `codex app-server proxy` 转发的也是这一端点的 WebSocket 字节流，不能把它当成 JSONL stdio 服务。桥接自身与短时查询命令之间使用本地 Unix socket 和 JSONL，不暴露网络监听。

后台服务可能缓存配置；用户修改配置后，用 `config/read` 和创建/恢复响应核对生效值，不自行重启正在执行的服务。

桥接只在目标会话的当前轮次完成时自动退出；其他会话或已知旧轮次的 `turn/completed` 不触发退出。恢复一个已在执行的会话时，若尚未观察到 `turn/started`，以该目标会话收到的完成事件为准。普通 `item/completed` 不触发退出。已接收的最终事件先写入 SQLite，正在处理的客户端请求完成后退出本地服务。退出后的 `poll` 从 SQLite 读取，返回 `connected=false`；是否完成仍以目标轮次的完成事件为准。后续 RPC 需要先 `start` 并重新接入会话。意外断线同样结束后台服务，`start` 会等待断开的旧接收进程释放资源，再重新启动；不会把 `connected=false` 当作连接成功。

## 增量轮询

`poll` 必须指定非空的 Codex 会话 ID（`--thread`）。`--event-limit` 范围为 1～200，默认 50。积累到指定数量的关键事件时返回；人工审批、结构化提问、目标会话轮次结束或断线提前返回。内部保留 100 秒超时保护，客户端 socket 超时为 110 秒，调用工具的超时应大于 110 秒。主 Agent 或宿主工具可能因长时间没有输出而终止调用；没有输出本身不说明 Codex 卡住。这些超时设置只能限制等待时间，不能阻止宿主提前终止工具。客户端被终止后，先核对桥接和会话状态，再用最后确认的游标查询，不重新派发任务。旧的 `--wait`、`--until-idle`、`--limit` 已移除。

`poll` 固定保留 `item/completed`、`thread/status/changed`、`turn/started`、`turn/completed`、服务请求与解决通知、提问、错误及桥接诊断，过滤 delta、`account/rateLimits/updated`、`thread/tokenUsage/updated`、`skills/changed` 等其他通知。`item/started` 与 `item/completed` 中 `summary`、`content` 均为空的 reasoning 也被过滤。条数按过滤后的事件计算，空 reasoning 不占 `--event-limit`，过滤不删除原始记录。

`events` 按条数分页；`urgent_events` 单独返回游标之后的紧急事件，包含后续页中的审批、结构化提问和完成事件。若紧急事件已在本页 `events` 中，`urgent_events` 仅返回 `{cursor, method}` 引用；只有后续页的紧急事件才带完整事件结构（内容仍遵循下述精简规则）。跨页按事件 `cursor` 去重。`pending_requests` 与 `question_messages` 仍是独立状态快照，可能来自游标之前；提交答复前核对最新状态。旧连接的失效请求不会持续唤醒新的 `poll`；已出现后续用户消息的提问在该消息读过后也不再持续唤醒，但仍保留“答复尚未核实”的标记。新轮次开始会清除上一轮提问快照。

默认输出只在 poll 组装时精简，SQLite 的结构和原始事件不变，旧库无需迁移：

- `commandExecution` 保留 `id`、`type`、`command`、`cwd`、`status`、`exitCode`、`durationMs` 和 `aggregatedOutput`；省略 `pluginId`、`scriptPath`、`processId`、`source`、`commandActions` 等字段。`aggregatedOutput` 成功失败均只保留前 200 字符，超过时追加 `…（共 N 字符，已截断）`，N 为原始字符数。
- `userMessage` 保留事件及消息的 `id/type`，用 `text: "收到用户消息"` 和 `character_count` 替代正文；字符数按 `content` 文本段的字符数求和。提问快照仍使用原始用户消息计算，保留 `followup_observed_answer_unconfirmed` 行为。
- `turn/completed` 保留 turn 的 `status/error`；`items` 中已通过已读页或本页 `item/completed:agentMessage` 投递的回复按连接、会话、轮次和消息 ID 去重。尚未投递的回复保留全文；剩余 items 为空时省略该字段，空 reasoning 同样移除。
- `question_messages`、`pending_requests`、`urgent_events` 为空时不输出，缺省即为空。固定 `coverage` 说明仅在 `--full` 或返回错误事件时输出。

`poll --full` 恢复命令完整输出及字段、用户消息全文，并显示 `coverage`；使用原游标可重读。它不改变关键事件过滤、分页、紧急引用和完成回复去重规则，也不恢复空数组字段。

`cursor` 是原始事件序号。还有关键事件未返回时，游标停在本页最后一条普通分页记录；读完当前快照才推进到快照末尾，包含已过滤事件。紧急事件提前返回不推进分页游标，避免跳过普通记录。`has_more=true` 时继续翻页。

`return_reason` 为 `event_limit`（已满指定条数）、`attention`（有紧急事件或人工处理项）、`disconnected`（连接已断开）或 `timeout`（内部等待超时）。完成判定仍需核对目标 turn 的完成事件和状态，不能只看返回原因。

## 请求记录

带 `id` 和 `method` 的后端消息属于服务发给客户端的请求，桥接记录完整 `params`，保留原类型。常见类型：

- `item/commandExecution/requestApproval`：命令执行审批。
- `item/fileChange/requestApproval`：文件改动审批。
- `item/permissions/requestApproval`：额外权限请求。
- `item/tool/requestUserInput`：需要用户回答。
- MCP elicitation 或其他类型：保留原始方法和参数，按实际问题处理，不能默认为允许。

`pending_requests` 的 `key` 包含连接 epoch 和原 request ID；同一个数字 ID 在重连后不是同一个请求。`serverRequest/resolved` 表示服务已报告解决。发送响应后仍须观察后端确认或任务继续运行，不能把 socket 写入成功当作审批完成。

桥接只能记录自己接收的请求，不保证看到其他连接已经收到的审批，也不保证首次接入能重放旧请求。`unknown_after_disconnect` 表示原连接已断开，不能继续使用旧 request ID 回答；从原任务检查是否重新发起请求。手机没有显示审批时，向用户明确说明，不能承诺跨客户端审批已支持。

## 提交用户答复

人工交互流程见 [SKILL.md 第 4 节](../SKILL.md#4-审批输入与结果)。以下仅用于用户已明确答复、且仍待响应的服务请求。

使用当前 CLI 生成的协议 schema 确认该请求的响应形状；不同请求类型不可混用。可在临时目录运行：

```bash
codex app-server generate-json-schema --out <临时目录> --experimental
```

例如命令审批的具体决定必须按当前 `CommandExecutionRequestApprovalResponse` 校验；用户输入按 `ToolRequestUserInputResponse`。不要默认“本次允许”意味着“整场会话允许”。

把准确响应对象写入私有 JSON 文件，按 [回复服务请求模板](tracking-examples.md#人工处理回复服务请求) 提交。

`--human-confirmed` 是对已获得用户答复的声明，不是获取许可的替代品。脚本只能核对请求是否属于当前连接且未解决，不能判断自然语言授权是否充分。

## 故障处理

客户端收到顶层 `error` 时输出错误 JSON 并返回非零退出码；`status` 返回 `connected=false` 也使用非零退出码。主助手同时检查退出码和返回内容。

- `connected=false`：原服务任务可能仍运行。先看事件和历史，定位连接失败原因；不重建任务、不重发未确认的写操作。
- 当前版本断线后自动退出，直接 `start` 可重建连接；若旧版本进程仍未退出，先核对 PID/命令并停止该旧桥接，不停止后台 Codex 服务。重新 `thread/resume` 时即使沿用原操作 ID，也会在新连接重新订阅；历史创建操作不会因此重复执行。
- 客户端查询超时：用相同游标重新查询。写操作重试遵循 SKILL.md 第 2 节；RPC 40 秒超时后的响应记录为 `bridge/lateResponse`，按 RPC ID 和内容核对。
- 协议版本不匹配：查看 `codex --version`、`codex app-server daemon version` 和当前 schema，报告不兼容；不自动更新或降级运行中的服务。
- `thread/resume` 写入冲突：可能是桌面 App 独立服务持有会话；应切换到正确入口或等用户决定交接，不能删锁。

## 已验证与未验证

持续追踪使用一个连接接收事件，短时查询读取增量；手机与其共享后台服务。创建技能时已通过无模型调用的真实连接/当前会话查询检查及模拟协议测试。后续用户授权的真实测试已成功创建任务并收到带 `questions` 的异步提问；随后另一客户端提交“简短段落”，桥接收到用户消息、最终答复和 `turn/completed`；测试端没有代用户回答。手机实时引导、跨客户端审批交接、长时间断线恢复和 Claude Desktop 实际工具循环，需要接入后的端到端验证。

2026-10-11 已完成以下验证：

- CLI 派发与桥接追踪联调通过：先由桥接创建并订阅会话，再调用 `codex queue`，桥接收到 `turn/started`、预期最终回复和 `turn/completed`；最后用 `codex archive` 归档，并从归档列表核对成功。

- 本机 CLI 0.162.1 的 `codex queue` 在约 0.39 秒内提交并退出，测试轮次约 8.6 秒后完成；派发客户端退出未阻止该测试任务继续执行。
- 短连接新建会话后通过 CLI 仅派发的流程实测成功，最终得到预期回复；测试会话已归档。仅派发后遇到真实审批、长期排队和断线恢复的行为未实测。
- 27 项桥接离线测试通过，覆盖事件条数等待、紧急事件跨页返回、桥接进程退出后读取 SQLite。桥接进程退出测试使用真实本地进程和 socket，Codex 后端为模拟；不等同于真实模型端到端验证。

2026-10-12 已完成显式设置修复验证（CLI 与共享 App Server 均为 0.162.1）：

- 本地测试服务抓取确认：`codex queue --remote` 的 `-m`、`-c model_reasoning_effort=...` 未进入请求，CLI 仍返回入队成功。skill 改为在创建时传入设置，或通过 `settings.py` 更新已有会话；未修改原生 CLI。
- 真实服务验证新会话 high + Fast、high + 普通模式的创建响应；普通模式请求 `serviceTier:null`，当前服务回读为 `"default"`。没有首轮历史的新会话直接 `thread/resume` 会失败，因此新会话在创建时传设置。
- 真实已有会话验证 Fast → 普通 → Fast，以及只改推理强度时保留服务等级；原生 queue 派发的 high + Fast、low + 普通轮次均完成，派发后回读设置保持一致。轮次历史确认 effort 为 high/low；该版本历史不记录 service tier，服务等级以服务端配置回读为依据，不据此声称已核验上游计费或排队优先级。测试会话已归档。
- 41 项离线测试通过，其中 6 项设置测试覆盖切换、字段省略、模型设置、无效参数、服务拒绝、静默忽略与断线；设置更新失败时不派发、不自动重试。

来源：
- https://learn.chatgpt.com/docs/app-server
- 本机 `codex app-server generate-json-schema` 的输出（CLI 0.162.1）；以部署时版本为准。
