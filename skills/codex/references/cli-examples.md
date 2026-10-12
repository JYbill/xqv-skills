# Codex CLI 调用模板

先按 [SKILL.md](../SKILL.md#先选择模式) 确定用户选择的模式。以下模板按场景选用，不是从头到尾依次执行的脚本。模型、审批和沙箱沿用现有配置；目录信任、未知结果重试等约束见 SKILL.md。

## 准备参数

将技能路径替换为当前加载的目录。下面的 `THREAD_ID`、`TURN_ID`、`REQUEST_KEY` 必须来自实际响应，不能保留占位文字执行。

```bash
export CODEX_SKILL_DIR="/absolute/path/to/codex"
umask 077
CODEX_INPUT_DIR=$(mktemp -d)
THREAD_ID="实际会话ID"
```

本文件展示的 JSON 应写入对应文件。用文件工具或 JSON 序列化写入用户原文，不把原文拼进 shell；换行等字符按 JSON 格式编码。重试需要复用的输入文件在结果核对前保留，其余用完清理。

## 持续追踪：连接

适用：用户选择模式 1，或明确要求通过桥接查询、管理已有会话。

```bash
python3 "$CODEX_SKILL_DIR/scripts/bridge.py" start
python3 "$CODEX_SKILL_DIR/scripts/bridge.py" status
```

确认 `connected=true` 且初始化没有错误。两条命令只连接既有 App Server，不创建模型任务。桥接退出后，新的 RPC 需要先重新 `start`；读取已保存事件的 `poll` 不需要重新启动。

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

保存 `result.thread.id`，更新 `THREAD_ID`。`thread/start` 已为这个桥接连接订阅会话事件；随后按 [直接派发](#直接派发) 调用原生 `codex queue`。CLI 返回后进入轮询，不结束追踪。

从 `turn/started` 或轮次历史核对实际 turn ID；CLI 输出的 queued message ID 不是 turn ID。创建会话的 RPC 重试复用原操作 ID 和原文件；CLI 派发不使用操作 ID，超时后先核对会话，不能重复提交。

## 持续追踪：续接已有会话

适用：需要重新接收原会话的实时事件。先按“查询会话与历史”读取状态，再写入 `resume.json`：

```json
{"threadId":"实际会话ID","excludeTurns":true}
```

```bash
RESUME_OP=$(python3 -c 'import uuid; print(uuid.uuid4())')
python3 "$CODEX_SKILL_DIR/scripts/bridge.py" rpc --method thread/resume \
  --params-file "$CODEX_INPUT_DIR/resume.json" --operation-id "$RESUME_OP"
```

恢复连接不等于发送任务。仍有活跃轮次时直接追踪；需要新一轮且原轮次已结束时，保持订阅后按 [直接派发](#直接派发) 使用 `codex queue`。

## 持续追踪：读取进展

适用：任务已派发，或桥接已退出但尚有已保存事件未读。

```bash
CURSOR=0
python3 "$CODEX_SKILL_DIR/scripts/bridge.py" poll \
  --thread "$THREAD_ID" --cursor "$CURSOR" --event-limit 50
```

首次接入用 `0`；后续把 `CURSOR` 更新为返回的 `cursor`。省略 `--event-limit` 也是 50，范围为 1～200。检查 `events`、`urgent_events`、`pending_requests`、`question_messages`；跨页紧急事件按事件游标去重。`has_more=true` 时继续读取，不能因为已看到完成事件就丢弃尚未读取的工具结果。单次内部等待最多 100 秒，客户端超时为 110 秒，宿主工具超时应大于 110 秒。主 Agent 或宿主可能终止长时间没有输出的调用；未收到返回时保留原游标，核对状态后再查询，不重复派发。内部超时不代表完成，按 [轮询协议](protocol.md#增量轮询) 处理返回原因。

## 仅派发：新会话或已有会话

适用：用户选择模式 2。模式 1 也复用“直接派发”命令，但先完成桥接订阅，并在提交后继续轮询。主助手直接执行原生 CLI，不启动桥接，也不运行派发包装脚本。已有会话跳过创建步骤。

### 新会话的创建

当前已验证的 `codex queue` 需要已有会话 ID。新会话须先核对目录与信任，再用一次性 Python 调用 `thread/start`；复用 `transport.py` 的 WebSocket 传输类不会启动后台服务或写 SQLite。创建结果未知时先查会话列表，不自动重复创建。

`create.json`：

```json
{"cwd":"/absolute/project/path"}
```

```bash
python3 - "$CODEX_SKILL_DIR" "$CODEX_INPUT_DIR/create.json" <<'PY'
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]) / "scripts"))
from config import HOME, dumps
from transport import UnixWebSocket
ws = UnixWebSocket(HOME / "app-server-control/app-server-control.sock")
ws.sock.settimeout(40)
messages = iter(ws)
def rpc(request_id, method, params):
    ws.write(dumps({"id": request_id, "method": method, "params": params}) + "\n")
    ws.flush()
    for raw in messages:
        response = json.loads(raw)
        if response.get("id") == request_id and "method" not in response:
            if "error" in response:
                raise RuntimeError(dumps(response["error"]))
            return response["result"]
    raise RuntimeError("连接断开；核对会话列表后再决定，勿重复创建。")
try:
    rpc(1, "initialize", {"clientInfo": {"name": "codex_skill_create", "version": "1"}})
    ws.write(dumps({"method": "initialized", "params": {}}) + "\n")
    ws.flush()
    params = json.loads(Path(sys.argv[2]).read_text())
    print(dumps(rpc(2, "thread/start", params)), flush=True)
finally:
    ws.terminate()
PY
```

从返回的 `thread.id` 保存 `THREAD_ID`。这一段仅用于 CLI 尚未覆盖的会话创建，不发送模型任务。

### 直接派发

任务正文写入 `task.json`，不把用户原文直接拼进 shell：

```json
{"text":"用户授权的任务、约束和验收条件"}
```

```bash
TASK_TEXT=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["text"], end="")' "$CODEX_INPUT_DIR/task.json")
codex queue --thread "$THREAD_ID" --message "$TASK_TEXT" \
  --remote "unix://${CODEX_HOME:-$HOME/.codex}/app-server-control/app-server-control.sock"
```

变量被双引号引用，正文中的反引号和 `$()` 不会再次执行；命令替换会去掉正文末尾的换行。若任务要求逐字保留末尾换行，主助手应使用执行工具的参数数组直接传入正文。

正常退出且返回 `Queued message ...` 表示提交成功，模式 2 随后回报“已派发”并结束；模式 1 继续轮询。超时或报错先核对原会话；CLI 没有桥接的操作去重保护，不能盲目重发。为执行工具设置合理超时，但不能把工具超时等同于提交失败。

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

返回后继续轮询，确认指示生效。原轮次已经结束时，先核对结果，确认桥接已订阅后，用 `codex queue` 提交仍需执行的内容。

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

## 查询会话与历史

适用：用户要求查询，或持续追踪需要核对状态。通过桥接 RPC 查询前先确认桥接运行；只读查询不需要 `--operation-id`，也不需要 `thread/resume`。

`read.json`：

```json
{"threadId":"实际会话ID"}
```

```bash
python3 "$CODEX_SKILL_DIR/scripts/bridge.py" rpc --method thread/read \
  --params-file "$CODEX_INPUT_DIR/read.json"
```

默认查询会话信息和状态。只有确实需要全部历史时才加入 `"includeTurns":true`；历史较多时使用分页接口。`history.json`：

```json
{"threadId":"实际会话ID","limit":20,"itemsView":"full","sortDirection":"desc"}
```

```bash
python3 "$CODEX_SKILL_DIR/scripts/bridge.py" rpc --method thread/turns/list \
  --params-file "$CODEX_INPUT_DIR/history.json"
```

从 `result.data` 读取轮次；有 `nextCursor` 时，把其原值作为 JSON 字符串写入下一次参数的 `cursor`。历史分页游标是服务端字符串，与 `poll` 的整数事件游标不同；`limit` 按轮次计数，不是事件条数。这两个接口返回历史记录，不能当成完整实时事件流或待处理审批清单。

## 归档会话

适用：用户要求归档。先用 `thread/read` 核对目标，再直接调用 CLI：

```bash
codex archive "$THREAD_ID" \
  --remote "unix://${CODEX_HOME:-$HOME/.codex}/app-server-control/app-server-control.sock"
```

CLI 不使用 `--operation-id`。提交结果不明时先查询归档状态，不自动重发。

写入 `archived-list.json`：

```json
{"archived":true,"limit":20}
```

```bash
python3 "$CODEX_SKILL_DIR/scripts/bridge.py" rpc --method thread/list \
  --params-file "$CODEX_INPUT_DIR/archived-list.json"
```

在 `result.data` 中核对目标 ID；有后续页时继续按返回游标查找，确认后再回报。仅归档不恢复会话、不发送新轮次。
