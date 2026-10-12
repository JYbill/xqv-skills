# Codex 持续追踪调用模板

适用：用户选择持续追踪，或明确要求通过桥接查询、管理已有会话。先按 [准备参数](cli-examples.md#准备参数) 设置技能目录和私有输入目录。仅派发见 [CLI 调用模板](cli-examples.md#仅派发新会话或已有会话)。

## 持续追踪：连接

适用：用户选择模式 1，或明确要求通过桥接查询、管理已有会话。

```bash
python3 "$CODEX_SKILL_DIR/scripts/bridge.py" start
python3 "$CODEX_SKILL_DIR/scripts/bridge.py" status
```

`start` 只返回 `connected`、`epoch`，失败附带 `error`；`status` 返回完整信息。确认 `connected=true` 且无 `error`。两条命令只连接既有 App Server，不创建模型任务。桥接退出后，新的 RPC 需要先重新 `start`；读取已保存事件的 `poll` 不需要重新启动。

## 持续追踪：新建会话并派发

适用：用户选择模式 1，且没有可续接的任务会话。先完成目录与信任检查。

写入 `create.json`：

```json
{"cwd":"/absolute/project/path"}
```

```bash
CREATE_OP=$(python3 -c 'import uuid; print(uuid.uuid4())')
python3 "$CODEX_SKILL_DIR/scripts/bridge.py" rpc --method thread/start \
  --params-file "$CODEX_INPUT_DIR/create.json" --operation-id "$CREATE_OP"
```

保存 `result.thread.id`，更新 `THREAD_ID`。`thread/start` 已为这个桥接连接订阅会话事件；随后按 [直接派发](cli-examples.md#直接派发) 调用原生 `codex queue`。CLI 返回后进入轮询，不结束追踪。

从 `turn/started` 或轮次历史核对实际 turn ID；CLI 输出的 queued message ID 不是 turn ID。创建会话的 RPC 重试复用原操作 ID 和原文件；CLI 派发不使用操作 ID，超时后先核对会话，不能重复提交。

## 持续追踪：续接已有会话

适用：需要重新接收原会话的实时事件。先按 [查询会话与历史](session-examples.md#查询会话与历史) 读取状态，再写入 `resume.json`：

```json
{"threadId":"实际会话ID","excludeTurns":true}
```

```bash
RESUME_OP=$(python3 -c 'import uuid; print(uuid.uuid4())')
python3 "$CODEX_SKILL_DIR/scripts/bridge.py" rpc --method thread/resume \
  --params-file "$CODEX_INPUT_DIR/resume.json" --operation-id "$RESUME_OP"
```

恢复连接不等于发送任务。仍有活跃轮次时直接追踪；需要新一轮且原轮次已结束时，保持订阅后按 [直接派发](cli-examples.md#直接派发) 使用 `codex queue`。

## 持续追踪：读取进展

适用：任务已派发，或桥接已退出但尚有已保存事件未读。

```bash
CURSOR=0
python3 "$CODEX_SKILL_DIR/scripts/bridge.py" poll \
  --thread "$THREAD_ID" --cursor "$CURSOR" --event-limit 50
```

首次接入用 `0`；后续把 `CURSOR` 更新为返回的 `cursor`。省略 `--event-limit` 也是 50，范围为 1～200。检查 `events`、`urgent_events`、`pending_requests`、`question_messages`；后三个数组省略时按空数组处理。页内紧急事件只含 `{cursor, method}`，从 `events` 取正文；页外紧急事件带正文，跨页按事件游标去重。`has_more=true` 时继续读取，不能因为已看到完成事件就丢弃尚未读取的工具结果。单次内部等待最多 100 秒，客户端超时为 110 秒，宿主工具超时应大于 110 秒。主 Agent 或宿主可能终止长时间没有输出的调用；未收到返回时保留原游标，核对状态后再查询，不重复派发。内部超时不代表完成，按 [轮询协议](protocol.md#增量轮询) 处理返回原因。

默认命令输出最多保留前 200 字符，截断后标注原始长度；用户消息只显示“收到用户消息”和字符数。完成事件去掉已投递的重复回复，仍保留最终回复全文的可用来源和 turn 的 `status/error`。读取完整命令字段、输出及用户消息正文时，使用需要重读页面的原游标：

```bash
python3 "$CODEX_SKILL_DIR/scripts/bridge.py" poll \
  --thread "$THREAD_ID" --cursor "$CURSOR" --event-limit 50 --full
```

`--full` 仍过滤空 reasoning、使用紧急引用并去重完成回复。`coverage` 说明只在 `--full` 或出错时出现。

## 人工处理：回复服务请求

适用：模式 1 中收到仍有效的审批或输入请求，且用户已经明确答复。`REQUEST_KEY` 取自最新 `pending_requests`；`answer.json` 按实际请求对应的协议写入，不把普通文字提问当作服务请求。

```bash
REQUEST_KEY="最新待处理请求的key"
ANSWER_OP=$(python3 -c 'import uuid; print(uuid.uuid4())')
python3 "$CODEX_SKILL_DIR/scripts/bridge.py" respond \
  --request-key "$REQUEST_KEY" --result-file "$CODEX_INPUT_DIR/answer.json" \
  --human-confirmed --operation-id "$ANSWER_OP"
```

`response_sent` 只说明已写入连接，继续观察请求解决或任务继续执行。响应结构与断线后处理见 [提交用户答复](protocol.md#提交用户答复)。

## 人工处理：追加指示或文字答复

适用：用户已给出纠正或文字答复，并已核对原轮次仍在执行。写入 `steer.json`：

```json
{"threadId":"实际会话ID","expectedTurnId":"正在执行的轮次ID","input":[{"type":"text","text":"用户的纠正要求或文字答复"}]}
```

```bash
STEER_OP=$(python3 -c 'import uuid; print(uuid.uuid4())')
python3 "$CODEX_SKILL_DIR/scripts/bridge.py" rpc --method turn/steer \
  --params-file "$CODEX_INPUT_DIR/steer.json" --operation-id "$STEER_OP"
```

返回后继续轮询，确认指示生效。原轮次已经结束时，先核对结果，确认桥接已订阅后，按 [直接派发](cli-examples.md#直接派发) 用 `codex queue` 提交仍需执行的内容。

## 人工处理：中断轮次

适用：用户明确要求停止。写入 `interrupt.json`：

```json
{"threadId":"实际会话ID","turnId":"正在执行的轮次ID"}
```

```bash
INTERRUPT_OP=$(python3 -c 'import uuid; print(uuid.uuid4())')
python3 "$CODEX_SKILL_DIR/scripts/bridge.py" rpc --method turn/interrupt \
  --params-file "$CODEX_INPUT_DIR/interrupt.json" --operation-id "$INTERRUPT_OP"
```

接口返回不等于已停止；核对目标轮次的 `turn/completed` 及 `interrupted` 状态后回报。
