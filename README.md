# A 股股票跟踪系统

本仓库当前实现第一阶段后端骨架：FastAPI + SQLite，以及股票池、标签、投资逻辑卡片、交易纪律计划的 CRUD API。

## 快速开始

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --app-dir backend
```

启动后访问：

- API 健康检查：<http://127.0.0.1:8000/health>
- OpenAPI 文档：<http://127.0.0.1:8000/docs>

默认 SQLite 数据库位置：`data/app.db`。可通过 `DATABASE_URL` 环境变量覆盖。

## 已实现 API

- `GET /api/v1/stocks`：查询股票池
- `POST /api/v1/stocks`：新增股票
- `GET /api/v1/stocks/{stock_id}`：查询股票
- `PUT /api/v1/stocks/{stock_id}`：更新股票
- `DELETE /api/v1/stocks/{stock_id}`：归档股票
- `GET /api/v1/tags`：查询标签
- `POST /api/v1/tags`：新增标签
- `PUT /api/v1/tags/{tag_id}`：更新标签
- `DELETE /api/v1/tags/{tag_id}`：删除标签
- `POST /api/v1/stocks/{stock_id}/tags/{tag_id}`：绑定标签
- `DELETE /api/v1/stocks/{stock_id}/tags/{tag_id}`：移除标签
- `GET /api/v1/stocks/{stock_id}/research-card`：查询投资逻辑卡片
- `PUT /api/v1/stocks/{stock_id}/research-card`：创建或更新投资逻辑卡片
- `GET /api/v1/stocks/{stock_id}/discipline-plan`：查询交易纪律计划
- `PUT /api/v1/stocks/{stock_id}/discipline-plan`：创建或更新交易纪律计划
- `POST /api/v1/quotes/refresh`：刷新股票池行情
- `GET /api/v1/quotes/latest`：查询股票池最新行情
- `GET /api/v1/stocks/{stock_id}/quote`：查询单只股票最新行情
- `GET /api/v1/data-sources`：查询数据源配置
- `POST /api/v1/data-sources`：新增数据源配置
- `GET /api/v1/data-sources/logs`：查询数据源调用日志
- `GET /api/v1/data-sources/health`：查询数据健康检查记录
- `GET /api/v1/system/scheduler`：查询定时任务状态
- `POST /api/v1/system/scheduler/start`：启动定时任务
- `POST /api/v1/system/scheduler/stop`：停止定时任务
- `POST /api/v1/system/scheduler/quote-refresh/run`：立即执行一次行情刷新任务

## 行情模块说明

当前行情模块提供 `akshare` 实时行情 provider，并保留离线可测试的 `mock` provider；后续仍可继续接入 Tushare、东方财富等备用源。每次刷新会写入行情快照、数据源调用日志和数据健康检查记录。

行情刷新会按 `data_source_configs.priority` 从小到大尝试启用的数据源；主源失败时会继续尝试备用源，并在返回结果和 `market_quotes.is_fallback` 中标记 fallback 状态。内置 provider 包括 `akshare`、`mock`、`failing`、`missing_price` 和 `stale`，其中 `akshare` 使用 AKShare 的 `stock_zh_a_spot_em()` 获取沪深京 A 股实时行情并标准化为系统字段。

## 定时行情刷新

系统集成 APScheduler。默认 `ENABLE_QUOTE_SCHEDULER=false`，启动服务时只注册任务但不自动运行；可通过环境变量启用自动刷新：

```bash
ENABLE_QUOTE_SCHEDULER=true QUOTE_REFRESH_INTERVAL_SECONDS=15 uvicorn app.main:app --reload --app-dir backend
```

默认 `QUOTE_SCHEDULER_SKIP_NON_TRADING=true`，非 A 股连续竞价时段会跳过自动刷新；手动调用 `/api/v1/system/scheduler/quote-refresh/run?force=true` 可强制执行一次刷新。

## AKShare 行情源

安装依赖后，可以手动指定 AKShare provider 刷新行情：

```bash
curl -X POST 'http://127.0.0.1:8000/api/v1/quotes/refresh?provider=akshare'
```

也可以在 `data_source_configs` 中新增 `provider=akshare`、`data_type=quote`、较小 `priority` 的配置，让定时刷新优先使用 AKShare；若主源失败，系统会继续按优先级尝试备用源。
