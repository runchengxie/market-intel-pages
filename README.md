# Quant Market Intel

Quant 市场情报是一个静态报告阅读网站，展示近期晨晚报、每日简评和带来源的市场解读。公开页面和仓库快照保留最近五个有报告的日期，完整报告与历次解读存放在仓库外的私有归档中。

[打开公开网站](https://runchengxie.github.io/market-intel-pages/)。

## 已有功能

- 按日期和晨晚报类型筛选报告，展开正文或查看 Markdown 原文。
- 将晨报与此前最近的一份晚报配对，生成一段每日简评。报告目标日期可以与生成日期不同，配对时同时检查日期和时间。
- 根据配对报告及截止时间内最近五个报告日期的材料生成市场解读，展示变化、分歧、观察条件和逐条来源。
- 校验解读中的引用和数字，并用后续首份符合条件的晚报核对观察条件。原解读和后续结果分别记录。
- 显示原报告时间、数据缺项和生成状态。补发材料及晚于材料截止时间三小时生成的解读标为历史回放。
- 展示最近一次美国宏观与利率日报的 FRED 指标、观测日、来源和缺项；该日期独立于 A 股晨晚报筛选。
- 从明确允许公开的 manifest 导入报告，预览变更后再写入公开快照和私有归档。

窗口按实际存在的报告日期计算。某日只有晚报也会占用一个日期，五个日期的上限不代表最近五个交易日的数据已经齐全。

## 项目边界

本仓库负责报告导入、公开快照、模型解读、静态展示和 GitHub Pages 发布。相邻的 `quant-intel-platform` 负责行情与报告能力，私有仓库 `quant-intel-deploy` 维护生产部署和定时任务。后两者位于服务器 `/home/richard/code/quant/` 下，三个仓库独立管理，本项目没有 Git submodule。

Pages 部署成功只说明网站构建和发布完成。数据是否及时，应查看页面中的原报告时间与数据状态。上游交接方式、已知缺口和运行记录见[每日生成与维护说明](docs/daily-generation-options.md)。

## 本地预览

构建脚本先用 Python 标准库审核公开快照，再调用 Astro 生成首页和逐期静态页。需要 Node.js 24 与锁定依赖。下面的输出目录专用于预览，构建时会重新创建，请勿指向已有业务数据的目录。

```bash
npm ci
preview_root=$(mktemp -d /tmp/qmi-preview.XXXXXX)
python3 scripts/build_site.py --output "$preview_root/market-intel-pages"
python3 -m http.server 8000 --directory "$preview_root"
```

打开 <http://localhost:8000/market-intel-pages/>。构建产物内链接按 GitHub Pages `/market-intel-pages/` 生成，构建目录必须位于仓库外。直接检查静态 HTML 可运行 `npm run build`，其 `dist/` 仅供开发验证。

## 导入与归档

在独立任务工作树中，先预览上游提供的公开报告清单：

```bash
python3 scripts/import_reports.py \
  --manifest /path/to/public/manifest.json \
  --archive-dir /path/to/private-archive
```

检查变更后，使用同样的参数加上 `--apply`。导入器会检查报告内容、生成时间和路径，保存报告修订，再更新最近五个报告日期的快照。清单格式见[导入流程](docs/daily-generation-options.md#导入与核验)。

已有报告索引需要归档或收窄公开窗口时，可单独运行：

```bash
python3 scripts/sync_public_snapshot.py \
  --archive-dir /home/richard/code/.research-data/quant-market-intel-archive
```

该命令先合并报告与简评并核对归档中的 Markdown，再更新公开快照。修改既有报告时优先使用导入器，以便保留修订记录。归档目录应与仓库分开，且互不包含。已提交过的报告仍可从公开 Git 历史中找到，收窄当前快照不会删除那些历史副本。

## 模型生成

生产发布器在本机定时导入新报告时，优先用已登录的 Codex CLI 一次生成结构化解读，并将其通过证据引用与数字校验的概览用作每日简评；CLI 在只读沙盒运行，登录态不上传到 GitHub。无效输出不会写入公开索引，也不会阻止原报告发布。

Actions 部署会保留有效的 Codex 记录；如无记录，结构化解读依次尝试 Gemini、DeepSeek、MiniMax。首个通过校验的结果即停止回退，简评优先沿用同一条解读的概览；所有解读均不可自行补造没有来源的公司新闻或市场归因。若三者均不可用，短简评仍可独立尝试 MiniMax。

本地入口：

| 内容 | 脚本 | 配置 |
|---|---|---|
| 本机默认 | `scripts/generate_codex_commentary.py` | 已登录的 Codex CLI；私有工作与归档目录 |
| 一段每日简评 | `scripts/generate_daily_summary.py` | 有效解读概览；否则 `MINIMAX_API_KEY` |
| 带来源的市场解读 | `scripts/generate_insights.py` | Actions 依次尝试 Gemini、DeepSeek、MiniMax |

本地单独测试可通过 `--provider` 选择 Gemini、DeepSeek 或 MiniMax；GitHub Actions 使用固定的回退顺序。密钥通过本地进程环境或 GitHub Actions Secret 提供，浏览器只读取生成结果。模型输出通过格式校验并不等于新闻事实获得独立核实。

本地模型环境可以复制 `.env.example` 为 `.env`，再加载后运行：

```bash
cp .env.example .env
set -a; . ./.env; set +a
python3 scripts/generate_insights.py --reports data/reports.json --output /tmp/insights.json --provider deepseek --force
```

网页支持跟随系统、浅色和深色主题，右上角按钮会记住选择。

本地生成示例：

```bash
python3 scripts/generate_insights.py \
  --reports data/reports.json \
  --history data/insights.json \
  --output /tmp/quant-market-intel-insights.json \
  --archive-dir /path/to/private-archive
```

源内容、提示词和模型决定缓存是否可复用。`--force` 可重新生成，旧解读仍应保留在归档中。模型缺失、调用失败或材料未齐时，原报告保持可读，页面显示对应状态。

GitHub Actions 在 PR 中执行检查，在 `main` 更新或手动触发时发布。发布流程会读取已部署的近期生成记录，生成新的简评与解读，再上传 Pages 产物。手动输入 `force_summary` 和 `force_insights` 分别控制两种内容的重新生成。

Actions 中的解读与核验记录另存为保留 90 天的 artifact。生产发布器会在部署完成后下载 ledger，写入仓库外的私有归档并核对文件哈希，具体安排见维护说明。

## 文件与数据

| 路径 | 用途 |
|---|---|
| `src/pages/`、`src/components/`、`src/lib/`、`src/styles/` | Astro 首页、逐期静态正文、六图状态与安全 Markdown 渲染 |
| `index.html`、`app.js`、`report-markdown.js`、`summary-utils.js`、`market-daily-utils.js`、`styles.css` | 迁移期间保留的旧页面回退材料，不再作为正式构建的首页 |
| `data/charts/` | 仅收录逐点审核后 `publication: public` 的按期六图 JSON；无批准文件时静态页显示缺项 |
| `data/reports.json`、`reports/` | 公开报告索引、正文与 Markdown 原文 |
| `data/daily_summaries.json` | 每日简评及配对来源 |
| `data/insights.json` | 带来源的解读、生成状态和观察条件结果 |
| `data/market_daily_report.json` | 最近一次美股宏观日报；仅在上游产出并经导入校验后存在 |
| `prompts/` | 两套生成入口使用的提示词 |
| `scripts/` | 导入、归档、生成、比较、健康检查与构建脚本 |
| `tests/` | Python 数据与流水线测试、Node.js 展示辅助函数测试 |
| `docs/` | 维护说明及历史设计记录 |

报告使用 `market_intel_pages.reports.v1`，每条记录包含 `id`、`date`、`kind`、`title`、`summary`、`sections` 和指向 `reports/` 的 `source_url`。`kind` 为 `morning` 或 `evening`。

每日简评使用 `market_intel_pages.daily_summaries.v1`，记录目标日期、正文、晨晚报 ID、生成时间、模型和提示词版本。结构化解读使用 `market_intel_pages.insights.v1`，另记录材料截止时间、内容哈希、段落证据、观察条件与核验结果。

构建时生成的 `data/health.json` 使用 `market_intel_pages.health.v1`，分别计算原报告时间和目标数据日期的年龄，避免补发旧数据掩盖延迟。未提供交易日历目标时，标记 `calendar_unverified`，并保留默认 72 小时的过期提醒。报告正文中的 Markdown 表格、列表和标题会转换为页面结构，单元格与正文仍通过文本节点展示；不执行原文中的 HTML。

## 检查与维护

```bash
npm ci
python3 -m pip install --group dev
ruff check scripts tests tools
ruff format --check scripts tests tools
ty check
vulture scripts tests tools --min-confidence 80
python3 -m pytest
node --test tests/*.cjs
node --check app.js
node --check report-markdown.js
python3 scripts/build_site.py --output /tmp/quant-market-intel-check
pip-audit --strict
python3 tools/audit_structure.py --output /tmp/market-intel-structure.json
```

开发工具版本固定在 `pyproject.toml`。CI 使用 Python 3.11 和 Node.js 24，检查类型、格式、未使用代码、依赖漏洞和 85% 的行与分支联合覆盖率门槛。Ruff 的 McCabe 复杂度上限为 10，另输出 Radon 报告与 AST、模块依赖和静态直接调用清单。不同工具对布尔表达式和推导式的计数不同，数值应在同一工具内比较。

提交前还应运行 `git diff --check`。页面展示有改动时，检查默认日期、日期切换、晨晚报筛选、缺少简评和来源展开等状态。本轮事实、质量指标和遗留项见[维护检查记录](docs/maintenance-audit-2026-09-19.md)。

维护约定见 [AGENTS.md](AGENTS.md)。09-15 的[设计记录](docs/superpowers/specs/2026-09-15-quant-market-intel-pages-design.md)、[网站实施记录](docs/superpowers/plans/2026-09-15-quant-market-intel-pages.md)与 [MiniMax 实施记录](docs/superpowers/plans/2026-09-15-quant-market-intel-minimax.md)保留早期决策背景，当前操作以本页和每日生成说明为准。
