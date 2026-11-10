# node-pool — 自建免费节点池

每 30 分钟自动执行：抓取公开节点源 → 去重 → 全量测延迟 → 淘汰 >900ms → 生成带国家分组的 Clash 订阅。

## 部署步骤（约 5 分钟）

1. GitHub 新建一个**公开**仓库（Public，节点数据本身是公开的，公开仓库才能用免费订阅链）
2. 把本目录下 `scripts/` 和 `.github/workflows/update.yml` 按原路径上传到仓库
   （网页上传：Add file → Upload files，把两个文件夹拖进去，注意 .github 是隐藏文件夹，需用 git push 或拖拽）
3. 到仓库 Actions 页确认工作流已启用（首次可能需要点 Enable）
4. 点 Run workflow 手动触发一次，验证跑通

## 订阅链接（二选一，导入 Clash Verge）

- GitHub Raw：`https://raw.githubusercontent.com/<你的用户名>/<仓库名>/main/output/clash.yaml`
- jsDelivr CDN（国内更稳）：`https://cdn.jsdelivr.net/gh/<你的用户名>/<仓库名>@main/output/clash.yaml`

Verge 里新建订阅填入后，把"自动更新"间隔设为 30 分钟，与流水线节奏对齐。

## 调整

- 测速淘汰线：改 update.yml 里 `-max-latency 900ms`（推荐 800-1200ms）
- 数据源增删：改 scripts/fetch_merge.py 顶部 YAML_SOURCES / LINK_SOURCES
- 分频：改 cron（注意 GitHub 定时任务可能有 5-15 分钟延迟，30 分钟是较实用的下限）

## 安全提醒

免费节点运营者不可信：仅用于普通浏览，勿登录银行/支付类账号。
