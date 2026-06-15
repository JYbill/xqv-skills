# Docker 构建与部署模板

## 统一构建入口模板

正式构建并推送 registry：

```bash
bash ./docker-build.sh -p x86-debian
```

本地导出镜像，不推送 registry：

```bash
bash ./docker-build.sh -p x86-debian -s
```

## `package.json` 脚本模板

如果项目保留 `package.json` 脚本，`deploy:docker` 应指向统一入口：

```json
{
  "deploy:docker": "bash ./docker-build.sh -p x86-debian"
}
```

## `.dockerignore` 模板

常见后台项目会包含本地配置、缓存、文档、测试、agent/AI 工作目录和环境目录。默认使用下面模板减少构建上下文，并避免把本地或敏感文件复制进镜像；如果某个项目的 Dockerfile 明确需要其中某项，先说明原因再移除对应忽略项。

```dockerignore
.husky
.cache
node_modules/
.git/
.idea/
alter-table
.gitignore
.jscsrc
tmp/
logs/
coverage/
.vitest-attachments/
docker-build.sh
*.Dockerfile
public/files/*
public/uploads/*
.editorconfig
lint-staged.config.js
*.DockerFile
eslint.config.js
mise.toml
prettier.config.js
README.md
.ai
.aiassistant
.sisyphus
.claude
.agents
update-log
test
.github
CLAUDE.md
.mcp.json
docs
docker.compose.yaml
AGENTS.md
skills-lock.json

# legacy env
src/env

# env
env
```

## 镜像 tag 模板

`docker-build.sh` 根据 Git 信息生成镜像 tag：

```text
<platform>_<branch_name>_<commit_id>_<latest_git_tag>
```

其中分支名里的 `/` 会替换成 `_`。

## 多阶段构建顺序模板

```text
install
  ├─ format → lint
  └─ test
       └─ coverage-report
production
```

`format`、`lint`、`test` 任一失败时，不继续构建 `production`。`coverage-report` 用于从 `test` 阶段导出 `/app/coverage/`，不参与最终生产镜像。

## `x86-debian.Dockerfile` 模板

```Dockerfile
# 依赖基础层：提供安装原生依赖和运行校验 target 所需的工具链。
FROM --platform=linux/amd64 node:24.15.0-slim AS base
WORKDIR /app
RUN echo "deb http://mirrors.aliyun.com/debian/ bookworm main" > /etc/apt/sources.list && \
  echo "deb http://mirrors.aliyun.com/debian/ bookworm-updates main" >> /etc/apt/sources.list && \
  echo "deb http://mirrors.aliyun.com/debian-security/ bookworm-security main" >> /etc/apt/sources.list && \
  rm -rf /etc/apt/sources.list.d/*
RUN apt-get update && apt-get install -y --no-install-recommends openssl build-essential python3 && \
  apt-get clean && apt-get autoclean && apt-get autoremove -y && \
  rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*
RUN npm install -g pnpm && npm cache clean -f

# 安装层：先复制依赖清单以复用 Docker 缓存，再复制完整源码。
FROM base AS install
COPY package.json .
COPY pnpm-workspace.yaml .
COPY pnpm-lock.yaml .
COPY patches patches
COPY vendor ./vendor
COPY .npmrc .
RUN npm pkg delete scripts.prepare
RUN pnpm --version
RUN pnpm config list
RUN pnpm install --frozen-lockfile
COPY . .

# 格式化校验层：由 docker-build.sh 在 production 前置阶段触发。
FROM install AS format
RUN pnpm format

# 代码检查层：依赖 format 层，保持 Docker 构建顺序清楚。
FROM format AS lint
RUN pnpm lint

# 测试层：只运行普通测试 project；e2e 依赖专门测试环境，不纳入镜像发布前置构建。
FROM install AS test
RUN pnpm test

# 覆盖率报告层：用于从 test 阶段导出 coverage 产物。
FROM scratch AS coverage-report
COPY --from=test /app/coverage/ /

# 生产层：项目生产态通过 PM2 直接运行 TypeScript 入口。
FROM --platform=linux/amd64 node:24.15.0-slim AS production
WORKDIR /app
RUN echo "deb http://mirrors.aliyun.com/debian/ bookworm main" > /etc/apt/sources.list && \
  echo "deb http://mirrors.aliyun.com/debian/ bookworm-updates main" >> /etc/apt/sources.list && \
  echo "deb http://mirrors.aliyun.com/debian-security/ bookworm-security main" >> /etc/apt/sources.list && \
  rm -rf /etc/apt/sources.list.d/*
RUN apt-get update && apt-get install -y --no-install-recommends bash vim ffmpeg curl procps openssl && \
  apt-get clean && apt-get autoclean && apt-get autoremove -y && \
  rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*
ENV NODE_ENV=production
RUN npm install -g pm2 pnpm && npm cache clean -f
RUN pm2 install pm2-logrotate && pm2 set pm2-logrotate:max_size 200M && pm2 set pm2-logrotate:retain 7
COPY package.json .
COPY pnpm-workspace.yaml .
COPY pnpm-lock.yaml .
COPY patches patches
COPY vendor ./vendor
COPY .npmrc .
RUN npm pkg delete scripts.prepare
RUN pnpm install --prod --frozen-lockfile && pnpm store prune
COPY . .
# 对 vim 编辑会读取该环境变量，从而使用 utf-8 而非兜底的 latin1 字符集。
ENV LANG=C.utf8
ENV LC_ALL=C.utf8

EXPOSE 3000
CMD ["pm2-runtime", "pm2.config.cjs"]
```

## 汇报模板

```markdown
已更新 Docker 构建与部署约定。

变更：
- 明确 `x86-debian.Dockerfile` 是默认 Dockerfile。
- 明确 `docker-build.sh -p x86-debian` 是统一构建与部署入口。
- 记录 Docker 多阶段构建顺序：install → (format → lint) 与 test 并行 → production。
- 记录 `coverage-report` 从 test 阶段导出 coverage 产物。
- 记录默认推送 registry 和 `-s` 导出 `images.tar` 的区别。
- 增加 `.dockerignore` 模板，排除常见本地配置、缓存、文档、测试、agent/AI 工作目录和环境目录。

验证：
- 已检查 `docker-build.sh` 与 `x86-debian.Dockerfile` 的 target 对应关系。
- `<实际执行的 docker 构建命令>`：<结果>。

注意：
- 未在文档中复制 registry 账号密码。
- 如未实际执行 Docker 构建，说明原因。
```
