# pm2.config.cjs 模板

以 HTTP 服务进程为模板：使用集群模式，并在 NestJS 开始监听后通知 PM2 就绪。PM2 启动 Node.js 编译产物时保留原生 source map，以便日志定位到源码。

```js
const os = require('os')

module.exports = {
  apps: [
    {
      name: 'api',
      script: './dist/main.js',
      node_args: '--enable-source-maps --trace-warnings',
      cwd: __dirname,
      watch: false,
      // 按可用并行数减一确定进程数，至少 1 个，最多 6 个。
      instances: Math.min(6, Math.max(1, os.availableParallelism() - 1)),
      exec_mode: 'cluster',
      wait_ready: true,
      kill_timeout: 5000,
      error_file: 'logs/err.log',
      out_file: 'logs/out.log',
      merge_logs: true,
      log_date_format: 'YYYY-MM-DD HH:mm Z',
      env: {
        NODE_ENV: 'production',
        TZ: 'Asia/Shanghai',
      },
    },
  ],
}
```

`wait_ready: true` 要求应用在完成启动后发送就绪信号。在 NestJS 入口的 `app.listen` 后加入：

```ts
await app.listen(port || 3000)
process.send?.('ready')
```

直接运行时没有 PM2 IPC，使用可选调用避免报错。迁移时按项目实际调整服务名、编译入口、进程数上限、关闭等待时间、日志时间格式和时区；不要将只运行后台任务的 manager 进程配置用于 HTTP 服务。
