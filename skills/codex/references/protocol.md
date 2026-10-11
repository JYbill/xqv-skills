# 协议与待处理请求

## 连接和配置

桥接直接连接 `$CODEX_HOME/app-server-control/app-server-control.sock`，使用 Unix socket 上的 WebSocket（HTTP Upgrade，客户端掩码帧，支持分片与 ping/pong）。手机 SSH 的 `codex app-server proxy` 转发的也是这一端点的 WebSocket 字节流，不能把它当成 JSONL stdio 服务。桥接自身与短时查询命令之间使用本地 Unix socket 和 JSONL，不暴露网络监听。

后台服务可能缓存配置；用户修改配置后，用 `config/read` 和创建/恢复响应核对生效值，不自行重启正在执行的服务。

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

把准确响应对象写入私有 JSON 文件：

```bash
python3 "$CODEX_SKILL_DIR/scripts/bridge.py" respond --request-key '<poll返回的key>' --result-file <响应JSON路径> --human-confirmed --operation-id <唯一操作ID>
```

`--human-confirmed` 是对已获得用户答复的声明，不是获取许可的替代品。脚本只能核对请求是否属于当前连接且未解决，不能判断自然语言授权是否充分。

## 故障处理

- `connected=false`：原服务任务可能仍运行。先看事件和历史，定位连接失败原因；不重建任务、不重发未确认的写操作。
- 重建桥接前终止旧桥接（核对 PID/命令），确认不会丢失尚未响应的请求，再运行 `start`。后台 Codex 服务无需跟着停止。历史事件仍可查询，旧请求标为状态未知。
- 客户端查询超时：用相同游标重新查询。写操作重试遵循 SKILL.md 第 2 节；RPC 40 秒超时后的响应记录为 `bridge/lateResponse`，按 RPC ID 和内容核对。
- 协议版本不匹配：查看 `codex --version`、`codex app-server daemon version` 和当前 schema，报告不兼容；不自动更新或降级运行中的服务。
- `thread/resume` 写入冲突：可能是桌面 App 独立服务持有会话；应切换到正确入口或等用户决定交接，不能删锁。

## 已验证与未验证

实现目标是一个持久连接接收事件，短时查询读取增量；手机与其共享后台服务。创建技能时已通过无模型调用的真实连接/当前会话查询检查及模拟协议测试。后续用户授权的真实测试已成功创建任务并收到带 `questions` 的异步提问；随后另一客户端提交“简短段落”，桥接收到用户消息、最终答复和 `turn/completed`；测试端没有代用户回答。手机实时引导、跨客户端审批交接、长时间断线恢复和 Claude Desktop 实际工具循环，需要接入后的端到端验证。

来源：
- https://learn.chatgpt.com/docs/app-server
- 本机 `codex app-server generate-json-schema` 的输出（CLI 0.162.1）；以部署时版本为准。
