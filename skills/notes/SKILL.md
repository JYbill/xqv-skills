---
name: notes
description: 当用户明确要求补注释、调整注释、review 注释质量、沉淀注释规范，或需要判断复杂逻辑、循环块、变量组、状态分支、数据转换、SQL 口径、React Hook 副作用、Node.js 后台编排中哪些位置值得注释时，使用这个 skill。目标是让注释解释代码块意图、变量职责和业务边界，不给简单代码逐行配旁白。
---

# notes

这个 skill 用于写代码注释。注释要帮助后来读代码的人理解关键意图，而不是把代码翻译成中文。

只有任务涉及注释治理时才使用它。普通 React、后端或 SQL 开发任务不应仅因为出现这些技术栈就触发；如果用户要求检查当前改动是否缺少必要注释，可以使用。

## 规范读取要求

执行注释相关任务时，必须先读取对应的 `references` 文档，再判断是否要写注释、写什么注释。

- 所有任务都先读 `references/common.md`。
- 涉及前端、React、Hook、组件、事件处理、渲染分支时，再读 `references/frontend.md`。
- 涉及 Node.js 后台、controller、service、SQL、任务、队列、外部接口时，再读 `references/backend.md`。

## 规则分层

- `references/common.md`：前后端无关的通用注释规则，包括 JSDoc、for 循环、复杂判断、字段映射、空行分组和反面示例。
- `references/frontend.md`：前端 React 注释规则，包括 Hook、副作用、事件处理函数和渲染分支。
- `references/backend.md`：Node.js 后台注释规则，包括 controller、service、SQL、定时任务、队列和外部副作用。

## 执行原则

先按通用规则判断，再叠加具体场景规则。注释要解释关键意图、业务边界、状态优先级、副作用原因、数据口径、循环块产出或变量职责；不要写只复述代码表面行为的注释。
