# NestJS Dockerfile 模板

以 `wzj-nodejs-v2` 的 `x86-debian.Dockerfile` 为基础同步公共阶段、包管理器和排查工具；NestJS 保留 Prisma 生成、`build` 和 `dist` 生产入口。

```dockerfile
FROM --platform=linux/amd64 node:26.3-slim AS base
WORKDIR /app
RUN . /etc/os-release && \
  echo "deb http://mirrors.aliyun.com/debian/ ${VERSION_CODENAME} main" > /etc/apt/sources.list && \
  echo "deb http://mirrors.aliyun.com/debian/ ${VERSION_CODENAME}-updates main" >> /etc/apt/sources.list && \
  echo "deb http://mirrors.aliyun.com/debian-security/ ${VERSION_CODENAME}-security main" >> /etc/apt/sources.list && \
  rm -rf /etc/apt/sources.list.d/*
RUN apt-get update && \
  apt-get install -y --no-install-recommends openssl build-essential python3 && \
  apt-get clean && \
  apt-get autoclean && \
  apt-get autoremove -y && \
  rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*
# 从项目清单读取 pnpm 精确版本，构建和生产阶段共用。
COPY package.json .
RUN npm install -g "$(node -p 'require("./package.json").packageManager')" && npm cache clean -f

FROM base AS install
COPY package.json .
RUN npm pkg delete scripts.prepare
COPY .npmrc .
COPY pnpm-lock.yaml .
COPY pnpm-workspace.yaml .
RUN pnpm --version
RUN pnpm config list
RUN pnpm install --frozen-lockfile && pnpm store prune
COPY prisma.config.ts .
COPY prisma prisma
COPY env env
RUN pnpm prisma:generate
COPY . .

FROM install AS format
ARG CHECK_FILES=""
RUN if [ -n "$CHECK_FILES" ]; then \
  set -f; \
  pnpm exec oxfmt --config oxfmt.config.ts $CHECK_FILES; \
  else \
  pnpm run format; \
  fi

FROM format AS lint
ARG CHECK_FILES=""
RUN if [ -n "$CHECK_FILES" ]; then \
  set -f; \
  pnpm exec oxlint --config oxlint.config.ts --fix --no-error-on-unmatched-pattern $CHECK_FILES; \
  else \
  pnpm run lint; \
  fi

FROM install AS test
# 测试进程按上海时区处理本地日期，避免容器默认时区导致日期偏移。
ENV TZ=Asia/Shanghai
RUN pnpm test:cov

FROM scratch AS coverage-report
COPY --from=test /app/coverage/ /

FROM install AS build
RUN pnpm build

FROM base AS production
WORKDIR /app
COPY .vimrc /root/.vimrc
ENV NODE_ENV=production
ENV LANG=C.utf8
ENV LC_ALL=C.utf8
RUN apt-get update && \
  apt-get install -y --no-install-recommends bash vim curl procps linux-perf && \
  apt-get clean && \
  apt-get autoclean && \
  apt-get autoremove -y && \
  rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*
RUN npm install -g pm2 && npm cache clean -f
RUN pm2 install pm2-logrotate && \
 pm2 set pm2-logrotate:max_size 200M && \
 pm2 set pm2-logrotate:retain 7
COPY --from=build /app/package.json .
RUN npm pkg delete scripts.prepare
COPY --from=build /app/.npmrc .
COPY --from=build /app/pnpm-lock.yaml .
COPY --from=build /app/pnpm-workspace.yaml .
RUN pnpm install --prod --frozen-lockfile && pnpm store prune
COPY --from=build /app/pm2.config.cjs .
COPY --from=build /app/dist dist

EXPOSE 3000
CMD ["pm2-runtime", "pm2.config.cjs"]
```

## 按目标项目适配

- Node 镜像版本和平台以目标项目为准；`package.json#packageManager` 必须声明项目使用的 pnpm 精确版本。
- 生产阶段包含 `bash`、`vim`、`curl`、`procps`、`linux-perf` 排查工具。源 Dockerfile 的 `ffmpeg` 属于业务依赖，仅在目标项目需要音视频处理时加入。
- 项目依赖 `patches/` 或 `vendor/` 时，在 install 和 production 两处执行 `pnpm install` 前复制对应目录；目录不存在时不要添加 `COPY`。
- `CHECK_FILES` 为按空白分隔的文件列表，非空时仅校验指定文件，为空时执行全量 format / lint。传参方使用 `--build-arg CHECK_FILES="..."`，并保证文件名不含空白；路径、配置文件和命令选项以目标项目为准。
- `lint` 继承 `format`，使格式化结果进入代码检查阶段；test 独立继承 install。
- 直接运行 TypeScript 源码的项目按实际入口复制源码及运行资源，不套用 NestJS 的 Prisma、build 和 dist 步骤。

## 配套 `.vimrc`

使用上面的 Dockerfile 时，在项目根目录创建并提交 `.vimrc`，内容如下；确认 `.dockerignore` 没有排除该文件，否则 `COPY` 会失败。

```vim
set encoding=utf-8
set fileencodings=utf-8
set fileencoding=utf-8
set mouse-=a
```

编码统一使用 UTF-8，不加入 `ucs-bom`、`cp936` 或 `gb2312`。不设置 `termencoding`，沿用 `encoding`。模板按 root 用户将配置复制到 `/root/.vimrc`；项目使用其他用户时，调整为实际用户的 home 目录，并确认该用户可读取配置。
