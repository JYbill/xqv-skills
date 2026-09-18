# Dockerfile 阶段契约

Docker 构建 workflow 不拥有一份适用于所有后台项目的 Dockerfile。NestJS、Koa、Express 等项目可以使用不同的基础镜像、系统依赖、构建产物、启动入口和生产镜像结构。

## 与 docker-build.sh 的共享接口

使用本 workflow 的 Dockerfile 至少提供这些 target：

- `install`：安装依赖并准备后续校验阶段。
- `format`：运行项目格式化检查或项目约定的 format 命令。
- `lint`：运行项目代码检查；由 `docker-build.sh` 保证在 `format` 成功后执行。
- `test`：运行项目测试，可与 `format -> lint` 这一组并行。
- `production`：只在全部前置校验通过后构建最终镜像。

项目存在编译产物时可以提供 `build` target，并让 `production` 通过 `FROM build` 或 `COPY --from=build` 形成依赖；项目直接运行源码时不要虚构 `build` target。`docker-build.sh` 构建 `production` 时会由 Docker 自动构建其依赖阶段。

构建阶段需要 `env/` 或 `src/env/` 时，`production` 优先从干净的 runtime / base 阶段开始并选择性复制运行产物。若项目必须继承 build 阶段或整体复制工作目录，进入最终镜像前必须移除环境目录；不能让测试和构建配置随 production 产物保留。

```text
install
  ├─ format -> lint
  └─ test
全部通过
  └─ production
       └─ build（仅在具体 Dockerfile 需要时传递构建）
```

可选的 `coverage-report` 等 target 属于项目能力，不能成为 workflow 的强制接口。

## 公共层与排查工具

Debian Node 镜像参考具体模板同步以下配置：从 `package.json#packageManager` 安装项目指定的 pnpm；生产阶段安装 `bash`、`vim`、`curl`、`procps`、`linux-perf`，并配置 UTF-8 和 `.vimrc`。`ffmpeg` 等业务依赖按目标项目需要加入。依赖安装涉及 `patches/`、`vendor/` 时，在构建和生产安装依赖前分别复制所需目录。

采用 `CHECK_FILES` 时，format / lint target 声明该构建参数；非空时检查指定文件，为空时执行项目全量命令。调用脚本需显式传入 `--build-arg CHECK_FILES="..."`。lint 继承 format 可保留格式化结果，test 继续独立继承 install。具体命令见框架模板。

## 选择具体模板

先识别目标项目框架和现有 Dockerfile，再选择对应 framework 模板。NestJS 的当前具体模板见 `../../frameworks/nestjs/dockerfile.md`。没有对应 framework 模板时，以项目事实为基础新增或调整，不能借用 NestJS 模板冒充通用模板。
