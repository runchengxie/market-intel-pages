const test = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync, existsSync } = require('node:fs');
const { execFileSync } = require('node:child_process');
const path = require('node:path');

const root = path.join(__dirname, '..');

test('Astro emits a readable five-session static site with six chart states', () => {
  execFileSync('npm', ['run', 'build'], { cwd: root, stdio: 'pipe' });
  const index = readFileSync(path.join(root, 'dist/index.html'), 'utf8');
  assert.match(index, /Quant 市场情报/);
  assert.match(index, /2026-09-23-morning/);
  const report = path.join(root, 'dist/reports/2026-09-18-evening/index.html');
  assert.ok(existsSync(report));
  const html = readFileSync(report, 'utf8');
  assert.match(html, /<table/);
  assert.match(html, /data-chart-key="dashboard"/);
  assert.match(html, /data-chart-key="weekly_chart"/);
  assert.match(html, /\/market-intel-pages\/reports\/2026-09-18-evening\.md/);
  assert.match(html, /缺项/);
  assert.doesNotMatch(html, /private-chat-target/);
});

test('GFM tables render but untrusted HTML and script URLs are removed', async () => {
  const { renderMarkdown } = await import('../src/lib/markdown.mjs');
  const html = renderMarkdown('| 维度 | 值 |\n|---|---:|\n| 流动性 | 17.1 |\n\n<script>alert(1)</script>\n[bad](javascript:alert(1))');
  assert.match(html, /<table>/);
  assert.match(html, /流动性/);
  assert.doesNotMatch(html, /<script|href="javascript:/);
});
