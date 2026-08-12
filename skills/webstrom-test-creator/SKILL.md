---
name: webstrom-test-creator
description: 为项目中的 Vitest 测试文件创建可提交、可跨团队使用的 WebStorm `.run/*.run.xml` 文件级运行配置。当用户要求为某个测试目录或 glob 批量生成 WebStorm 运行配置、按 `folderName` 分组、参考已有 `.run` 模板，或为手动调试补齐 Vitest 配置时使用。
---

# WebStorm Test Creator

为目标范围内的每个真实测试文件创建一份 `TEST_FILE` 运行配置。保留项目现有运行约定，只把名称、分组、测试路径和经证据确认的执行参数替换为当前目标。

## 流程引导

```text
[测试目录或 glob + folderName]
               |
               v
[读取仓库规则、模板、package.json 和 Vitest 配置]
               |
               v
[筛选真实测试文件，排除 schema / fixture / setup / helper]
               |
               v
[逐文件确认 project / options / env]
               |
               +-- 无法确认 --> [说明缺失的执行契约并停止]
               |
               +-- 已确认 ----> [读取 references 中的核心 XML 模板]
                                      |
                                      v
                         [处理名称冲突并写入 .run/*.run.xml]
                                      |
                                      v
                         [核对文件映射 -> XML 校验 -> diff 检查]
```

## 工作流

1. 读取仓库规则、用户指定的 `.run` 模板、`package.json` 测试脚本和 Vitest 配置。
2. 在用户给定的目录或 glob 内列出文件，并依据 Vitest `include`、`exclude` 和项目测试命名规范筛出真实测试文件。排除 schema、fixture、setup 和测试辅助模块。
3. 为每个测试文件确认对应的 Vitest project、命令参数和环境变量。
4. 以用户指定模板为优先来源；没有指定模板时，读取 [references/vitest-test-file.run.md](references/vitest-test-file.run.md) 中的核心 XML 模板。
5. 在项目根目录的 `.run/` 下为每个测试文件生成一份配置，并按用户指定值设置 `folderName`。
6. 校验目标测试文件与新配置一一对应，再检查 XML 和 diff 格式。

## 确认执行参数

把 Vitest 配置中的 project `include`、`exclude` 作为文件归属的主要证据，再用 `package.json` 脚本和已有 `.run` 配置确认命令参数及环境变量。

- 普通单元或集成测试使用项目定义的普通测试 project。
- `*.e2e-spec.*`、`*.llm-spec.*`、`*.otel-spec.*` 等专用测试只使用与其命名和 include 规则对应的 project。
- 一个文件同时被普通 project 和聚合 project 收录时，默认选择最具体、成本最低且符合文件用途的 project；只有用户要求整套 E2E 时才选择聚合 project。
- `folderName` 只是 WebStorm 界面分组，不能据此推断 Vitest project。
- 只有测试脚本、Vitest 配置或现有运行配置明确要求时才添加环境变量。不要根据 project 名称猜测环境变量。
- 不要把模板中的 `--project test`、`NODE_ENV` 或其他测试专属参数无条件复制到所有文件。

无法从仓库确认文件属于哪个 project 时，先向用户说明缺少的执行契约，不要生成看似可用但实际运行错误的配置。

## 生成配置

从参考文本提取 XML 模板，保留项目真实使用的 runner 类型、Node 解释器、Vitest 包位置、工作目录和 `<method>` 版本，并替换这些动态字段：

| 字段 | 写法 |
| --- | --- |
| `name` | 默认使用测试文件名；同一 `folderName` 内重名时加最短的唯一父目录前缀 |
| `folderName` | 使用用户指定的分组名 |
| `vitest-options` | 使用当前测试文件所属 project 的参数 |
| `envs` | 使用当前测试命令明确要求的环境变量；无要求时保留 `<envs />` |
| `scope-kind` | 使用 `TEST_FILE` |
| `test-file` | 使用 `$PROJECT_DIR$/` 加仓库相对测试路径 |

禁止把开发者机器的绝对路径写入 `SKILL.md`、模板或生成的 `.run` 配置。项目文件统一通过 `$PROJECT_DIR$` 定位。

## 避免覆盖同名配置

默认把配置保存为 `.run/<测试文件名>.run.xml`。

- 目标文件已有配置时，确认 `<test-file>` 指向相同文件后再更新需要变化的字段。
- 文件名已被其他测试占用时，保留现有配置，并给新配置文件名添加 `folderName` 或最短唯一父目录前缀。
- 同一 `folderName` 内存在相同显示名称时，同时给 `name` 添加最短唯一父目录前缀。
- 不修改无关运行配置，不改变用户已有的暂存状态。

## 验证

完成前逐项确认：

1. 重新列出目标范围内被 Vitest 收录的测试文件。
2. 确认每个目标测试文件都有且只有一份本次创建或更新的文件级配置。
3. 确认所有配置使用用户指定的 `folderName`，且 `<test-file>` 使用 `$PROJECT_DIR$` 相对路径。
4. 使用 `xmllint --noout <配置文件...>` 校验 XML；环境没有 `xmllint` 时使用可用的 XML 解析器。
5. 对本次配置运行 `git diff --check`。

创建手动调试配置不要求执行测试本身。除非用户另外要求，只报告生成的配置、project/env 选择和 XML 校验结果。
