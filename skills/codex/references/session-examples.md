# Codex 会话管理调用模板

用于独立查询、归档，或持续追踪时核对状态。先按 [准备参数](cli-examples.md#准备参数) 设置技能目录、私有输入目录和实际会话 ID；单纯查询或归档不要求选择派发模式。

## 查询会话与历史

适用：用户要求查询，或持续追踪需要核对状态。通过桥接 RPC 查询前先按 [连接模板](tracking-examples.md#持续追踪连接) 确认桥接运行；只读查询不需要 `--operation-id`，也不需要 `thread/resume`。

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

适用：用户要求归档。先按 [查询会话与历史](#查询会话与历史) 用 `thread/read` 核对目标，再直接调用 CLI：

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
