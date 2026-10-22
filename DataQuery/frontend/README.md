# DataQuery数据仓库前端

面向现有 Data Agent 后端的可部署 Web 界面。用户可以用自然语言提问，实时查看 SSE 分析进度，并浏览或导出查询结果。

## 环境要求

- Node.js `>=22.13.0`
- 一个可访问的 FastAPI Data Agent 后端（默认本地地址为 `http://127.0.0.1:8000/api/query`）

当前前端未启用用户认证；`app/chatgpt-auth.ts` 只是未接入的辅助代码，不能视为安全边界。

## 本地启动

前端通过同源 API Route `/api/query` 代理后端 SSE，浏览器不直接访问 FastAPI，因此不需要配置 CORS。请按以下顺序启动。

### 1. 启动基础设施

在仓库根目录执行：

```bash
docker compose -f docker/docker-compose.yaml up -d --build
```

等待 MySQL、Elasticsearch、Qdrant 和 Embedding 服务 ready，然后构建元知识索引：

```bash
uv run python -m app.scripts.build_meta_knowledge -c conf/meta_config.yaml
```

### 2. 启动 FastAPI 后端

仍在仓库根目录执行：

```bash
uv run uvicorn main:app --host 127.0.0.1 --port 8000
```

也可以执行：

```bash
uv run python main.py
```

先用 curl 确认后端能返回 SSE：

```bash
curl -N \\
  -H 'Accept: text/event-stream' \\
  -H 'Content-Type: application/json' \\
  -X POST http://127.0.0.1:8000/api/query \\
  -d '{"query":"统计华北地区销售总额"}'
```

### 3. 启动前端

```bash
cd frontend
npm ci
cp .env.example .env.local
npm run dev -- --host 127.0.0.1 --port 3000
```

本地 `.env.local` 可以显式配置后端地址：

```dotenv
DATA_AGENT_API_URL=http://127.0.0.1:8000/api/query
```

浏览器访问：

```text
http://127.0.0.1:3000
```

数据链路为：

```text
浏览器 → 前端同源 /api/query → FastAPI /api/query → LangGraph → 数据库/检索服务
```

## 上线配置

生产环境不能使用 `127.0.0.1`。必须把 `DATA_AGENT_API_URL` 配置为部署平台能够访问的 HTTPS 后端地址：

```dotenv
DATA_AGENT_API_URL=https://your-api.example.com/api/query
```

Cloudflare/Vinext Worker 部署时，请将该变量配置为运行时变量或 secret，不要只配置在构建机环境中。还需要确认：

- FastAPI 地址可被 Worker 访问，并支持长连接 SSE。
- 后端基础设施已经 ready。
- 已经执行元知识构建脚本。
- 不要把真实 LLM API Key 写入前端代码或环境变量。

## 检查命令

```bash
npm run lint
npm run build
npm test
```

## 常用命令

- `npm run dev`: 启动开发服务器
- `npm run build`: 生成生产构建
- `npm test`: 构建并检查页面 HTML
- `npm run lint`: 运行 ESLint
