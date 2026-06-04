---
name: notes
description: 当用户要求补注释、调整注释、review 注释质量、沉淀注释规范，或代码涉及前后端通用逻辑、前端 React Hook / 事件处理器、Node.js 后台 controller / service / SQL / 任务编排时，使用这个 skill。目标是让注释解释关键意图，不给简单代码逐行配旁白。
---

# notes

这个 skill 用于写代码注释。注释要帮助后来读代码的人理解关键意图，而不是把代码翻译成中文。

## 前后端通用注释

注释只写在值得解释的地方。它应该说明为什么这样写、避免什么误解、字段代表什么业务含义。简单赋值、普通取字段、明显的空值回退、一眼能看懂的单条件判断，不要单独写注释。
多行相似取值如果需要说明，优先在这一组代码上方写一行总结注释，不要每一行都配一句旁白。空行只用于分隔不同业务阶段、不同控制流或确实需要停顿的说明。
导出函数、class 的 static 方法，必须在定义上方写简短 JSDoc，说明入参或返回结果的业务含义。不要写只复述函数名的 JSDoc。
复杂判断、连续判断、复杂三元表达式、循环、switch、数字计算、字段语义、数据结构转换、展示文案拼接、输出模板和 prompt 边界，才是优先补注释的地方。注释要讲判断依据、计算口径、转换后的读取方式、最终用户可见效果或模型可见边界。
不要写“获取某某”“设置某某”“返回某某”“处理某某”这种表面注释。不要把十几个字段取值逐行解释。不要写长段落，一条注释只讲一个重点。

### 前后端通用示例

```ts
// 这些字段只是把已有统计结果塞进模板，保持一组注释即可。
const questionActivityCount = output.question?.activityCount ?? "计算中";
const discussionActivityCount = output.discussion?.activityCount ?? "计算中";

const attendanceRateNumber = Number(evaluation.attendanceRate);
const attendanceRateAverageNumber = Number(evaluation.attendanceRateAverage);
// 两个值都是真正的数字时才计算差值，否则保留原始展示文本，避免输出 NaN。
if (Number.isFinite(attendanceRateNumber) && Number.isFinite(attendanceRateAverageNumber)) {
  const attendanceRateComparison = attendanceRateNumber >= attendanceRateAverageNumber ? "高出" : "低于";
}

// 有姓名时拼成 学生A、学生B、学生C 这种展示形式，不展示内部 studentId。
const quickAnswerTopStudentText = `${quickAnswerTopStudentNames.join("、")}同学互动积极`;
```

## 前端 React 注释

React 组件里的 `useEffect`、`useMemo`、`useCallback` 和事件处理函数，只有在承载外部订阅、定时器、防抖 / 节流、异步请求、DOM 或滚动副作用、本地输入态与父级状态解耦等不直观意图时才补注释。
`useEffect` 的注释写在 hook 上方，说明副作用边界、cleanup 原因和依赖意图。不要写“监听某某变化”这种表面注释。
事件处理函数的注释写在函数上方，说明用户交互如何被拆成立即 UI 更新和延迟副作用，或为什么不直接调用父级回调。不要写“处理某某输入”。
渲染分支、空态、加载态、回放态、浮窗 / 全屏态这类 UI 状态互斥时，如果优先级容易看错，要在分支上方说明展示顺序。普通 JSX 结构、显而易见的 className 和按钮点击，不要补注释。

### 前端 React 示例

```tsx
// RxJS 只订阅搜索输入流，组件卸载时主动释放订阅，避免切换入口后残留搜索回调。
useEffect(() => {
  const subscription = searchSubjectRef.current
    .pipe(debounceTime(300), distinctUntilChanged())
    .subscribe((value) => onChangeSearchKeyword(value));

  return () => {
    subscription.unsubscribe();
  };
}, [onChangeSearchKeyword]);

// 本地输入值先立即更新，原始关键词再进入防抖流，避免每次敲字都刷新列表。
const handleSearchChange = (event: ChangeEvent<HTMLInputElement>) => {
  const value = event.target.value;

  setSearchInput(value);
  searchSubjectRef.current.next(value);
};
```

## Node.js 后台注释

Node.js 后台的注释重点是业务边界、数据一致性和副作用。controller 注释说明请求参数、权限、租户、角色和提前返回的业务原因。service 注释说明编排顺序、事务边界、幂等设计、重试策略、缓存失效、软删除、状态流转和副作用顺序。
数据库查询、SQL、ORM query builder、聚合统计要给不直观的 join 关系、group by 口径、时间范围、状态过滤和业务 key 映射补注释。不要给普通 where 条件逐句解释。
定时任务、队列消费、消息订阅、外部接口、webhook、文件上传、支付、消息推送，要说明重入、去重、失败处理、字段映射和补偿策略。错误处理和日志只写决策原因，不要给每个 `try/catch` 写“捕获异常”。

### Node.js 后台示例

```ts
/** 刷新课程答题统计，并返回本次任务产出的课程维度汇总。 */
export async function refreshCourseAnswerStats(courseId: number) {
  const course = await findCourseById(courseId);

  // 历史任务可能残留已删除课程，跳过脏数据即可，避免整批统计刷新被单条记录中断。
  if (!course) return emptyCourseAnswerStats;

  return database.transaction(async (transaction) => {
    // 同一个后台任务允许失败后重试，先清理本轮临时明细再写入，保证重复执行不会累计旧数据。
    await deleteTemporaryAnswerStats(courseId, transaction);
    await insertTemporaryAnswerStats(courseId, transaction);

    // 汇总结果只在事务末尾落库，避免接口读到明细已更新但汇总未更新的中间态。
    return updateCourseAnswerSummary(courseId, transaction);
  });
}
```
