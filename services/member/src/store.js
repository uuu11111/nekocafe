'use strict';
// 会员领域：PoC 用进程内 Map，重启即清空（文档已说明）。要落库时换实现即可。
// 对外返回前统一过一遍脱敏，手机号 / 邮箱不以明文出现在响应里。

const TIERS = new Set(['BRONZE', 'SILVER', 'GOLD', 'BLACK_CAT']);

let seq = 1000;
const members = new Map();

function maskPhone(phone) {
  if (!phone) return phone;
  return String(phone).replace(/^(\d{3})\d{4}(\d{4})$/, '$1****$2');
}
function maskEmail(email) {
  if (!email) return email;
  return String(email).replace(/^(.).*(@.*)$/, '$1***$2');
}

function toPublic(m) {
  return {
    id: m.id,
    name: m.name,
    tier: m.tier,
    active: m.active,
    phone: maskPhone(m.phone),
    email: maskEmail(m.email),
    joinedAt: m.joinedAt,
  };
}

function create({ name, tier = 'BRONZE', phone, email, active = true }) {
  if (!name || typeof name !== 'string') {
    throw new Error('name 不能为空');
  }
  if (!TIERS.has(tier)) {
    throw new Error(`tier 必须是 ${[...TIERS].join(' / ')} 之一`);
  }
  const id = `m-${(seq += 1)}`;
  const member = { id, name, tier, phone, email, active, joinedAt: new Date().toISOString() };
  members.set(id, member);
  return member;
}

function get(id) {
  return members.get(id) || null;
}

function list() {
  return [...members.values()].map(toPublic);
}

function seed() {
  members.clear();
  seq = 1000;
  // 这几个 id 与预约服务单测/演示脚本里用到的 member_id 对应，保证跨服务调用打得通
  create({ name: '示例会员·窗边喵', tier: 'GOLD', phone: '13800000001', email: 'gold@example.com' });
  create({ name: '示例会员·猫屋常客', tier: 'BLACK_CAT', phone: '13800000002', email: 'vip@example.com' });
  const stopped = create({ name: '示例会员·已停用', tier: 'SILVER' });
  stopped.active = false;
}

module.exports = { create, get, list, seed, toPublic, TIERS };
