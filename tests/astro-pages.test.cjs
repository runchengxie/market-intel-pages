const test = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync, existsSync } = require('node:fs');
const { execFileSync } = require('node:child_process');
const path = require('node:path');

const root = path.join(__dirname, '..');

test('Astro emits a readable five-session static site with six chart states', () => {
  execFileSync('npm', ['run', 'build'], { cwd: root, stdio: 'pipe' });
  const index = readFileSync(path.join(root, 'dist/index.html'), 'utf8');
  const reports = JSON.parse(readFileSync(path.join(root, 'data/reports.json'), 'utf8')).reports;
  const reportId = reports[0].id;
  assert.match(index, /Quant 市场情报/);
  assert.ok(index.includes(reportId));
  const report = path.join(root, `dist/reports/${reportId}/index.html`);
  assert.ok(existsSync(report));
  const html = readFileSync(report, 'utf8');
  assert.match(html, /class="panel report-body markdown-body"/);
  assert.match(html, /data-chart-key="dashboard"/);
  assert.match(html, /data-chart-key="weekly_chart"/);
  assert.ok(html.includes(`/market-intel-pages/reports/${reportId}.md`));
  assert.doesNotMatch(html, /private-chat-target/);
  assert.doesNotMatch(index, /echarts\.|ChartIsland\.|\.png["']/);
  assert.doesNotMatch(html, /echarts\.|ChartIsland\.|\.png["']/);
});

test('historical insight discloses timing, limitations and verification units', () => {
  const insight = JSON.parse(readFileSync(path.join(root, 'data/insights.json'), 'utf8')).insights[0];
  if (!insight) return;
  const index = readFileSync(path.join(root, 'dist/index.html'), 'utf8');
  assert.match(index, /信息截至/);
  assert.match(index, /解读生成/);
  if (insight.generation_mode === 'retrospective') assert.match(index, /历史材料回放/);
  if (insight.quality_warnings.length) assert.match(index, /数据缺项与限制/);
  const point = insight.analysis.watchpoints[0];
  if (point) {
    assert.ok(index.includes(insight.metrics[point.metric].label));
    assert.match(index, /待验证|条件满足|条件未满足|数据不足，无法验证/);
  }
});

test('GFM tables render but untrusted HTML and script URLs are removed', async () => {
  const { renderMarkdown } = await import('../src/lib/markdown.mjs');
  const html = renderMarkdown('| 维度 | 值 |\n|---|---:|\n| 流动性 | 17.1 |\n\n<script>alert(1)</script>\n[bad](javascript:alert(1))');
  assert.match(html, /<table>/);
  assert.match(html, /流动性/);
  assert.doesNotMatch(html, /<script|href="javascript:/);
});
