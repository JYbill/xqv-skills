已更新 Docker 构建与部署约定。

变更：
- 明确 `x86-debian.Dockerfile` 是默认 Dockerfile。
- 明确 `docker-build.sh -p x86-debian` 是统一构建与部署入口。
- 记录 Docker 多阶段构建顺序：install → format/lint/test/test-cov/build → production。
- 记录 `coverage-report` 从 test-cov 阶段导出 coverage 产物，且只在项目保留 `test:cov` 时使用。
- 记录默认推送 registry 和 `-s` 导出 `images.tar` 的区别。
- 增加 `.dockerignore` 模板，排除常见本地配置、缓存、文档、测试、agent/AI 工作目录和环境目录。

验证：
- 已检查 `docker-build.sh` 与 `x86-debian.Dockerfile` 的 target 对应关系。
- `<实际执行的 docker 构建命令>`：<结果>。

注意：
- 未在文档中复制 registry 账号密码。
- 如未实际执行 Docker 构建，说明原因。
