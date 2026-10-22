# 架构说明

## 1. 分层结构

```text
main.py
  └─ app.api.routers.query_router
      └─ app.api.dependencies
          ├─ app.clients
          ├─ app.repositories
          └─ app.services.query_service
              └─ app.agent.graph
                  └─ app.agent.nodes
```

- `app/api`：HTTP 路由、请求 Schema 和依赖装配。
- `app/services`：在线查询和离线元知识构建。
- `app/agent`：LangGraph 状态、上下文、LLM 和工作流节点。
- `app/repositories`：MySQL、Qdrant 和 Elasticsearch 持久层。
- `app/entities` / `app/models` / `app/mappers`：业务实体、ORM 模型和转换器。
- `app/clients`：外部客户端生命周期管理。
- `conf`：OmegaConf YAML 配置和 Demo 元数据。
- `prompts`：运行时提示词模板。

## 2. 在线查询流程

1. 浏览器请求前端同源 `/api/query`。
2. `frontend/app/api/query/route.ts` 将请求转发到 FastAPI。
3. `query_router` 创建 `StreamingResponse`。
4. `QueryService` 将六类依赖装配到 `DataAgentContext`。
5. LangGraph 从 `DataAgentState(query=...)` 开始执行：
   - `extract_keywords` 抽取关键词。
   - `recall_column`、`recall_metric`、`recall_value` 并行召回。
   - `merge_retrieved_info` 合并字段、指标、值和主外键。
   - `filter_table`、`filter_metric` 使用 LLM 精选上下文。
   - `add_extra_context` 添加日期与数据库信息。
   - `generate_sql` 生成只读 SQL。
   - `validate_sql` 使用 `EXPLAIN` 校验。
   - 失败时 `correct_sql` 修正并重新校验，最多三次。
   - `execute_sql` 执行并推送结果和统计。
6. `QueryService` 将节点的自定义事件编码为 SSE。

## 3. 存储职责

| 存储 | 内容 | 代码入口 |
| --- | --- | --- |
| MySQL `meta` | 表、字段、指标及关联 | `MetaMySQLRepository` |
| MySQL `dw` | Demo 数仓和查询结果 | `DWMySQLRepository` |
| Qdrant | 字段、指标向量 | `ColumnQdrantRepository` / `MetricQdrantRepository` |
| Elasticsearch | 可检索字段值 | `ValueESRepository` |
| Embedding 服务 | BGE 文本向量 | `EmbeddedClientManager` |
| LLM | 关键词、筛选、SQL | `app/agent/llm.py` |

## 4. 离线知识构建

`uv run python -m app.scripts.build_meta_knowledge -c conf/meta_config.yaml` 会：

1. 从 Demo 数仓读取字段类型和少量样例值。
2. 将表、字段、指标写入 meta MySQL。
3. 将字段和指标文本向量写入 Qdrant。
4. 将 `sync: true` 字段的枚举值写入 Elasticsearch。

这是运行在线召回前的必要步骤。重复构建前应确认目标库和索引的数据清理/幂等策略。

## 5. 当前限制

- 认证辅助代码 `frontend/app/chatgpt-auth.ts` 当前没有接入页面或 API 路由，不代表应用已经启用认证。
- Compose 默认面向本地开发，ES/Qdrant 端口和安全设置不适合生产。
- SQL 安全校验是应用层基础防护，生产仍应增加数据库只读账号、AST 解析、超时和行数限制。
- 公开仓库不包含 Embedding 权重，需按上游许可证自行下载。
