# 每日数据生成机制与市场记忆

盘点日期：2026-09-19。目标是晨晚报稳定更新、信息时间可追溯、解读有依据、下期能复盘。

## 实际盘点

- Pages 的原始链路是提交报告 → main 推送 → Actions 构建和生成短简评 → GitHub Pages。它不负责采集，也没有导入上游报告的步骤。
- 本次服务器仓库与完整报告归档的最新目标日期均为 2026-09-14，目录更新时间为 09-15。网页的目录更新时间不能证明行情新鲜。
- 服务器已有 systemd 用户定时器：跨市场采集（工作日 06:00）、亚洲市场刷新（17:30）、A 股 current 发布（18:00）、恢复检查（约 45 分钟一次）。不能因为网站落后而再建立另一套行情采集。
- 09-19 的恢复回执：daily_market、minute_market、current_contract 对 09-18 健康；report_datasets 为 not_installed；morning_model 为 disabled_by_configuration，morning_report 为 disabled_dependency；evening_report 为 waiting_source_window。
- 禁用 morning_model 是部署仓库中的显式配置。恢复它涉及现有产品和模型职责，不能把它当作一个遗忘启动的任务。这次不改变该配置，也不调用带 --notify 的恢复入口。
- 现行数据目录的晨报产物中，09-18 的 morning_manifest.json 为零字节，且没有对应 Markdown。上游 morning_pipeline.sh 使用直接重定向写 manifest，失败时会先清空文件。需要在部署 owner 单独修复为临时文件生成、校验、原子替换，并排查该次生产命令失败原因；网站导入器会拒收缺内容或缺时间的报告。
- 初次盘点时 GitHub 仓库没有模型 Secret；09-19 已由用户配置 GEMINI_API_KEY。首轮 gemini-2.5-flash 实际返回 404 NOT_FOUND，切换 gemini-3.8-flash 后已生成并发布一条基于 09-14 材料的历史回放，引用和数字校验通过。运行回执：https://github.com/runchengxie/market-intel-pages/actions/runs/35420008327 。原有简评是人工审核样例，不能据此认为在线 MiniMax 已经运行。

## 方案比较

| 方案 | 优点 | 局限 | 适用判断 |
|---|---|---|---|
| 本机 systemd + 单次幂等流水线 | 接近已有数据、日志和凭据；支持补跑，维护量较小 | 受休眠、网络影响；需持久化状态和截止时间 | **当前主方案**，复用现有采集，补报告就绪到公开发布的桥 |
| 上游 artifact 就绪触发 + 定时对账 | 数据齐了就运行，迟到数据可以补齐；避免靠固定时间猜就绪 | 需明确 manifest 和成功回执，不宜直接监控写到一半的文件 | **推荐叠加**，先完成 manifest 契约，再接生产 owner |
| GitHub Actions 全部生成 | 执行环境干净，日志和产物容易查 | 不能直接访问本地私有数据；schedule 可能延迟，公共仓库闲置时还可能停用 | 适合无本地依赖的公共数据报告；当前只负责校验与发布 |
| Prefect / Dagster 等编排服务 | 多依赖任务、回填、运行视图更完整 | 新服务、数据库、升级与运维成本 | 多市场、多受众、复杂回填成为常态后再选型 |
| LLM Agent 自行决定每日抓取和写作 | 适合临时专题与异常事件探索 | 每日产物的完整性、成本和可复现性较难保证 | 放在可选解读层，基础行情仍由确定性任务生产 |

GitHub 官方明确说明 schedule 在负载高时可能延迟，且公共仓库连续 60 天无活动会停用定时工作流：
https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule

systemd timer 的 Persistent 可用于补触发错过的日历任务；补跑哪一个业务日期仍应由流水线读取交易日历决定：
https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html

## 推荐的数据流

```text
权威行情 owner / 新闻来源
  → 各市场交易日历 + 数据就绪检查
  → 确定性报告生成（不依赖聊天 agent，不发送消息）
  → 明确允许公开的 Markdown manifest
  → 本地全量归档 + 最近五日期快照
  → Gemini 解读（失败不阻断原报告）
  → 下一份晚报核对观察条件
  → 测试、PR、Pages 发布
```

调度器只唤起工作，业务日期由上游日历提供。晨报目标日和生成日可能不同，不能用系统日期直接覆盖。美国、香港、日本与 A 股不能共享一个“昨日”。06:00、17:30 等是现有触发时刻，不是承诺的数据可用时间；晨晚报截止时间应在确认上游依赖后配置。

每次运行用 `(业务日期, 晨/晚, 源内容哈希, 提示词哈希, 模型)` 区分。获取单实例锁，先在临时目录生成，校验通过后原子发布 manifest；重试有次数、退避和截止时间。每阶段保存 started/succeeded/degraded/failed、source_as_of、output_hash、attempts、error_code。不要只看整个进程是否退出 0。

行情缺失、时间未知、schema/hash 不匹配：不冒充新报告。新闻或解读缺失：发布可用事实并显示缺项。回填优先原报告和条件结果，重新生成的解读标为“历史材料回放”，不能算作当时的预测。

## 本次提供的可执行入口

公开 manifest 必须由上游明确提供；不要 glob 整个私人输出目录。示例：

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

路径相对 manifest 所在目录；文件必须含标题与 `生成时间: YYYY-MM-DD HH:MM`（北京时间）。这里的日期仅作格式示例，不表示存在这些报告。

在独立发布工作树中运行：

```bash
python3 scripts/import_reports.py --manifest /path/to/public/manifest.json --archive-dir /path/to/private-archive
# 检查预览后应用；重复相同输入不改目录更新时间
python3 scripts/import_reports.py --manifest /path/to/public/manifest.json --archive-dir /path/to/private-archive --apply
python3 scripts/pipeline_health.py --reports data/reports.json --expected-date YYYY-MM-DD --strict
python3 scripts/generate_insights.py --reports data/reports.json --output data/insights.json --archive-dir /path/to/private-archive
python3 -m unittest discover -s tests
node --test tests/*.cjs
python3 scripts/build_site.py --output /path/to/site-artifact
```

`--expected-date` 应传入 owner 交易日历的目标日期；未传时仅提供 72 小时阈值提醒，不声称已经验证交易日完整性。流水线需在独立任务工作树提交公开快照、正常推送并经 PR 合并；systemd 应调用稳定生产目录中的桥接入口，不能固定引用临时工作树。

已找到无投递的晨报入口 `a-share-daily morning --date YYYYMMDD` 与 `a-share-daily morning-report --manifest ... --news ... --out ...`（省略 `--send-feishu`）。接生产前尚需明确公开 manifest 的 owner、晚报的无投递调用、report_datasets 是否仍是必需依赖，以及停用旧晨报模型后的替代路径。当前没有足够依据重开这些生产任务，因此本次交付导入契约、验证入口和迁移步骤，未安装第二套调度。

## Gemini 与对比评估

仓库 Secret：`GEMINI_API_KEY`；可选变量 `GEMINI_MODEL`、`INSIGHT_PROVIDER=gemini|minimax`。默认模型是已通过真实调用验证的 `gemini-3.8-flash`，可用变量覆盖；浏览器不发起模型调用。切换 MiniMax 时使用 `MINIMAX_API_KEY` 和 `MINIMAX_MODEL`。提供方 429/5xx/连接错误最多三次尝试；认证失败不重试。失败只记录错误类型、HTTP 状态码及白名单中的 API 错误代码，不把请求 URL、服务端正文或密钥写入网页。

模型结构化输出能力： https://ai.google.dev/gemini-api/docs/structured-output

模型目录： https://ai.google.dev/gemini-api/docs/models

同一份历史报告比较两家输出：

```bash
python3 scripts/compare_models.py --reports data/reports.json --output-dir /path/to/private-comparison
```

结构校验检查引用存在、数字来自引用、观察阈值来自已提取指标；它不证明因果或观点正确。人工比较证据支持、因果克制、对缺项的处理、可验证性和中文质量。没有实际 API 输出时，不给模型胜负结论。先积累约十个有效交易日样本，再决定默认提供方。

## 借鉴 MaiBot：保留经历，让表达自然

参考其自然表达、长期交互和发言时机思路，不引入整个聊天框架：
https://github.com/Mai-with-u/MaiBot

这一版实现来源证据、信息截止时间、生成时间、观点版本与追加式结果记录。正文可以口语化，事实和观察阈值仍来自同一份材料。生成时间超过材料截止三小时的解读标为历史回放；它不能混入真实前瞻记录。观察条件结果是 met / not_met / pending / unverifiable，不是投资收益或预测胜率。

本地 `--archive-dir` 保存不可覆盖的 insights、outcomes、report_revisions。报告修订保留旧版本；结果更新另存回执。网页只保留当前窗口内可引用证据，私有全量记录不进入 Pages。

Actions 额外上传版本与结果 artifact，保留 90 天。这是中转备份，不是永久档案；若使用云端生成，应在到期前下载到私有全量归档。对长期运行，更推荐本地生成并直接写永久归档，然后让 Pages 消费经过审核的快照。

09-19 首条真实解读的 artifact 已下载到服务器私有归档 `actions-ledgers/35420008327/`，位于 `/home/richard/code/.research-data/quant-market-intel-archive/` 下。后续 artifact 的持续同步仍需纳入生产调度，单次下载不等于已建立永久自动同步。

下一阶段可增加主题/事件/观点/结果的结构化表、按时间和来源检索、相似案例与反例各自召回。风格偏好单独存储，不从聊天用语自动更新事实或投资立场。数字概率只有在定义事件、预测窗口和校准方法之后才引入。异常事件点评另设去重、冷却和来源确认，不与每日准点产出混成一个无限运行的 agent。
