# 问题设计与组合方法

用于设计新的 Jev 功能、调整问题含义或组合多个判断。请求字段和 curl 用法见 [HTTP 请求与返回](http.md)；这里只描述设计方法，不代表已经调用服务或验证业务效果。

## 先确定结果如何被使用

从最终行为倒推：代码需要哪些判断、每个判断需要什么材料、前后是否有依赖，以及无匹配或材料不足时如何处理。确定规则、检索、计算和执行交给代码；需要理解语义的局部判断交给 Jev。模式只是起点，不要求把功能套进固定分类。

例如“挑选符合需求的资料”：代码检索候选，Jev 判断各候选与需求的相关程度，代码排序并展示。若还需核验某个说法，则另取该说法及原文证据来判断，不能把相关程度当成事实支持度。

## 设计每个问题

| 所需结果 | 设计方式 | 注意事项 |
| --- | --- | --- |
| 从已知候选中选一个 | `choice` | 概率比较的是这些候选；遗漏的值无法被选中 |
| 判断条件是否成立 | `noul` | 多个标签可能同时成立时，每个标签单独提问；接近 0.5 表示不确定，不是程度中等 |
| 评估某个维度的程度 | `score` | 等级有序、具体且各自可独立理解；逐项排序使用可比较的标准，不能把 Choice 的相对概率当成通用评分 |

- `state` 提供原文、对象身份、关系、适用规则与当前事实；上下文复杂时使用有名称的 JSON 字段，并在问题中明确引用路径，如 `ticket.messages[0].text`。
- `instructions` 写完整判断，`criteria` 解释候选或等级。问题 ID 不传递判断含义；不要只靠 `is_urgent` 等 ID 告诉模型判断什么。
- 每题聚焦一个连贯判断；需要独立使用的维度分别提问，但不要拆掉关系。例如判断“证据是否支持说法”必须同时给出说法和证据。聚焦不等于只能问字面事实，也不限制为一句话。
- 需要定义、对照、排除条件或示例时，可用结构化对象或数组表达指令；对应字段的可用结构以当前 API 文档为准。
- 评分等级描述可观察的情形，避免只有“差／一般／好”，或只能依靠上一等级理解的“更多／更好”。标准改变后，旧分数不再直接可复用。
- 候选不完整时区分“没有匹配项”和“信息不足”。选择原文值前检查候选覆盖；只有存在性判断本身也有用途时，才额外增加该问题，不为每次选择固定多加一题。

## 组合方法

### 独立合并与分支预判

同一状态下可独立回答的问题放在一次请求中。若某个分支可能用到的材料已经齐全，可提前提出带明确假设的问题，返回后由代码决定使用哪些答案。各问题不能看到彼此的答案。

例如工单分流时，同时判断类别，以及“假设按故障工单处理，现有描述表明影响程度如何”。代码只在类别为故障时使用影响程度；未采用分支的不确定结果不应触发复核或改变最终处理。

不要把所有可能分支无限展开。额外问题仍消耗 token；根据分支使用频率、请求预算和实际耗时决定是否预判。

### 依赖结果时分阶段

只有前一次答案才能确定需要检索什么、如何构造新状态或下一轮候选时，安排后续请求。例如先选择产品，再由代码查询该产品的实际配置，最后判断哪些配置符合需求。后一题不能在缺少配置资料时假装与前一题独立。

每阶段检查返回结构及候选有效性，满足业务条件后再继续；无匹配、材料不足或调用失败走各自的处理路径，不能当成正常候选继续执行。

### 评分与组合规则分开

保留各维度原始分数、等级含义及对应材料，再由代码计算权重、阈值、排序和视图。不同量纲需要先按各自等级定义转换；不要默认所有 Score 都是百分制。

允许相互补偿的偏好可加权求和，例如资料的相关程度和可读性；“任一严重违规即排除”应使用独立条件，不能被其他维度高分抵消。证据和问题含义不变时，只调整权重或展示筛选无需重新调用；有标注结果时，原始判断也可作为传统机器学习的特征，需另行验证效果。

### 核验与升级处理

将具体说法或字段与它的证据一起交给 Jev 核验，代码决定通过、补充资料、转人工或交给推理模型进一步分析。未提供给模型的证据不能由置信度补足。

Choice／Score 的 confidence 反映分布集中程度，不等于事实正确率或整个流程的成功率；多个都可接受的选项也可能分散概率。根据实际错误后果和样本评估处理策略，不给所有任务套用同一阈值，也不因为无害偏好选择的低置信度一律阻断。

### 随状态更新判断

代码保存目标、实际观察和当前步骤，Jev 根据这些信息判断下一步。推断结果与已观察事实分别保存，不把“可能已完成”写成“已完成”。

在应用答案前检查相关状态是否仍有效，例如订单状态已变化或候选已失效；材料或选项改变时更新后重新判断。循环应有完成条件、步数或时间预算，以及无法继续时的退出方式。选择操作之后仍由代码执行并核验结果；浏览器执行交给相应浏览器 skill。

## 按功能选择起点

以下是官方 skill 提供的主要方向。新工作流选择最接近的一项阅读，无需一次加载全部 cookbook；具体字段和示例阈值仍要核对并验证。

| 功能 | Jev 与代码如何配合 | 官方参考 |
| --- | --- | --- |
| 路由与参数选择 | Jev 从已有处理器和参数候选中选择，代码验证参数并调用；材料已齐全时预判分支 | [Function calling](https://docs.typesafe.ai/cookbooks/function_calling)、[Fan-out](https://docs.typesafe.ai/patterns/fan-out) |
| 候选提取与结构恢复 | 代码找出值或原文片段，Jev 选择，代码复制、规范化或组装；不要求 Jev 生成任意文本 | [Value extraction](https://docs.typesafe.ai/cookbooks/pre_parsed_value_extraction_cookbook)、[Structure recovery](https://docs.typesafe.ai/cookbooks/autoformat) |
| 重排序与分层分类 | 代码检索候选，Jev 按一致标准判断相关程度，代码排序；类别过多时考虑分层，并检查前层误判影响 | [Reranking](https://docs.typesafe.ai/cookbooks/rerank_typesafe)、[Hierarchical classification](https://docs.typesafe.ai/cookbooks/hierarchical_classification) |
| 多维评分与复用 | Jev 产生维度分数，代码调整权重和视图；有标注数据时可探索特征用途 | [Composite scoring](https://docs.typesafe.ai/patterns/composite-scoring)、[Feature discovery](https://docs.typesafe.ai/cookbooks/autoresearch_feature_discovery) |
| 证据核验与升级 | Jev 判断证据支持程度，代码将失败或不确定案例转后续处理 | [Citation checks](https://docs.typesafe.ai/cookbooks/citation_check)、[Extraction cascades](https://docs.typesafe.ai/cookbooks/sde_cascade) |
| 动态状态驱动 | 代码维护目标与观察，Jev 判断下一步，应用前检查状态有效性 | [Building guide](https://docs.typesafe.ai/concepts/how-to-build-with-system-one) |

## 示例：工单分流与故障分支预判

以下是合成数据的请求体示例，使用主文件规定的 curl 方式发送；仅展示设计，不包含真实调用结果。

```json
{
  "model": "jev-latest",
  "state": {
    "ticket": {"text": "今天付款成功后仍无法下载文件，刷新也没用，之前下载正常。"}
  },
  "questions": {
    "route": {
      "type": "choice",
      "instructions": "根据 ticket.text 中用户需要解决的主要问题，选择处理团队。付款只是背景且主要问题是功能不可用时，选择技术支持。",
      "criteria": {
        "technical": "处理功能故障和使用异常",
        "billing": "处理发票、扣款或退款问题",
        "other": "需求明确，但不属于上述团队",
        "insufficient": "材料不足，无法判断用户主要需求"
      }
    },
    "impact": {
      "type": "choice",
      "instructions": "假设该工单按故障处理，仅根据 ticket.text 描述选择影响范围；未说明范围时选择信息不足。",
      "criteria": {
        "all": "用户明确报告整个服务无法使用",
        "partial": "用户报告具体功能无法使用，未报告整个服务不可用",
        "minor": "用户明确报告功能仍可使用，仅有体验问题",
        "insufficient": "无法根据描述判断影响范围"
      }
    }
  }
}
```

代码先检查请求和答案结构，再读取 `route`。只有技术支持分支使用 `impact`；其他分支忽略它。`route` 信息不足时补充材料，不能当作 `other`；技术支持分支的 `impact` 信息不足时只表明影响范围待补充。两题都基于现有文本，不互相引用答案。若后续需要该用户的订单记录，由代码查询后再构造新请求，不能在此示例中臆测订单状态。

## 官方设计资料

- [TypeSafe 官方 skill](https://github.com/typesafe-ai/skills/blob/main/skills/typesafe-ai/SKILL.md)：本文件的设计方法来源。
- [State](https://docs.typesafe.ai/concepts/state)、[Primitives](https://docs.typesafe.ai/primitives)：输入组织与类型选择；具体指导见 [Choice](https://docs.typesafe.ai/primitives/choice)、[Noul](https://docs.typesafe.ai/primitives/noul)、[Score](https://docs.typesafe.ai/primitives/score)。
- [Confidence](https://docs.typesafe.ai/confidence)：不确定性的解释与使用。
