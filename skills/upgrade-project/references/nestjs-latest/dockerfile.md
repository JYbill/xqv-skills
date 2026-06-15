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
RUN npm pkg delete scripts.prepare
COPY .npmrc .
COPY patches patches
COPY pnpm-lock.yaml .
COPY pnpm-workspace.yaml .
COPY vendor vendor
RUN pnpm --version
RUN pnpm config list
RUN pnpm install --frozen-lockfile && pnpm store prune
COPY prisma.config.ts .
# 当前项目的 prisma.config.ts 使用 strict 模式读取 env，prisma:generate 需要该目录。
COPY env env
COPY prisma prisma
RUN pnpm prisma:generate
COPY . .

# 格式化校验层：由 docker-build.sh 在 production 前置阶段触发。
FROM install AS format
RUN pnpm format

# 代码检查层：由 docker-build.sh 在 format 之后触发；Dockerfile 自身不依赖 format 层，避免把格式化产物带入 lint。
FROM install AS lint
RUN pnpm lint

# 测试层：运行项目统一测试脚本；当前项目没有独立 test:cov 脚本，因此不保留 test-cov/coverage-report target。
FROM install AS test
RUN pnpm test

# 构建层：产出 dist，供 production 阶段复制。
FROM install AS build
RUN pnpm build

# 生产层：只安装生产依赖，并通过 PM2 运行编译产物。
FROM --platform=linux/amd64 node:24.15.0-slim AS production
ENV NODE_ENV=production
# 对 vim 编辑会读取该环境变量，从而使用 utf-8 而非兜底的 latin1 字符集。
ENV LANG=C.utf8
ENV LC_ALL=C.utf8
WORKDIR /app
RUN echo "deb http://mirrors.aliyun.com/debian/ bookworm main" > /etc/apt/sources.list && \
  echo "deb http://mirrors.aliyun.com/debian/ bookworm-updates main" >> /etc/apt/sources.list && \
  echo "deb http://mirrors.aliyun.com/debian-security/ bookworm-security main" >> /etc/apt/sources.list && \
  rm -rf /etc/apt/sources.list.d/*
RUN apt-get update && apt-get install -y --no-install-recommends openssl build-essential python3 bash vim curl ffmpeg procps && \
  apt-get clean && apt-get autoclean && apt-get autoremove -y && \
  rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*
RUN npm install -g pm2 pnpm && npm cache clean -f
RUN pm2 install pm2-logrotate && pm2 set pm2-logrotate:max_size 200M && pm2 set pm2-logrotate:retain 7
COPY --from=build /app/package.json .
RUN npm pkg delete scripts.prepare
COPY --from=build /app/.npmrc .
COPY --from=build /app/pnpm-lock.yaml .
COPY --from=build /app/patches patches
COPY --from=build /app/pnpm-workspace.yaml .
COPY --from=build /app/vendor vendor
RUN pnpm install --prod --frozen-lockfile && pnpm store prune
COPY --from=build /app/pm2.config.js .
COPY --from=build /app/dist dist

EXPOSE 3000
CMD ["pm2-runtime", "pm2.config.js"]
