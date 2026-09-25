const test = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync, existsSync, cpSync, writeFileSync, mkdtempSync, rmSync, readdirSync } = require('node:fs');
const { execFileSync } = require('node:child_process');
const path = require('node:path');

const root = path.join(__dirname, '..');

test('Astro emits a readable five-session static site with six chart states', () => {
  execFileSync('npm', ['run', 'build'], { cwd: root, stdio: 'pipe' });
  const index = readFileSync(path.join(root, 'dist/index.html'), 'utf8');
  const reports = JSON.parse(readFileSync(path.join(root, 'data/reports.json'), 'utf8')).reports;
  const reportId = reports[0].id;
  assert.match(index, /Quant 市场情报/);
  assert.match(index, /id="theme-toggle"/);
  assert.match(index, /市场驱动/);
  assert.match(index, /经济数据、公司新闻与报告全文/);
  const styles = readdirSync(path.join(root, 'dist/_astro')).filter((name) => name.endsWith('.css'))
    .map((name) => readFileSync(path.join(root, `dist/_astro/${name}`), 'utf8')).join('\n');
  assert.match(styles, /:root\[data-theme=?"?dark/);
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
  assert.match(index, /来源：<a href="https:\/\//);
  assert.doesNotMatch(index, /\| 流动性 \|/);
  assert.match(html, /<table>/);
});

test('Astro market brief shows verified primary facts, semantic sources and compact secondary content', () => {
  const fixture = mkdtempSync(path.join(path.dirname(root), 'market-daily-brief-'));
  try {
    cpSync(path.join(root, 'data'), path.join(fixture, 'data'), { recursive: true });
    cpSync(path.join(root, 'reports'), path.join(fixture, 'reports'), { recursive: true });
    const file = path.join(fixture, 'data/market_daily_report.json');
    const report = JSON.parse(readFileSync(file, 'utf8'));
    const reportDate = report.run_id.slice(6);
    const fact = (id, value, unit, source, source_url, metric, observation_date) => ({
      id, value, unit, source, source_url, metric, observation_date,
    });
    report.facts.push(
      fact('treasury.2y.level_percent', 3.85, 'percent', 'US Treasury', 'https://home.treasury.gov/data', 'yield_level', reportDate),
      fact('cross_asset.brent.close', 68.25, 'USD/barrel', 'Yahoo Finance', 'https://finance.yahoo.com/quote/BZ=F/', 'close', reportDate),
      fact('cross_asset.brent.change_percent', 1.25, 'percent', 'Yahoo Finance', 'https://finance.yahoo.com/quote/BZ=F/', 'daily_return', reportDate),
    );
    writeFileSync(file, JSON.stringify(report));
    execFileSync('npm', ['run', 'build', '--', '--outDir', path.join(fixture, 'built')], {
      cwd: root, stdio: 'pipe', env: { ...process.env, ASTRO_DATA_ROOT: fixture },
    });
    const html = readFileSync(path.join(fixture, 'built/index.html'), 'utf8');
    assert.match(html, /美股收盘/);
    assert.match(html, /美债收益率/);
    assert.match(html, /3\.850%/);
    assert.match(html, /跨资产行情/);
    assert.match(html, /68\.25 USD\/barrel/);
    assert.match(html, />美国财政部</);
    assert.match(html, />Yahoo Finance</);
    assert.match(html, /来源1/);
    assert.match(html, /经济数据、公司新闻与报告全文/);
  } finally {
    rmSync(fixture, { recursive: true, force: true });
  }
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

test('market daily source URLs become compact numbered links only in the rendered page', async () => {
  const { renderMarkdown } = await import('../src/lib/markdown.mjs');
  const source = '- 来源：https://example.com/one, https://example.org/two';
  const html = renderMarkdown(source, { compactSources: true });
  assert.match(html, /<a href="https:\/\/example.com\/one"[^>]*>来源1<\/a>/);
  assert.match(html, /<a href="https:\/\/example.org\/two"[^>]*>来源2<\/a>/);
  assert.doesNotMatch(html, />https:\/\/example.com\/one</);
  assert.match(renderMarkdown(source), /https:\/\/example.com\/one/);
});

test('single table-row evidence is labelled instead of showing raw Markdown pipes', async () => {
  const { formatEvidenceLine } = await import('../src/lib/evidence.mjs');
  assert.equal(formatEvidenceLine('六维观察', '| 流动性 | 25.4 | 偏弱 | 成交额/历史中位 0.90x |'),
    '维度：流动性；观察分：25.4；状态：偏弱；证据：成交额/历史中位 0.90x');
  assert.equal(formatEvidenceLine('七、行业板块 TOP10', '| 电子 | +0.94% | +0.53% | 436 | 59.9% |'),
    '行业：电子；均涨跌：+0.94%；中位数：+0.53%；家数：436；上涨率：59.9%');
  assert.equal(formatEvidenceLine('市场总览', '上涨 1891 家 | 下跌 3564 家'), '上涨 1891 家 | 下跌 3564 家');
});

test('verified watchpoint outcome shows labelled table evidence', () => {
  const fixture = mkdtempSync(path.join(path.dirname(root), 'market-insight-outcome-'));
  try {
    cpSync(path.join(root, 'data'), path.join(fixture, 'data'), { recursive: true });
    cpSync(path.join(root, 'reports'), path.join(fixture, 'reports'), { recursive: true });
    const file = path.join(fixture, 'data/insights.json');
    const insights = JSON.parse(readFileSync(file, 'utf8'));
    const outcome = insights.outcomes[0];
    outcome.status = 'met';
    outcome.report_id = '2026-09-23-evening';
    outcome.observed_date = '2026-09-23';
    outcome.observed_value = 25.4;
    outcome.evidence = [{ report_id: outcome.report_id, section: '六维观察', text: '| 流动性 | 25.4 | 偏弱 | 成交额/历史中位 0.90x |' }];
    writeFileSync(file, JSON.stringify(insights));
    execFileSync('npm', ['run', 'build', '--', '--outDir', path.join(fixture, 'built')], {
      cwd: root, stdio: 'pipe', env: { ...process.env, ASTRO_DATA_ROOT: fixture },
    });
    const html = readFileSync(path.join(fixture, 'built/index.html'), 'utf8');
    assert.match(html, /查看核对依据/);
    assert.match(html, /维度：流动性；观察分：25\.4；状态：偏弱/);
    assert.doesNotMatch(html, /\| 流动性 \|/);
  } finally {
    rmSync(fixture, { recursive: true, force: true });
  }
});
