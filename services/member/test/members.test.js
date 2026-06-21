'use strict';
// 用 Node 自带 test runner + 全局 fetch，零测试依赖。每个用例起一个临时端口的
// 服务器并在 finally 里关掉，用例之间互不干扰。
const test = require('node:test');
const assert = require('node:assert');
const { createApp } = require('../src/app');
const store = require('../src/store');

function start() {
  store.seed();
  const server = createApp().listen(0);
  const { port } = server.address();
  return { server, base: `http://127.0.0.1:${port}` };
}

test('healthz 返回 ok', async () => {
  const { server, base } = start();
  try {
    const r = await fetch(`${base}/healthz`);
    assert.equal(r.status, 200);
    assert.equal((await r.json()).status, 'ok');
  } finally {
    server.close();
  }
});

test('readyz 返回 ready', async () => {
  const { server, base } = start();
  try {
    const r = await fetch(`${base}/readyz`);
    assert.equal(r.status, 200);
    assert.equal((await r.json()).status, 'ready');
  } finally {
    server.close();
  }
});

test('metrics 暴露 Prometheus 文本', async () => {
  const { server, base } = start();
  try {
    await fetch(`${base}/api/v1/members`);
    const r = await fetch(`${base}/metrics`);
    const body = await r.text();
    assert.equal(r.status, 200);
    assert.ok(body.includes('http_requests_total'));
  } finally {
    server.close();
  }
});

test('GET 已存在会员，手机号脱敏', async () => {
  const { server, base } = start();
  try {
    const r = await fetch(`${base}/api/v1/members/m-1001`);
    assert.equal(r.status, 200);
    const body = await r.json();
    assert.equal(body.id, 'm-1001');
    assert.ok(body.phone.includes('****'), '响应里的手机号必须脱敏');
  } finally {
    server.close();
  }
});

test('GET 不存在会员返回 404', async () => {
  const { server, base } = start();
  try {
    const r = await fetch(`${base}/api/v1/members/ghost-9`);
    assert.equal(r.status, 404);
  } finally {
    server.close();
  }
});

test('POST 创建会员成功返回 201', async () => {
  const { server, base } = start();
  try {
    const r = await fetch(`${base}/api/v1/members`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ name: '新会员', tier: 'SILVER', phone: '13912345678' }),
    });
    assert.equal(r.status, 201);
    assert.equal((await r.json()).tier, 'SILVER');
  } finally {
    server.close();
  }
});

test('POST 非法 tier 返回 422', async () => {
  const { server, base } = start();
  try {
    const r = await fetch(`${base}/api/v1/members`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ name: 'x', tier: 'PLATINUM' }),
    });
    assert.equal(r.status, 422);
  } finally {
    server.close();
  }
});

test('列表包含种子数据', async () => {
  const { server, base } = start();
  try {
    const r = await fetch(`${base}/api/v1/members`);
    assert.ok((await r.json()).length >= 3);
  } finally {
    server.close();
  }
});
