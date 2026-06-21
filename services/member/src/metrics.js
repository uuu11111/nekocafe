'use strict';
// Prometheus 指标，同样走 RED 方法。collectDefaultMetrics 顺带把进程级的
// CPU/内存/事件循环延迟（USE 视角）也吐出来，省得另装 node-exporter。
const client = require('prom-client');

const register = new client.Registry();
register.setDefaultLabels({ service: process.env.OTEL_SERVICE_NAME || 'member' });
client.collectDefaultMetrics({ register });

const httpRequests = new client.Counter({
  name: 'http_requests_total',
  help: 'HTTP 请求总数',
  labelNames: ['method', 'route', 'status'],
  registers: [register],
});
const httpDuration = new client.Histogram({
  name: 'http_request_duration_seconds',
  help: 'HTTP 请求耗时（秒）',
  labelNames: ['method', 'route'],
  buckets: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5],
  registers: [register],
});

function metricsMiddleware(req, res, next) {
  if (req.path === '/metrics') return next();
  const start = process.hrtime.bigint();
  res.on('finish', () => {
    // req.route 在路由匹配后才有值，用它拿到模板（/api/v1/members/:id）控制基数
    const route = req.route ? req.baseUrl + req.route.path : req.path;
    const seconds = Number(process.hrtime.bigint() - start) / 1e9;
    httpRequests.labels(req.method, route, String(res.statusCode)).inc();
    httpDuration.labels(req.method, route).observe(seconds);
  });
  next();
}

async function metricsHandler(req, res) {
  res.set('Content-Type', register.contentType);
  res.end(await register.metrics());
}

module.exports = { metricsMiddleware, metricsHandler, register };
