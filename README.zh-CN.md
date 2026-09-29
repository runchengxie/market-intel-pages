# Quant 市场情报

[English README](README.md)

日报已经迁入 `quant-intel-platform`。本仓库暂留旧版页面、历史报告和回滚入口，不再作为新增日报的发布目标。旧首页会跳转到新站；访问旧首页并加上 `?legacy=1` 可查看旧版。报告仅供研究参考。

[打开新日报](https://runchengxie.github.io/quant-intel-platform/) · [查看旧版归档](https://runchengxie.github.io/quant-intel-pages/?legacy=1)

## 能看到什么

- 07:00 美股收盘复盘：指数、已核实重点个股、美债收益率及日变动、布伦特原油、金银和比特币行情。
- 19:00 亚洲市场收盘复盘：A 股与亚洲市场表现、六维观察、图表和次日验证。
- 原报告、Markdown 阅读版和纯文本下载。需要核对数字时，以带来源的原报告为准。

页面的 07:00 和 19:00 是北京时间的发布目标，并不保证每次准点或每项数据齐全。请以页面显示的实际生成时间、观测日和数据状态判断新鲜度。五个日期的窗口也不表示五个交易日的数据都已齐全。

## 快速预览

准备 Python 3.11、Node.js 24 和 npm。在仓库根目录执行：

```bash
npm ci
preview_root=$(mktemp -d /tmp/qmi-preview.XXXXXX)
python3 scripts/build_site.py --output "$preview_root/quant-intel-pages"
python3 -m http.server 8000 --directory "$preview_root"
```

然后打开 <http://localhost:8000/quant-intel-pages/>。输出目录由 `mktemp` 新建；构建会重新创建指定目录，请勿改成存放业务数据的路径。只想检查 Astro 页面时，可运行 `npm run build`。

## 到哪里找

| 目录 | 内容 |
|---|---|
| `src/` | 正式 Astro 网站和 `/legacy/` 旧版回退页面 |
| `artifacts/public/` | 已审核、可公开的近期报告与数据，构建后仍以 `/data/`、`/reports/` 提供下载 |
| `scripts/`、`prompts/` | 导入、生成、校验与构建脚本；模型提示词 |
| `configs/` | 无密钥的配置样例，真实凭据放在仓库外 |
| `tests/`、`tools/` | 测试与结构审计工具 |
| `docs/` | 维护方法、数据契约和历史设计记录 |

本仓库没有 Git submodule。日报展示代码和公开快照已保留历史地并入 `quant-intel-platform/web/`，新站由平台仓库统一构建。生产发布与定时任务由 `quant-intel-deploy` 负责。

这里的导入、快照和模型脚本只作为旧版回滚材料保存，不再接收新的生产报告。旧站的模型密钥不会自动迁移到新站。历史实现细节见[开发与数据维护](docs/technical-guide.md#项目边界)。

## 常见问题

为什么网页有缺项？报告只展示通过日期、来源和公开审核的字段。模型输出通过格式校验，不代表新闻事实已核实；缺少可靠材料时会保留空缺。

数据和报告为什么不直接放在网站根目录？`artifacts/public/` 是 Git 中的公开输入，构建器会把它们放到网站的 `/data/` 和 `/reports/`。因此下载网址没有增加 `artifacts/public/` 这一层。

如何导入报告或运行完整检查？参见[开发与数据维护](docs/technical-guide.md)、[每日生成与维护说明](docs/daily-generation-options.md)和[仓库协作约定](AGENTS.md)。六图的公开审核另见[审核记录](docs/chart-review-2026-09-25.md)。
