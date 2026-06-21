'use strict';
// OpenTelemetry 初始化。必须在任何业务模块之前 require（见 index.js 第一行）。
// 只有配了 OTEL_EXPORTER_OTLP_ENDPOINT 才真正启动，否则安全降级为 no-op，
// 这样本地裸跑 / 单测都不需要拉起 collector。
const endpoint = process.env.OTEL_EXPORTER_OTLP_ENDPOINT;
if (!endpoint) {
  console.error(JSON.stringify({ level: 'info', service: 'member', msg: '未配置 OTLP 端点，跳过链路追踪' }));
} else {
  const { NodeSDK } = require('@opentelemetry/sdk-node');
  const { OTLPTraceExporter } = require('@opentelemetry/exporter-trace-otlp-http');
  const { HttpInstrumentation } = require('@opentelemetry/instrumentation-http');
  const { ExpressInstrumentation } = require('@opentelemetry/instrumentation-express');
  const { resourceFromAttributes } = require('@opentelemetry/resources');
  const {
    ATTR_SERVICE_NAME,
    ATTR_SERVICE_VERSION,
  } = require('@opentelemetry/semantic-conventions');

  const sdk = new NodeSDK({
    resource: resourceFromAttributes({
      [ATTR_SERVICE_NAME]: process.env.OTEL_SERVICE_NAME || 'member',
      [ATTR_SERVICE_VERSION]: process.env.APP_VERSION || '0.1.0',
      'deployment.environment': process.env.APP_ENV || 'dev',
    }),
    // OTLP/HTTP 端点（collector 默认 4318），比 grpc 少一个 grpc-js 依赖、镜像更小
    traceExporter: new OTLPTraceExporter({ url: `${endpoint.replace(/\/$/, '')}/v1/traces` }),
    // 只挂 http + express 两个仪表，避免 auto-instrumentations 全家桶把镜像撑大
    instrumentations: [new HttpInstrumentation(), new ExpressInstrumentation()],
  });
  sdk.start();
  process.on('SIGTERM', () => sdk.shutdown().finally(() => process.exit(0)));
}
