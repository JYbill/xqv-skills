# Bull Board HTTP API

接口依据：[bull-board 路由](https://github.com/felixmosh/bull-board/blob/master/packages/api/src/routes.ts)、[任务列表与字段转换](https://github.com/felixmosh/bull-board/blob/master/packages/api/src/handlers/queues.ts)。实际能力以部署版本为准。

## 认证与请求

以下示例适用于使用 HTTP Basic 的部署，执行前应核对目标部署的认证方式。客户端发送原始密码，服务端密码哈希不是客户端凭据；目标使用其他认证方式时，先核对其认证要求再调整请求。

HTTP 请求统一使用 curl；仅在凭据转义、URL 编码或 JSON 筛选需要逻辑处理时使用 Node.js。以下 Bash 示例在三个变量已加载时执行。临时配置避免把密码直接放入 curl 命令参数；不启用 `set -x`、verbose 或 trace，也不输出配置内容。

```bash
set -euo pipefail
umask 077
bull_tmp_dir=$(mktemp -d "${TMPDIR:-/tmp}/bullboard.XXXXXXXX")
trap 'rm -rf -- "$bull_tmp_dir"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
export BULL_CURL_CONFIG="$bull_tmp_dir/auth.conf"

node --input-type=module <<'JS_AUTH'
import { writeFileSync } from 'node:fs';

for (const key of ['BULL_URL', 'BULL_USER', 'BULL_PASSWORD']) {
  const value = process.env[key];
  if (!value || /[\r\n\0]/.test(value)) {
    throw new Error(key + ' 缺失或包含非法字符');
  }
}
const url = new URL(process.env.BULL_URL);
if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) {
  throw new Error('BULL_URL 必须是无凭据、查询参数和片段的 HTTP(S) 面板地址');
}
const user = process.env.BULL_USER;
const secret = process.env.BULL_PASSWORD;
if (user.includes(':') || secret.includes(':')) {
  throw new Error('此示例保守拒绝含冒号的凭据；先核对目标认证中间件的解析规则');
}
const value = (user + ':' + secret).replaceAll('\\', '\\\\').replaceAll('"', '\\"');
writeFileSync(process.env.BULL_CURL_CONFIG, 'user = "' + value + '"\n', {
  encoding: 'utf8', mode: 0o600, flag: 'wx',
});
JS_AUTH

bull_curl_args=(--silent --show-error --globoff
  --connect-timeout 10 --max-time 60 --config "$BULL_CURL_CONFIG")

# 未知目标时查一次列表；已知目标时改为对应详情路径。
bull_exit=0
bull_http=$(curl "${bull_curl_args[@]}" \
  -D "$bull_tmp_dir/headers" -o "$bull_tmp_dir/body.json" \
  -w '%{http_code}' "${BULL_URL%/}/api/queues") || bull_exit=$?
printf 'curl_exit=%s http_status=%s\n' "$bull_exit" "$bull_http"
# 核对退出码、HTTP 状态、Content-Type 和 JSON 结构后，只提取所需字段。
```

后续命令在同一 Bash 进程内复用参数与临时目录。诊断时保留错误正文，但只输出脱敏摘要；curl 退出码为 0 不表示 HTTP 成功。401/403 停止依赖认证或权限的操作；3xx、200 HTML 不当作 JSON 成功，不盲目跟随跳转。网络或 TLS 错误不通过 `-k` 掩盖。

## 只读查询

| 目标                         | 方法与路径                               |
| ---------------------------- | ---------------------------------------- |
| 队列概况及选中队列的任务列表 | `GET /api/queues`                        |
| 单任务详情与当前状态         | `GET /api/queues/:queueName/:jobId`      |
| 任务日志                     | `GET /api/queues/:queueName/:jobId/logs` |
| 队列 Worker 信息             | `GET /api/queues/:queueName/workers`     |

列表参数为 `activeQueue`、`status`、`page`、`jobsPerPage`，页码从 1 开始。状态使用响应 `statuses` 中的值，例如 `active`、`waiting`、`waiting-children`、`prioritized`、`completed`、`failed`、`delayed`。`latest` 混合多个状态，不用于完整历史分页。

```bash
# bull_queue_name 使用 API 返回的完整 name。
curl "${bull_curl_args[@]}" --fail-with-body --get \
  "${BULL_URL%/}/api/queues" \
  --data-urlencode "activeQueue=$bull_queue_name" \
  --data-urlencode 'status=failed' \
  --data-urlencode 'page=1' \
  --data-urlencode 'jobsPerPage=20' \
  -o "$bull_tmp_dir/jobs.json"
```

`activeQueue` 不会把队列概况裁剪成单个队列；响应中的 `queues` 需要再按完整名称选择。不要假定服务器支持字段筛选参数。

路径中的队列名和任务 ID 必须分别用 Node.js 的 `encodeURIComponent(value)` 编码；例如 `example#documentQueue` 变为 `example%23documentQueue`。不要直接拼接含 `#` 的名称，不对整个 URL 一次性编码。

任务详情响应含 `job` 与 `status`。按需提取 `job.progress`、`returnValue`、`failedReason`、`stacktrace`、`attempts`、`timestamp`、`processedOn`、`finishedOn`。结果字段为 `returnValue`，不是 BullMQ 内部的 `returnvalue`。`processedOn - timestamp` 可能包含延迟调度和重试时间，不能直接当作纯排队耗时。

## 写操作

以下是常见路由，操作前核对部署版本、授权范围和目标状态。新增任务、修改数据、优先级或调度等带请求体的操作，先读取部署对应的 handler/schema 确认字段，不能靠猜测发请求。

| 目标                 | 方法与路径                                                          |
| -------------------- | ------------------------------------------------------------------- |
| 重试一个任务         | `PUT /api/queues/:queueName/:jobId/retry`                           |
| 提前执行一个延迟任务 | `PUT /api/queues/:queueName/:jobId/promote`                         |
| 删除一个任务         | `PUT /api/queues/:queueName/:jobId/clean`                           |
| 暂停／恢复一个队列   | `PUT /api/queues/:queueName/pause`、`/api/queues/:queueName/resume` |
| 批量重试指定状态任务 | `PUT /api/queues/:queueName/retry/:queueStatus`                     |
| 批量清理指定状态任务 | `PUT /api/queues/:queueName/clean/:queueStatus`                     |
| 添加任务             | `POST /api/queues/:queueName/add`                                   |

`readOnlyMode`、`allowRetries`、`allowCompletedRetries` 等字段用于确认候选能力；最终以服务端响应为准。重试完成任务可能重复业务副作用，不能将失败重试授权用于完成任务。清空队列、彻底删除队列、全局暂停和全局恢复需要各自明确的范围，不能作为普通故障排查的默认动作。

写请求保存响应头、正文、HTTP 状态和 curl 退出码，禁止自动重试。按实际 handler 判断预期状态码与响应体，204 可无正文。超时或断连时报告“操作结果不明，可能已执行”；可只读核对同一目标，不重发写请求。

暂停／恢复通过 `isPaused` 回读确认，不承诺 active 任务立即结束。删除前先确认任务存在；删除后 404 需要结合成功响应、同一面板和队列仍可读取等证据判断，不能把权限或连接问题当作删除成功。

## 等待与结果

仅按入口文件约定的显式等待范围跟踪固定的面板、完整队列名和任务 ID。每轮读取详情，不重复枚举所有队列。

- `completed`：本次观察到任务完成；业务是否成功还需按用户目标核对返回结果。
- `failed`：本次观察到任务失败，报告必要的错误摘要，不自动重试。
- `waiting`、`active`、`delayed`、`waiting-children` 等非终态：报告原始状态并在时限内继续；一次执行失败后可能进入延迟重试，不能只靠历史错误字段认定最终失败。
- 404：任务可能已自动清理或目标不可见，报告无法确认最终结果，不推断成功，不创建替代任务。
- 超时：报告最后一次状态和任务标识，停止本地等待，不改变远端任务。

跟随日志也遵守同一总时限；没有新日志不能证明任务完成。只轮询用户要求的内容，不默认将状态等待扩大为日志跟随。
