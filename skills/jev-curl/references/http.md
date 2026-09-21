# HTTP 请求与返回

官方接口：`POST https://api.typesafe.ai/v1/systemone`。使用 Bearer API Key 和 JSON 请求体，默认模型 `jev-latest`。

## 最小调用示例

以下为合成文本。实际任务替换 `state` 和问题；密钥须已导出到执行进程，示例不包含设置或打印密钥的命令。

```bash
(
  set +x
  : "${TYPESAFE_API_KEY:?请先在执行环境中配置 TYPESAFE_API_KEY}"
  printf 'Authorization: Bearer %s\n' "$TYPESAFE_API_KEY" |
    curl --silent --show-error --fail-with-body \
      --connect-timeout 10 --max-time 30 \
      --request POST 'https://api.typesafe.ai/v1/systemone' \
      --header @- \
      --header 'Content-Type: application/json' \
      --write-out '\nHTTP_STATUS=%{http_code}\n' \
      --data-binary @/dev/fd/3 3<<'JSON'
{
  "model": "jev-latest",
  "state": "我需要修改上个月发票上的公司名称。",
  "questions": {
    "route": {
      "type": "choice",
      "instructions": "应将这条请求交给哪个团队？",
      "criteria": {
        "billing": "发票、付款或退款",
        "technical": "软件故障或接口问题",
        "other": "不属于以上类别"
      }
    }
  }
}
JSON
)
```

该示例适用于 Bash/zsh：认证头经标准输入传给 curl，请求体用独立文件描述符，避免把密钥展开到进程参数。其他 shell 可用受限权限的临时请求文件传递 JSON，完成后清理。不要启用重定向跟随或将认证头发送到其他域名。

`--fail-with-body` 让 HTTP 错误返回非零退出码并保留错误正文；末尾 `HTTP_STATUS` 是本地附加状态行，不属于响应 JSON。需要程序解析时将响应体与状态码分别保存，避免直接对混合输出做 JSON 解析。错误报告去除私密输入和凭据。

## 问题与结果

请求顶层字段为 `model`、`state`、`questions`。`state` 可为字符串、对象或数组；`questions` 是以自定 ID 为键的问题对象。

| 类型 | 请求中的 criteria | answers[问题ID] 中的结果 |
| --- | --- | --- |
| `choice` | 必填对象：候选键映射到描述，最多 255 个候选 | `choice`、`probabilities`、`confidence` |
| `noul` | 可省略；提供时用 `true`、`false` 两个键定义含义 | `noul`，范围 0～1，无独立 confidence |
| `score` | 必填有序数组，2～10 个等级描述 | `score`、`legend`、`probabilities`、`confidence` |

三个类型均需要 `type` 和 `instructions`。例如同一请求中可增加：

```json
{
  "urgent": {"type": "noul", "instructions": "请求是否明确要求紧急处理？"},
  "urgency": {
    "type": "score",
    "instructions": "请求的紧急程度如何？",
    "criteria": ["未提及期限", "有明确期限但不紧急", "明确要求立即处理"]
  }
}
```

此片段是 `questions` 的内容，不是完整请求。响应顶层包含 `model`、`answers`、`usage`；每个 answer 的 `type` 应匹配请求。Score 可落在等级之间，按 `legend` 的等级编号解释。Noul 接近 0.5 表示是非不确定，不表示程度中等。

## 按需核对

- [官方 HTTP API](https://docs.typesafe.ai/api)：字段、返回类型与错误码。
- [官方模型列表](https://docs.typesafe.ai/models)：需要固定版本或更换模型时读取。
- [官方 agent skill](https://docs.typesafe.ai/agent-skill)：上游 skill 来源及用途。
