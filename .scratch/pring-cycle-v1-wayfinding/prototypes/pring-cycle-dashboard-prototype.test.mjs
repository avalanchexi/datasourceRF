import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const htmlPath = fileURLToPath(new URL('./pring-cycle-dashboard-prototype.html', import.meta.url));
const html = readFileSync(htmlPath, 'utf8');

const requiredFragments = [
  '<html lang="zh-CN" data-theme="light">',
  'projection_set_id · prj_20260821_1812',
  '完整度 · complete',
  '--rise:',
  '--fall:',
  '--font-meta: 12px;',
  '--font-label: 13px;',
  '--font-secondary: 14px;',
  '--font-body: 16px;',
  'let initialTheme = \'light\';',
  'role="tablist" aria-label="报告工作区"',
  'data-report-tab="generate"',
  'data-report-tab="history"',
  'data-report-tab="reader"',
  'data-report-panel="generate"',
  'data-report-panel="history"',
  'data-report-panel="reader"',
  'id="generateReportButton"',
  'id="reportRunStatus"',
  '生成新版本，不覆盖历史报告',
  '证据包预检',
  '演示可生成',
  'fixture 可用 · 部分适配器待实现',
  'P2 · 授权待认证',
  '构建证据包；演示按钮只模拟任务状态',
  '确定性简版',
  '数据覆盖与后续评估',
  'V1目录存在但本页未展开',
  'V1明确排除',
  'CN_EQ_ADV_DEC',
  'CN_CREDIT_IMPULSE',
  'COMEX_GC_ACTIVE_MONTH_SETTLEMENT_USD_OZT',
  '生猪 LH',
  'id="themeToggle"',
  'html[data-theme="light"]',
  'html[data-theme="light"] .icon-button',
  'html[data-theme="light"] .tab.active',
  'html[data-theme="light"] .badge.cyan',
  'prefers-reduced-motion: reduce',
  'align-self: start;',
];

for (const fragment of requiredFragments) {
  assert.ok(html.includes(fragment), `missing required report/design fragment: ${fragment}`);
}

assert.equal(/<script[^>]+src=["']https?:\/\//i.test(html), false, 'prototype must not load remote scripts');
assert.equal(/<link[^>]+href=["']https?:\/\//i.test(html), false, 'prototype must not load remote stylesheets');
assert.equal(html.includes('构建议证据包'), false, 'report copy must not contain the typo 构建议证据包');
assert.equal(/font-size:\s*(?:[0-9]|1[01])(?:\.[0-9]+)?px/.test(html), false, 'readable text must not use font-size below 12px');
assert.equal(/font:\s*(?:[0-9]|1[01])(?:\.[0-9]+)?px\//.test(html), false, 'font shorthand must not use text below 12px');
assert.equal(/font-size=["'](?:[0-9]|1[01])(?:\.[0-9]+)?["']/.test(html), false, 'SVG text must not use font-size below 12px');

const reportPanels = html.match(/data-report-panel=/g) ?? [];
assert.equal(reportPanels.length, 3, 'report workspace must contain exactly three panels');

console.log('prototype contract checks passed');
