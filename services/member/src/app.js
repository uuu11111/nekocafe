'use strict';
// Express 应用工厂。拆出 createApp 是为了让单测能直接拿 app 起临时服务器，
// 不必依赖固定端口，也不必引入 supertest 这类额外依赖。
const express = require('express');
const { httpLogger } = require('./logger');
const { metricsMiddleware, metricsHandler } = require('./metrics');
const store = require('./store');

function createApp() {
  const app = express();
  app.disable('x-powered-by');
  app.use(express.json());
  app.use(httpLogger);
  app.use(metricsMiddleware);

  app.get('/healthz', (req, res) => res.json({ status: 'ok', service: 'member' }));
  app.get('/readyz', (req, res) =>
    res.json({
      status: 'ready',
      env: process.env.APP_ENV || 'dev',
      version: process.env.APP_VERSION || '0.1.0',
    }),
  );
  app.get('/metrics', metricsHandler);

  app.get('/api/v1/members', (req, res) => res.json(store.list()));

  app.get('/api/v1/members/:id', (req, res) => {
    const member = store.get(req.params.id);
    if (!member) return res.status(404).json({ detail: '会员不存在' });
    return res.json(store.toPublic(member));
  });

  app.post('/api/v1/members', (req, res) => {
    try {
      const created = store.create(req.body);
      // 故意把 phone/email 也带进日志，用来验证 logger 的 redact 脱敏确实生效
      req.log.info(
        { memberId: created.id, phone: created.phone, email: created.email },
        '会员创建成功',
      );
      return res.status(201).json(store.toPublic(created));
    } catch (err) {
      return res.status(422).json({ detail: err.message });
    }
  });

  return app;
}

module.exports = { createApp };
