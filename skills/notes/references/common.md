# 通用注释规则

注释要帮助后来读代码的人理解关键意图，而不是把代码翻译成中文。先判断这个位置是否真的需要注释，再决定写 JSDoc、行内注释，还是不写。

## 注释决策流程

```text
看到一个代码位置
        │
        ├─ 是导出函数或 class static 方法？
        │        └─ 写简短 JSDoc，说明业务用途、关键入参或返回含义
        │
        ├─ 是 for 循环？
        │        └─ 在循环上方写一行总结，说明本轮循环的业务产出、过滤边界、状态推进或副作用顺序
        │
        ├─ 是同一逻辑阶段里连续定义多个变量，且后面紧跟 for / if 等逻辑处理？
        │        └─ 每个变量上方写 // 描述变量在后续逻辑里的职责，for / if 上方写逻辑块目标或分支边界
        │
        ├─ 是复杂判断、状态流转、SQL 口径、异步副作用或模型协议边界？
        │        └─ 写注释说明为什么这样做、避免什么误解
        │
        ├─ 是一组相似字段映射或模板取值？
        │        └─ 在这一组上方写一行总结，不逐字段解释
        │
        ├─ 前面有空行，表示进入新的业务小阶段？
        │        └─ 在这一段代码上方写一行组注释；如果说不出注释，就去掉空行
        │
        └─ 是简单赋值、普通取字段、明显空值回退或普通按钮点击？
                 └─ 不写注释
```

## 通用判断表

| 代码场景                                 | 推荐动作     | 注释重点                                       |
| ---------------------------------------- | ------------ | ---------------------------------------------- |
| 导出函数、class 的 static 方法           | 写 JSDoc     | 写业务用途、关键入参或返回结果的业务含义       |
| 所有 for 循环                            | 写一行组注释 | 说明本轮循环的业务产出、过滤边界、状态推进或副作用顺序 |
| 多变量准备后紧跟 for / if 逻辑处理       | 逐变量注释   | 说明变量在后续逻辑里的职责，逻辑块说明过滤或分支边界   |
| 复杂判断、连续判断、复杂三元、switch     | 写行内注释   | 写判断依据、状态优先级或分支边界               |
| 数字计算、聚合统计、字段口径转换         | 写行内注释   | 写计算口径、精度边界、最终展示含义             |
| 数据结构转换、模板拼接、prompt 边界      | 写行内注释   | 写转换后的读取方式、模型可见边界或用户可见效果 |
| 多行相似取值或字段映射                   | 写一行组注释 | 解释这一组数据的共同语义                       |
| 空行分隔出的业务小块                     | 写一行组注释 | 说明这一段代码在当前流程里的业务目标           |
| 简单赋值、普通取字段、明显空值回退       | 不写         | 代码本身已经能表达，不要制造噪音               |
| “获取某某”“设置某某”“返回某某”“处理某某” | 不写         | 这类注释只复述代码表面行为                     |

## 规则细节

注释只写在值得解释的地方。它应该说明为什么这样写、避免什么误解、字段代表什么业务含义。简单赋值、普通取字段、明显的空值回退、一眼能看懂的单条件判断，不要单独写注释。

多行相似取值如果需要说明，优先在这一组代码上方写一行总结注释，不要每一行都配一句旁白。所有 `for`、`for...of`、`for await...of`、`for...in` 循环都要在循环上方写一行组注释，说明本轮循环的业务产出、过滤或归一化边界、状态推进、批量副作用顺序；不要写“遍历某某”这种语法描述。空行只用于分隔不同业务阶段、不同控制流或确实需要停顿的说明。只要保留空行，空行后面的代码块上方就要有一行组注释说明这一小块在做什么；如果这一段简单到写不出有意义的组注释，就去掉空行，让代码连续读下去。

当同一逻辑阶段先连续定义多个变量，后面又紧跟 `for`、`if`、`switch` 等逻辑处理时，不能只用一条组注释覆盖整段。每个变量定义上方都要写 `// ...`，说明这个变量在后续逻辑里的职责，比如基准值、比较对象、累计容器、状态标记、外部协议字段或展示口径；每个 `for` / `if` 逻辑块上方都要写 `// ...`，说明该块负责的过滤、归一化、分支边界或产出结果。注释仍然不要解释语法本身，也不要写“定义变量”“遍历数组”这类表面描述。

这些要求的重点是补齐复杂流程的阅读入口。agent 不能只给导出函数补 JSDoc 后就跳过内部逻辑；只要循环或变量组承载了业务状态、过滤口径或副作用顺序，就要把这层意图写出来。

导出函数、class 的 static 方法，必须在定义上方写简短 JSDoc，说明方法自身职责、关键入参或返回结果的业务含义。不要写只复述函数名的 JSDoc，也不要把通用方法绑定到某个当前调用方场景。

复杂判断、连续判断、复杂三元表达式、switch、数字计算、字段语义、数据结构转换、展示文案拼接、输出模板和 prompt 边界，才是优先补注释的地方。注释要讲判断依据、计算口径、转换后的读取方式、最终用户可见效果或模型可见边界。`for` 循环例外：无论逻辑是否复杂，都要写一行说明循环块目的的总结。

不要写“获取某某”“设置某某”“返回某某”“处理某某”这种表面注释。不要把十几个字段取值逐行解释。不要写长段落，一条注释只讲一个重点。

## 示例

```ts
/** 生成学生在当前课程范围内的课堂表现摘要。 */
export function buildStudentPerformanceSummaries(
  records: StudentActivityRecord[],
  activeCourseIds: Set<number>,
) {
  // studentSummaryById 是学生维度的累计容器，后续循环持续合并同一学生的课堂表现。
  const studentSummaryById = new Map<number, StudentPerformanceSummary>();
  // absentStudentIds 记录已命中缺勤边界的学生，避免后续互动分数把缺勤状态覆盖掉。
  const absentStudentIds = new Set<number>();

  // 逐条过滤课程范围内的课堂记录，并累计学生维度摘要。
  for (const record of records) {
    // 历史课程记录不进入本轮统计口径，避免跨课程表现混入当前摘要。
    if (!activeCourseIds.has(record.courseId)) continue;

    const summary = studentSummaryById.get(record.studentId) ?? createEmptySummary(record.studentId);

    // 缺勤是最高优先级状态，先锁定学生，再跳过互动分累计。
    if (record.status === StudentActivityStatus.Absent) {
      absentStudentIds.add(record.studentId);
      summary.status = StudentPerformanceStatus.Absent;
      studentSummaryById.set(record.studentId, summary);
      continue;
    }

    // 已缺勤学生只保留缺勤状态，不再用后续互动记录回写为活跃。
    if (absentStudentIds.has(record.studentId)) continue;

    summary.answerCount += record.answerCount;
    studentSummaryById.set(record.studentId, summary);
  }

  return [...studentSummaryById.values()];
}
```

下面这种注释不要写，它只翻译语法，没有降低复杂逻辑的理解成本。

```ts
// 定义学生 Map。
const studentSummaryById = new Map<number, StudentPerformanceSummary>();

// 遍历课堂记录。
for (const record of records) {
  // 判断课程 ID。
  if (!activeCourseIds.has(record.courseId)) continue;
}
```
