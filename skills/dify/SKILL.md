---
name: difyctl
description: 使用 difyctl CLI 管理 Dify 应用、工作区、成员和运行任务。适用于涉及 difyctl，或需要通过命令行操作 Dify 实例的任务。
---

# difyctl

difyctl 提供自描述帮助信息，不要猜测命令。

## 查找可用命令

1. 每次会话首次使用时，阅读 `difyctl help agent`，了解输出格式、认证、退出码、错误响应、人工介入（HITL）和重试规则。CLI 版本变化后重新读取。
   执行命令时使用 `-o json`（或 `-o yaml`）获取结构化结果；失败时同时检查退出码和标准错误中的错误响应。
   区分 `studio-app`（Studio 中管理的应用定义，用于导出、迁移等操作）与 `app`（已发布的应用，用于运行和查看）。
2. 阅读完整的精简命令索引：
   `difyctl help -o json --compact`
   每个条目仅包含 `command`、`description` 和 `effect`。
3. 将请求拆成必要步骤，为每一步选择对应命令。需要组合多条命令本身不代表请求不受支持，也不构成询问理由。
4. 执行每条选定命令前，查看其详细信息：
   `difyctl help <path> -o json`
   如果命令路径包含多个词，应将它们作为独立的 shell 参数传入；不要用引号包裹返回的整个路径。
   该 JSON 是位置参数、选项、示例、`effect` 和 `agentGuide` 的权威依据。不得跳过这一步：精简命令索引不包含位置参数或选项，未查看详情就使用任何选项都属于猜测。

通常无需读取完整命令树；排查帮助信息或全局调用规则问题时再按需读取。只有检查过精简命令索引后，才能报告某项请求不受支持。仅在目标、必要参数或操作范围存在影响结果的实质歧义时询问。

## 容易忽略的一点：HITL 暂停不代表失败

运行任务可能暂停以等待人工输入。此时命令以**退出码 0** 退出，并输出 `paused` JSON 数据。这表示命令执行成功，但任务仍在等待处理，并非崩溃。
检查结构化结果中的状态，不能仅凭退出码 0 报告任务完成。遇到 `paused` 时，明确报告“等待人工输入”，保留 `form_token`、`workflow_run_id` 等恢复所需信息，并向用户说明待填写或决定的内容。
不得自行代填需要用户决定的内容。取得必要输入后，查阅恢复命令的详细帮助，并按照返回数据中的说明恢复运行。

## 处理重试与结果不明的操作

以当前 `difyctl help agent` 和命令详情中的重试规则为准。CLI 会对符合条件的 GET、PUT、DELETE 请求自动重试，但不会自动重试 POST、PATCH。
命令超时、连接中断或响应丢失，并不证明服务端未执行。对可能产生副作用的操作，先用可用的查询命令核对状态；无法核实时报告结果不明，不要直接重复执行整个命令。

## 执行任何写入或破坏性操作之前

根据已查看命令的 `effect` 判断操作影响，并核对目标和影响是否在用户明确授权的范围内。已有明确授权时不重复询问；缺少授权，或目标、影响超出授权范围时，先说明具体操作及影响并取得确认，再执行。

---

## 来源与更新

本文件是自维护的中文适配版，来源于 [Dify 官方技能模板](https://github.com/langgenius/dify/blob/main/cli/src/help/skill-template.ts)，并参考[官方 CLI 文档](https://github.com/langgenius/dify/blob/main/cli/README.md)和 [agent 指南](https://github.com/langgenius/dify/blob/main/cli/src/help/topics.ts)。上游核对日期：2026-09-20。

CLI 升级后，使用 `difyctl version` 查看当前版本，并用 `difyctl skills install --stdout` 获取该版本内置的技能正文，对照差异更新中文适配版。不要用生成的原文直接覆盖本文件。
注意：不带参数的 `difyctl skills install` 仅预览安装位置，不会更新技能文件。
