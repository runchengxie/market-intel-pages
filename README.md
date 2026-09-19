# Quant Market Intel

Quant 市场情报是一个静态报告阅读网站，展示近期晨晚报、每日简评和带来源的市场解读。公开页面和仓库快照保留最近五个有报告的日期，完整报告与历次解读存放在仓库外的私有归档中。

[打开公开网站](https://runchengxie.github.io/market-intel-pages/)。

## 已有功能

- 按日期和晨晚报类型筛选报告，展开正文或查看 Markdown 原文。
- 将晨报与此前最近的一份晚报配对，生成一段每日简评。报告目标日期可以与生成日期不同，配对时同时检查日期和时间。
- 根据配对报告及截止时间内最近五个报告日期的材料生成市场解读，展示变化、分歧、观察条件和逐条来源。
- 校验解读中的引用和数字，并用后续首份符合条件的晚报核对观察条件。原解读和后续结果分别记录。
- 显示原报告时间、数据缺项和生成状态。晚于材料截止时间三小时生成的解读标为历史回放。
- 从明确允许公开的 manifest 导入报告，预览变更后再写入公开快照和私有归档。

窗口按实际存在的报告日期计算。某日只有晚报也会占用一个日期，五个日期的上限不代表最近五个交易日的数据已经齐全。

## 项目边界

本仓库负责报告导入、公开快照、模型解读、静态展示和 GitHub Pages 发布。相邻的 `quant-intel-platform` 负责行情与报告能力，私有仓库 `quant-intel-deploy` 维护生产部署和定时任务。后两者位于服务器 `/home/richard/code/quant/` 下，三个仓库独立管理，本项目没有 Git submodule。

Pages 部署成功只说明网站构建和发布完成。数据是否及时，应查看页面中的原报告时间与数据状态。上游交接方式、已知缺口和运行记录见[每日生成与维护说明](docs/daily-generation-options.md)。

## 本地预览

构建脚本只使用 Python 标准库。下面的输出目录专用于预览，构建时会重新创建，请勿指向已有业务数据的目录。

```bash
python3 scripts/build_site.py --output /tmp/quant-market-intel-site
python3 -m http.server 8000 --directory /tmp/quant-market-intel-site
```

打开 <http://localhost:8000>。构建目录必须位于仓库外。

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

两套生成入口分别维护简评和结构化解读：

| 内容 | 脚本 | 配置 |
|---|---|---|
| 一段每日简评 | `scripts/generate_daily_summary.py` | `MINIMAX_API_KEY`，可选 `MINIMAX_MODEL` |
| 带来源的市场解读 | `scripts/generate_insights.py` | 默认使用 `GEMINI_API_KEY`，可选 `GEMINI_MODEL` 和 `INSIGHT_PROVIDER` |

结构化解读默认模型为 `gemini-3.8-flash`。截至 2026-09-19，仓库已配置 `GEMINI_API_KEY`，并成功生成一条基于 09-14 材料的历史回放。仓库原有短简评标记为 `chatgpt-reviewed`，不能据此判断 MiniMax 在线调用是否成功。

将 `INSIGHT_PROVIDER` 设为 `minimax` 可切换结构化解读的提供方，使用 `MINIMAX_API_KEY` 和 `MINIMAX_MODEL`。密钥通过本地进程环境或 GitHub Actions Secret 提供，浏览器只读取生成结果。

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

Actions 中的解读与核验记录另存为保留 90 天的 artifact。长期记录需要持续导出到私有归档，具体安排见维护说明。

## 文件与数据

| 路径 | 用途 |
|---|---|
| `index.html`、`app.js`、`summary-utils.js`、`styles.css` | 页面结构、展示逻辑和样式 |
| `data/reports.json`、`reports/` | 公开报告索引、正文与 Markdown 原文 |
| `data/daily_summaries.json` | 每日简评及配对来源 |
| `data/insights.json` | 带来源的解读、生成状态和观察条件结果 |
| `prompts/` | 两套生成入口使用的提示词 |
| `scripts/` | 导入、归档、生成、比较、健康检查与构建脚本 |
| `tests/` | Python 数据与流水线测试、Node.js 展示辅助函数测试 |
| `docs/` | 维护说明及历史设计记录 |

报告使用 `market_intel_pages.reports.v1`，每条记录包含 `id`、`date`、`kind`、`title`、`summary`、`sections` 和指向 `reports/` 的 `source_url`。`kind` 为 `morning` 或 `evening`。

每日简评使用 `market_intel_pages.daily_summaries.v1`，记录目标日期、正文、晨晚报 ID、生成时间、模型和提示词版本。结构化解读使用 `market_intel_pages.insights.v1`，另记录材料截止时间、内容哈希、段落证据、观察条件与核验结果。

构建时生成的 `data/health.json` 使用 `market_intel_pages.health.v1`，按原报告时间计算数据年龄。上游未提供交易日历目标时，只给出默认 72 小时的过期提醒。报告与模型正文通过文本节点展示。

## 检查与维护

```bash
python3 -m unittest discover -s tests
node --test tests/*.cjs
node --check app.js
python3 scripts/build_site.py --output /tmp/quant-market-intel-check
```

提交前还应运行 `git diff --check`。页面展示有改动时，检查默认日期、日期切换、晨晚报筛选、缺少简评和来源展开等状态。

维护约定见 [AGENTS.md](AGENTS.md)。09-15 的[设计记录](docs/superpowers/specs/2026-09-15-quant-market-intel-pages-design.md)、[网站实施记录](docs/superpowers/plans/2026-09-15-quant-market-intel-pages.md)与 [MiniMax 实施记录](docs/superpowers/plans/2026-09-15-quant-market-intel-minimax.md)保留早期决策背景，当前操作以本页和每日生成说明为准。
