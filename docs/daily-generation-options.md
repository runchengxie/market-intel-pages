# 每日生成与维护说明

核对日期：2026-09-19。本文说明报告从上游生产到公开网站的交接方式、已实现的检查，以及仍需完成的生产接入。

## 仓库职责与发布流程

| 仓库 | 职责 |
|---|---|
| `market-intel-pages` | 导入明确可公开的报告，维护近期快照、模型解读、来源核验和静态网站 |
| `quant-intel-platform` | 提供行情处理和报告生产能力 |
| `quant-intel-deploy` | 私有部署配置、生产定时器和恢复任务 |

后两者位于服务器 `/home/richard/code/quant/` 下。三个仓库分别维护，本项目没有 submodule。上游生产问题在对应仓库修复，Pages 侧负责检查交接材料并准确显示状态。

当前 Pages 工作流在 PR 中运行检查，在 `main` 推送或手动触发时构建和发布。构建先读取已提交的报告快照，随后生成简评和结构化解读。工作流自身不采集行情，也没有定时拉取本地私有报告的步骤。

目标流程如下，其中从生产报告到公开 manifest 的持续交接仍需接入部署侧：

```text
行情来源与交易日历
  → 上游采集、数据就绪检查
  → 报告生成
  → 明确允许公开的 manifest
  → Pages 导入器：私有归档与近期快照
  → 模型解读与观察条件核验
  → 检查、PR、GitHub Pages 发布
```

报告缺失或时间无法确认时，保留缺项状态。新闻或模型解读不可用时，仍可发布已经验证的原报告。补发材料与重新生成的历史解读需要说明时间，供读者判断信息在当时是否可用。

## 09-19 初次盘点记录

以下记录描述当天维护开始时的状态，供排查和后续修复核对：

- Pages 仓库和完整归档的最新报告目标日期均为 09-14，索引更新时间为 09-15。网站部署成功，数据仍然落后。
- 服务器已有 systemd 用户定时器，分别在工作日 06:00 采集跨市场数据、17:30 刷新亚洲市场、18:00 发布 A 股 current 数据，并约每 45 分钟进行一次恢复检查。
- 恢复回执显示，`daily_market`、`minute_market`、`current_contract` 对 09-18 健康。`report_datasets` 为 `not_installed`，`morning_model` 为 `disabled_by_configuration`，`morning_report` 为 `disabled_dependency`，`evening_report` 为 `waiting_source_window`。
- `morning_model` 的停用来自部署仓库的显式配置。接回晨报前，需要确认停用该模型后的报告生产路径。
- 09-18 的 `morning_manifest.json` 为零字节，且没有对应 Markdown。上游 `morning_pipeline.sh` 直接重定向写入 manifest，命令失败时会先清空文件。部署侧需要查明失败原因，并改为临时文件生成、校验后替换。

既有采集任务应继续由部署侧维护。接入 Pages 时，重点补齐报告完成、允许公开和发布完成之间的交接记录。

## 模型运行记录

09-19 已配置仓库 Secret `GEMINI_API_KEY`。首次使用 `gemini-2.5-flash` 返回 `404 NOT_FOUND`，切换为 `gemini-3.8-flash` 后成功生成一条基于 09-14 材料的历史回放，来源引用与数字校验通过。详情见 [Actions 运行记录 35420008327](https://github.com/runchengxie/market-intel-pages/actions/runs/35420008327)。

原有短简评为 `chatgpt-reviewed` 人工审核样例。MiniMax 在线效果需要另行调用核对，不能从静态样例推断。

## 导入与核验

公开 manifest 由上游明确提供，只列允许公开的 Markdown。示例中的日期仅展示格式：

```json
{
  "schema_version": "market_intel_pages.import.v1",
  "publication": "public",
  "reports": [
    {"path": "evening.md", "date": "2026-09-18", "kind": "evening"},
    {"path": "morning.md", "date": "2026-09-18", "kind": "morning"}
  ]
}
```

路径相对 manifest 所在目录，文件需包含标题、正文和 `生成时间: YYYY-MM-DD HH:MM`，时间按北京时间解析。导入器检查路径边界、日期、报告类型和必需内容。重复相同输入不会更新索引时间。

在独立任务工作树中先预览：

```bash
python3 scripts/import_reports.py \
  --manifest /path/to/public/manifest.json \
  --archive-dir /path/to/private-archive
```

检查报告日期、内容和变更数量后应用：

```bash
python3 scripts/import_reports.py \
  --manifest /path/to/public/manifest.json \
  --archive-dir /path/to/private-archive \
  --apply
```

导入完成后检查数据状态，生成解读并构建：

```bash
python3 scripts/pipeline_health.py \
  --reports data/reports.json \
  --expected-date YYYY-MM-DD \
  --strict
python3 scripts/generate_insights.py \
  --reports data/reports.json \
  --history data/insights.json \
  --output data/insights.json \
  --archive-dir /path/to/private-archive
python3 scripts/build_site.py --output /tmp/quant-market-intel-check
```

`--expected-date` 应替换为上游交易日历给出的目标日期。未提供时，健康检查默认按原报告生成时间使用 72 小时阈值。该结果描述数据年龄，完整的晨晚报到齐情况仍需结合报告类型与配对状态检查。

随后执行 [README 中的完整检查](../README.md#检查与维护)，提交公开快照，经 PR 合并后发布。生产任务应调用稳定发布目录中的入口。

## 接入生产时需要明确的事项

已有无消息投递的入口包括 `a-share-daily morning --date YYYYMMDD` 和 `a-share-daily morning-report --manifest ... --news ... --out ...`，使用时省略 `--send-feishu`。接入前还需明确公开 manifest 的维护方、晚报调用方式、`report_datasets` 是否仍为必需依赖，以及旧晨报模型停用后的替代路径。

业务日期由上游交易日历提供。晨报目标日可能早于生成日，不同市场也可能处于不同交易日。06:00、17:30 等只是现有任务的触发时刻，报告截止时间需结合实际依赖确定。

持续运行的发布任务还应具备以下能力，当前导入器并未独立承担这些调度职责：

- 用业务日期、晨晚报类型、源内容哈希、提示词哈希和模型标识区分一次生成。
- 避免同一任务并发运行，在临时目录校验产物后发布 manifest。
- 保存各阶段状态、材料时间、产物哈希、重试次数和错误类型。
- 为重试设置次数、间隔与截止时间，并对迟到数据和补发报告留存回执。

## 调度方案取舍

| 方案 | 适用情况 | 需要承担的维护工作 |
|---|---|---|
| 复用本机 systemd 和单次流水线 | 当前数据、日志与凭据均在本地，便于补跑 | 持久化状态，处理休眠、网络和任务截止时间 |
| 报告就绪触发，配合定时对账 | 上游能提供完整 manifest，迟到数据需要及时补齐 | 定义完成标记和成功回执，避免读取写到一半的文件 |
| GitHub Actions 生成与发布 | 输入完全公开，或已有可供云端读取的产物 | 私有数据交接和定时任务延迟 |
| Prefect、Dagster 等编排服务 | 多市场、多受众和复杂回填已成为日常需求 | 额外服务、数据库、升级与运维 |
| 由 LLM agent 探索和写作 | 临时专题或异常事件分析 | 限定任务范围、成本和来源，保留确定性基础报告 |

现有环境适合复用本机调度，再补报告就绪触发和定时对账。GitHub Actions 的定时工作流可能延迟，公共仓库连续 60 天无活动时还会停用，参见 [GitHub 官方说明](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)。

## 解读生成与模型比较

结构化解读默认使用 `gemini-3.8-flash`。可选变量为 `GEMINI_MODEL` 与 `INSIGHT_PROVIDER`，后者接受 `gemini` 或 `minimax`。选择 MiniMax 时使用 `MINIMAX_API_KEY` 和 `MINIMAX_MODEL`。API 密钥在生成进程中读取。

生成器对限流、服务器错误和连接问题最多尝试三次，认证失败直接返回。公开诊断只包含错误类型、HTTP 状态码和白名单中的 API 错误代码。提供方输出形式参见 [Gemini 结构化输出文档](https://ai.google.dev/gemini-api/docs/structured-output)。

同一份历史材料可分别生成两家样本：

```bash
python3 scripts/compare_models.py \
  --reports data/reports.json \
  --output-dir /path/to/private-comparison
```

脚本保存各提供方的运行状态、样本和人工审核问题。检查引用存在、数字来自引用、观察阈值来自已提取指标后，还需人工判断证据是否支持观点、因果是否克制、缺项是否说清，以及中文是否自然。积累约十个有效交易日的真实样本后，再评估是否更换默认提供方。

## 长期记录与观察条件

当前已保存材料来源、信息截止时间、生成时间、观点版本和独立的条件核验结果。生成时间超过材料截止时间三小时的解读标为历史回放，避免混入当时可用的前瞻记录。

观察条件使用晚报中可提取的指标作为阈值。后续首份符合日期和时间条件的晚报到来后，记录 `met`、`not_met`、`pending` 或 `unverifiable`。这些状态只表示条件是否成立，不能换算为投资收益或预测胜率。

本地 `--archive-dir` 以追加方式保存 `insights`、`outcomes` 和 `report_revisions`。解读归档还保存报告快照与核验来源，使离开公开窗口的旧观点能够继续核对。报告修订保留旧版本，结果变化另存回执。

Actions 上传的解读与结果 artifact 保留 90 天，作为中转备份使用。09-19 首条真实解读的 artifact 已下载至服务器私有归档的 `actions-ledgers/35420008327/`，归档根目录为 `/home/richard/code/.research-data/quant-market-intel-archive/`。后续 artifact 的持续同步仍需接入生产调度。

早期讨论参考了 [MaiBot](https://github.com/Mai-with-u/MaiBot) 在自然表达和长期交互方面的思路。当前项目只实现报告来源、解读版本和条件结果的长期保存。主题检索、相似案例与反例召回、独立风格偏好，以及异常事件点评仍属后续方向。
