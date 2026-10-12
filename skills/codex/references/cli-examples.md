# Codex CLI 调用模板

派发新任务前，先按 [SKILL.md](../SKILL.md#先选择模式) 确定用户选择的模式。以下模板按场景选用，不是从头到尾依次执行的脚本。模型、审批和沙箱沿用现有配置；目录信任、未知结果重试等约束见 SKILL.md。

- 仅派发：使用本文件的 [新会话或已有会话](#仅派发新会话或已有会话) 模板。
- 持续追踪：使用 [追踪模板](tracking-examples.md)，包含连接、派发、续接、轮询和人工处理。
- 查询或归档：使用 [会话管理模板](session-examples.md)。

## 准备参数

将技能路径替换为当前加载的目录。下面的 `THREAD_ID`、`TURN_ID`、`REQUEST_KEY` 必须来自实际响应，不能保留占位文字执行。

```bash
export CODEX_SKILL_DIR="/absolute/path/to/codex"
umask 077
CODEX_INPUT_DIR=$(mktemp -d)
THREAD_ID="实际会话ID"
```

本文件展示的 JSON 应写入对应文件。用文件工具或 JSON 序列化写入用户原文，不把原文拼进 shell；换行等字符按 JSON 格式编码。重试需要复用的输入文件在结果核对前保留，其余用完清理。

## 仅派发：新会话或已有会话

适用：用户选择模式 2。主助手直接执行原生 CLI，不启动桥接，也不运行派发包装脚本。已有会话直接按下方 [直接派发](#直接派发) 提交任务。

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

从返回的 `thread.id` 保存 `THREAD_ID`。这一段仅用于 CLI 尚未覆盖的会话创建，不发送模型任务；随后按下方 [直接派发](#直接派发) 提交。

## 直接派发

适用：两种模式共用。模式 1 先完成桥接订阅，提交后继续轮询；模式 2 提交成功后结束回复。

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
