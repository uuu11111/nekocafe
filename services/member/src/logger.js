'use strict';
// 结构化日志（pino）。两个关键点：
//   1) mixin 从当前 span 取 traceId/spanId，和链路打通；
//   2) redact 对手机号/邮箱/身份证等字段脱敏，杜绝 PII 明文落盘。
const pino = require('pino');
const pinoHttp = require('pino-http');
const { trace } = require('@opentelemetry/api');

const logger = pino({
  level: process.env.LOG_LEVEL || 'info',
  base: {
    service: process.env.OTEL_SERVICE_NAME || 'member',
    env: process.env.APP_ENV || 'dev',
  },
  messageKey: 'msg',
  timestamp: pino.stdTimeFunctions.isoTime,
  formatters: {
    level(label) {
      return { level: label.toUpperCase() };
    },
  },
  redact: {
    paths: [
      'phone', 'email', 'idCard',
      '*.phone', '*.email', '*.idCard',
      'req.headers.authorization', 'req.headers.cookie',
    ],
    censor: '***',
  },
  mixin() {
    const span = trace.getActiveSpan();
    if (!span) return {};
    const ctx = span.spanContext();
    return { traceId: ctx.traceId, spanId: ctx.spanId };
  },
});

const httpLogger = pinoHttp({
  logger,
  customSuccessMessage() {
    return 'request completed';
  },
});

module.exports = { logger, httpLogger };
