'use strict';
// 第一行就 require instrumentation，确保 otel 在 express 被加载前完成 monkey-patch
require('./instrumentation');

const { createApp } = require('./app');
const { logger } = require('./logger');
const store = require('./store');

store.seed();

const port = Number(process.env.PORT || 8080);
const app = createApp();
const server = app.listen(port, () => logger.info({ port }, 'member 服务已启动'));

function shutdown(signal) {
  logger.info({ signal }, '收到退出信号，优雅关闭');
  server.close(() => process.exit(0));
}
['SIGTERM', 'SIGINT'].forEach((sig) => process.on(sig, () => shutdown(sig)));
