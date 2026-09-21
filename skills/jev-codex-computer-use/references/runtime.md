# 内置 bridge 的运行接口

本 skill 自带 [bridge.mjs](../scripts/bridge.mjs)，可独立替代 `jev-browser-use`。运行时只使用 Node 内置模块，不需要 npm 依赖；需要支持 `node:util.parseEnv` 的 Node 版本及兼容的 CUA 标签页接口。

## 加载与配置

从当前已加载的 `SKILL.md` 路径解析本 skill 目录，导入其 `scripts/bridge.mjs`。不要从旧 skill 目录导入，也不要把某台机器的用户名写进调用模板。

仅在读取当前页面后仍需 Jev 选择路径时使用以下模板；已确定的按钮、固定流程和确定性等待直接使用 CUA，不加载 bridge 或创建 Jev session。

CUA 首次调用已经按工具文档完成，并持有目标标签页 `taskTab` 后，在同一 CUA REPL 中运行下列模板。`bridgeUrl` 必须替换为实际模块的绝对 `file://` URL；目标、origin 和控件名必须替换为当前任务中核实的值。

```js
var jev = await import(bridgeUrl);
var jevConfig = await jev.loadConfig();
var jevSession = jev.createSession(taskTab, {
  ...jevConfig,
  allowedOrigins: ['https://example.com'],
  maxSteps: 12,
  maxMs: 45000,
  minConfidence: 0.55
});
var jevTask = {
  goal: '进入订单列表，找到并展开订单 TEST-1042 的详情；看到该订单编号和明细后停止，不修改订单。',
  policy: {
    click: true,
    allowNames: ['订单', '下一页', 'TEST-1042', '展开详情'],
    scrollDirections: ['down', 'up'],
    scrollAmount: 1,
    denyNames: [/删除|付款|取消订单/],
    requireCodexNames: [/发送|发布|保存/]
  }
};
var outcome = await jevSession.run(jevTask);
nodeRepl.write({status: outcome.status, metrics: outcome.sessionMetrics});
```

给这一 CUA 调用设置 `timeout_ms: 60000`。读取 outcome 后用当前工具文档支持的 API 获取新页面状态并验收。需要诊断时读取 `outcome.history`、`outcome.state`、`outcome.error`，不要默认打印整页私有文本或保存 trace。

`loadConfig()` 优先读取 `~/.config/jev-codex-computer-use/config.json`；仅当该文件不存在时兼容 `~/.config/jev-browser-use/config.json`。返回 `envFile`、`provider`、`model`，不返回 API key；缺少 `config.apiKey` 是正常现象。可用 `loadConfig({configDir})` 指定配置根目录，主要用于隔离测试或自定义部署。保留返回配置，不擅自覆盖；凭证由 bridge 从指定 dotenv 文件读取。配置维护见 [配置说明](provider-configuration.md)，不要输出 dotenv 或原始 HTTP 错误体。

## 复用、换目标与等待

- 同一子目标中由 Codex 输入文字或处理组件后，先读取当前状态：操作已明确则直接 CUA；仍需 Jev 选择路径才执行 `await jevSession.run(jevTask)`。保留 session 不代表必须继续调用。
- 独立新子目标且仍需 Jev 选择：先记录 `jevSession.metrics()`，再对同一个 `taskTab` 调用 `createSession()` 创建新会话；新目标有自己的完成条件。
- `session.reset()` 清除 Jev 历史和累计指标；不等于 `mcp__cua_repl.js_reset`，通常无需使用任何 reset。
- 等待可观察的加载条件：`await jev.waitForState(taskTab, {allowedOrigins, includes, excludes, timeoutMs: 30000, pollMs: 1000})`。`includes` 和 `excludes` 是子串数组，应绑定当前任务。返回 `matched` 或 `timeout`，等待不调用 Jev API。

## 候选分流与指标

候选经过生成、过滤和去重后：一个候选直接执行并返回 `action_executed`，零个候选直接返回 `no_candidates`，均不请求模型；多个候选才请求 Jev。Jev 可用 `HANDOFF` 返回 `handoff`，仅表示交回控制权；不再提供 DONE 选项。所有状态只说明操作或停止原因，任务是否完成统一由 Codex 主模型读取当前状态后评估。单候选仍在执行前重新读取页面，页面变化时不执行旧动作。

直接操作的历史使用 `choice: "DIRECT"`、`provider: null`、`model: null`、`confidence: null`、`apiMs: 0`。`sessionMetrics.directActions` 统计接口正常返回的直接操作；`decisions` 不计直接操作，`executedActions` 统计两种路径的已执行动作。

## 动作记录与异常恢复

调用动作接口前，session 已保存该记录；接口返回后更新同一条记录的 `executionStatus`：

- `not_executed`：尚未调用动作接口，例如执行前页面校验失败；`executed: false`。
- `executing`：动作接口调用中；`executed: null`。
- `executed`：动作接口正常返回；`executed: true`，不代表任务完成。
- `unknown`：动作接口抛错，可能已经产生部分或全部效果；`executed: null`，停止并由 Codex 检查，不自动重试。

`session.history()` 在动作调用中即可读取记录。`sessionMetrics.unknownActions` 单独统计结果未知的动作，不计入 `executedActions` 或 `directActions`。记录保存在当前内存会话中，不保证 REPL 重置或进程退出后恢复。

页面读取失败返回 `state_read_error`，origin 无法确认、未授权跳转或快照超限返回 `state_validation_error`。这些异常立即停止循环，保留动作历史、累计指标及最后一次通过校验的 `state`，并设置 `stateMayBeStale: true`；没有可用状态时 `state` 为 `null`。点击接口报错也设置该标记。Codex 必须获取新页面再判断，不能把旧状态当作当前页面。

点击已执行但后续读取失败时，记录仍为 `executed`，页面错误放在返回的 `status` / `error` 中，不改写为动作失败。以上结构化异常处理适用于 `run` / `session.run`；独立的 `waitForState` 仍会抛出读取或校验异常。

## 已知能力与限制

bridge 提供 `loadConfig`、`createSession`、`run`、`availableActions`、`discoverActions`、`waitForState` 和底层 `decide`。日常任务使用会话接口，不另写 API 客户端。

支持唯一名称的点击、有限滚动、部分按键和 reload；没有文字输入、原生桌面应用、iframe 专用接口、canvas、拖拽或上传动作。Codex 按当前 CUA 文档处理这些操作。不要让 Jev 生成选择器、URL、坐标或任意代码。

`allowedOrigins` 在读取状态与执行前后检查，但不能阻止一次已授权点击发生的所有外部副作用。候选动作本身也必须经过授权范围筛选。

`maxMs` 限制后续操作，不能中断已在运行的浏览器调用。累计 `sessionMetrics.apiMs` 包含决策请求耗时；`elapsedMs` 是 Jev 循环耗时，不含全部 Codex 接管与工具间等待，不能当作端到端时间。
