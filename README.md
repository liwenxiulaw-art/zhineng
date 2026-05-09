# A 股股票跟踪系统

本仓库当前实现第一阶段后端骨架：FastAPI + SQLite，以及股票池、标签、投资逻辑卡片、交易纪律计划的 CRUD API。

## 快速开始

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
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
