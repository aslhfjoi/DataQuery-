# DataQuery数据仓库

基于 **FastAPI、LangGraph、LangChain 和 React** 的中文自然语言问数项目。输入业务问题后，系统检索字段、指标和字段取值，生成并校验 SQL，在 MySQL 数仓执行查询，再通过 SSE 实时返回执行进展和结果。

```text
统计华北地区销售总额
统计各商品分类的销售数量
不同会员等级的订单金额分别是多少
```

本项目提供本地演示数仓与问数界面，适合学习和本地验证。当前版本不包含完整的用户认证、数据权限和生产运维能力。

## 目录

- [功能与技术栈](#功能与技术栈)
- [系统架构](#系统架构)
- [项目结构](#项目结构)
- [环境要求](#环境要求)
- [首次安装与启动](#首次安装与启动)
- [日常启动与关闭](#日常启动与关闭)
- [环境配置](#环境配置)
- [修改数据库密码](#修改数据库密码)
- [接入自己的业务数据](#接入自己的业务数据)
- [API 与事件协议](#api-与事件协议)
- [开发与检查](#开发与检查)
- [常见问题](#常见问题)
- [部署说明](#部署说明)

## 功能与技术栈

### 主要功能

- 中文自然语言查询：将问题转换成数据库查询。
- 元知识检索：结合向量检索与全文检索定位字段、指标和字段取值。
- SQL 生成与纠错：通过模型生成 SQL，执行只读规则检查和 `EXPLAIN` 校验，必要时尝试纠错。
- 实时分析过程：在同一个回答窗口逐步展示关键词、召回信息、筛选结果和 SQL，随后呈现查询结果。
- 历史结果恢复：最近问题与结果保存在当前浏览器本地，点击历史记录恢复已有结果，不自动重新查询。
- CSV 导出：导出非空查询结果。
- 自适应界面：按窗口宽度和高度调整标题、间距及分析窗口。
- 查询停止：前端可中断请求；这不等于保证所有已经发出的远端模型或数据库操作立即终止。
- 耗时分析：后端日志记录收到的阶段开始、结束事件及对应耗时。

过程展示来自真实执行事件，不额外调用模型编写“思考过程”，也不展示模型内部推理。

### 技术栈

| 层次 | 技术 |
| --- | --- |
| 前端 | React 19、TypeScript、Vinext、Vite、Next.js 兼容 API |
| 前端运行适配 | Cloudflare Vite 插件、Worker |
| 后端接口 | FastAPI、Uvicorn、SSE |
| Agent 编排 | LangGraph、LangChain |
| 大模型 | 当前代码通过 `init_chat_model` 配置，主要使用 DeepSeek 集成 |
| 关系数据库 | MySQL 8.0、SQLAlchemy Async、asyncmy |
| 向量数据库 | Qdrant |
| 全文检索 | Elasticsearch 8.19.10、IK 分词插件 |
| 向量服务 | Text Embeddings Inference、BAAI/bge-large-zh-v1.5 |
| 配置与日志 | python-dotenv、OmegaConf、Loguru |
| 依赖与基础设施 | uv、npm、Docker Compose |

## 系统架构

```text
浏览器 http://127.0.0.1:3000
    │ POST /api/query
    ▼
前端服务端代理
    │ SSE 转发
    ▼
FastAPI http://127.0.0.1:8000
    ▼
LangGraph 查询流程
    ├── LLM：语义扩展、筛选、SQL 生成与纠错
    ├── Embedding：文本转向量
    ├── Qdrant：字段、指标向量检索
    ├── Elasticsearch：字段值全文检索
    ├── MySQL meta：表、字段、指标定义
    └── MySQL dw：业务数据与查询执行
```

查询流程：

```text
抽取关键词
    ├── 召回字段 ──────┐
    ├── 召回指标 ──────┼── 合并信息
    └── 召回字段取值 ──┘       │
                    ┌────────┴────────┐
                  过滤表            过滤指标
                    └────────┬────────┘
                         添加上下文
                             │
                          生成 SQL
                             │
                          校验 SQL
                         /         \
                       通过        校正后重试
                         │
                       执行 SQL
                         │
                    返回结果与统计
```

字段和指标分支使用批量向量化减少逐词请求，但查询仍包含多次模型调用，不能保证固定秒数返回。当前校验节点在最多三次校正后会进入执行分支，执行层仍进行只读规则检查；应结合错误事件判断最终是否成功，不能只依赖进度中的“校验完成”。

## 项目结构

```text
DataQuery/
├── .env.example                 # 后端配置模板
├── .gitignore
├── README.md
├── SECURITY.md
├── main.py                      # FastAPI 入口
├── pyproject.toml
├── uv.lock
├── app/
│   ├── agent/                   # 图、状态、上下文、大模型及流程节点
│   ├── api/                     # 路由、请求 Schema、依赖注入
│   ├── clients/                 # 数据库、检索和 Embedding 客户端
│   ├── conf/                    # 配置加载与数据结构
│   ├── core/                    # 生命周期、日志、请求上下文和统计
│   ├── entities/                # 业务实体
│   ├── mappers/                 # 实体与 ORM 模型转换
│   ├── models/                  # 元数据库 ORM 模型
│   ├── prompt/                  # 提示词加载
│   ├── repositories/            # MySQL、Qdrant、ES 数据访问
│   ├── scripts/build_meta_knowledge.py
│   └── services/                # 查询服务与元知识构建
├── conf/
│   ├── app_config.yaml          # 环境变量映射
│   ├── meta_config.yaml         # 业务表、字段、指标定义
│   └── text_config.yaml
├── prompts/                     # 运行时提示词模板
├── docker/
│   ├── docker-compose.yaml
│   ├── mysql/                   # meta、dw 初始化 SQL
│   ├── elasticsearch/           # Elasticsearch 镜像和 IK 插件
│   └── embedding/               # 模型准备说明，本地模型不提交
├── frontend/
│   ├── .env.example
│   ├── .openai/hosting.example.json
│   ├── app/components/DataAssistant.tsx
│   ├── app/api/query/route.ts    # 后端代理
│   ├── app/page.tsx
│   ├── app/layout.tsx
│   ├── app/globals.css
│   ├── public/
│   ├── worker/
│   ├── package.json
│   ├── package-lock.json
│   └── vite.config.ts
├── test/                        # 后端基础测试和流程图
└── docs/                        # 架构与发布检查说明
```

## 环境要求

| 工具 | 要求 |
| --- | --- |
| Python | 3.12 或以上 |
| uv | 用于安装 Python 依赖和创建虚拟环境 |
| Node.js | 22.13.0 或以上，包含 npm |
| Docker | Docker Desktop 或 Docker Engine，支持 `docker compose` |
| LLM 账号 | 可访问的模型服务及有效 API Key |

建议为基础服务准备至少约 8 GB 可用内存，并预留数 GB 磁盘用于镜像、依赖和模型。模型权重约需 1.2 GB，具体以下载内容为准。

Compose 中 Embedding 固定为 `linux/amd64`。Apple Silicon 运行时依赖 Docker 的跨架构支持，性能可能低于原生运行；遇到异常应先检查 Embedding 容器日志。

检查工具：

```bash
python3 --version
uv --version
node --version
npm --version
docker --version
docker compose version
```

## 首次安装与启动

以下步骤除特别说明外，均在项目根目录执行。根目录应包含 `main.py`、`pyproject.toml` 和 `docker/`。

### 1. 获取代码并进入目录

```bash
git clone <你的仓库地址> DataQuery
cd DataQuery
```

如果已下载项目，直接进入本机对应目录，不必重新克隆。不要复制别人的 `.venv` 或 `node_modules`，应在本机重新安装。

### 2. 配置后端环境变量

仅在尚无 `.env` 时执行，避免覆盖已有配置：

```bash
cp .env.example .env
```

编辑 `.env`，至少填写：

```dotenv
LLM_MODEL_NAME=你的服务支持的模型名
LLM_API_KEY=你的真实APIKey

MYSQL_ROOT_PASSWORD=你的root密码
MYSQL_PASSWORD=你的业务账号密码
META_DB_PASSWORD=你的业务账号密码
DW_DB_PASSWORD=你的业务账号密码
```

`MYSQL_PASSWORD`、`META_DB_PASSWORD`、`DW_DB_PASSWORD` 必须一致，因为默认都对应 `data_agent` 账号。`root` 密码可以单独设置。模板里的模型名仅是默认配置，不代表账号一定可用；请按模型服务实际权限填写。当前代码使用 DeepSeek 集成，更换其他供应商可能需要安装对应 LangChain 集成并调整模型初始化。

当前 MySQL 连接串直接插入密码，尚未进行 URL 编码。密码若含 `@`、`/`、`:` 等 URL 保留字符可能解析失败；可先选用足够长的随机字母数字密码，或在代码中改用 SQLAlchemy `URL.create`。

### 3. 安装后端依赖

```bash
uv sync --locked
```

uv 会创建项目专属 `.venv`。系统默认 Python 版本不足时，可先用 `uv python install 3.12` 准备 Python，再运行依赖安装。

### 4. 下载 Embedding 模型

项目默认使用 `BAAI/bge-large-zh-v1.5`，向量维度为 **1024**。

```bash
uv run hf download BAAI/bge-large-zh-v1.5 \
  --local-dir docker/embedding/bge-large-zh-v1.5
```

如果当前环境没有 `hf` 命令，可以从模型仓库下载完整文件：

[BAAI/bge-large-zh-v1.5 模型仓库](https://huggingface.co/BAAI/bge-large-zh-v1.5)

默认目录至少应包含配置、Tokenizer 和权重文件，例如：

```text
docker/embedding/bge-large-zh-v1.5/
├── config.json
├── tokenizer.json
├── tokenizer_config.json
├── vocab.txt
└── model.safetensors 或 pytorch_model.bin
```

仅有配置文件不等于模型已下载完整。也可以在 `.env` 的 `EMBEDDING_MODEL_PATH` 中填写已有模型目录的绝对路径。默认相对路径 `./embedding/bge-large-zh-v1.5` 是相对于 `docker/docker-compose.yaml` 所在目录解析的。

### 5. 启动基础服务

先启动 Docker Desktop 或 Docker Engine，再执行：

```bash
docker compose --env-file .env -f docker/docker-compose.yaml config --quiet
docker compose --env-file .env -f docker/docker-compose.yaml up -d --build
docker compose --env-file .env -f docker/docker-compose.yaml ps
```

| 服务 | 默认本机端口 | 用途 |
| --- | --- | --- |
| MySQL | 3306 | `meta` 元数据库、`dw` 业务数仓 |
| Elasticsearch | 9200 | 字段值检索 |
| Kibana | 5601 | Elasticsearch 管理界面，查询主流程不依赖它 |
| Qdrant | 6333 / 6334 | HTTP / gRPC 向量服务 |
| Embedding | 8081 | 文本向量化服务 |

首次运行会下载镜像、构建 IK 插件镜像并初始化数据库，耗时较长。容器显示 `Up` 不代表内部服务已就绪。检查：

```bash
docker compose --env-file .env -f docker/docker-compose.yaml logs --tail=100 mysql elasticsearch qdrant embedding
curl -f http://127.0.0.1:9200
curl -f http://127.0.0.1:6333
curl -f http://127.0.0.1:8081/health
```

MySQL 日志出现 `ready for connections` 后，再用配置的业务账号确认可以登录。初始化 SQL 只在空数据卷首次启动时执行。

### 6. 构建元知识库

基础服务就绪后执行：

```bash
uv run python -m app.scripts.build_meta_knowledge -c conf/meta_config.yaml
```

构建流程会读取 `dw` 的字段类型和示例值，将描述写入 `meta`，将字段与指标向量写入 Qdrant，并将配置为 `sync: true` 的字段取值写入 Elasticsearch。

这一步是首次完整问数前的必要步骤，当前不提供前端构建按钮。日常启动不需要重复执行。

MySQL 元数据已支持按主键合并，但当前 Qdrant 构建使用随机点 ID，反复执行会新增向量点；不能将整个构建过程视为完全幂等。修改元知识后重建前，应规划集合和索引的更新或清理策略，不要盲目反复运行。

### 7. 启动后端

```bash
uv run uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

保持终端运行。接口文档：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)。`--reload` 仅供开发使用。当前没有单独的 `/health` 路由，文档可访问也不代表依赖链路全部正常。

### 8. 启动前端

新开终端进入项目的 `frontend` 目录：

```bash
cd frontend
npm ci
```

创建 `frontend/.env.local`，写入以下配置。模板可能使用示例远端地址，本地运行应明确改为本机后端：

```dotenv
DATA_AGENT_API_URL=http://127.0.0.1:8000/api/query
```

启动：

```bash
npm run dev -- --host 127.0.0.1 --port 3000
```

打开 [http://127.0.0.1:3000](http://127.0.0.1:3000)。根目录 `.env` 与前端 `.env.local` 是两份配置，前端不会因为根目录写了代理地址就自动读取它。

### 9. 验证完整查询

在页面输入示例问题，或新开终端直接测试后端：

```bash
curl -N \
  -H 'Accept: text/event-stream' \
  -H 'Content-Type: application/json' \
  -X POST http://127.0.0.1:8000/api/query \
  -d '{"query":"统计华北地区销售总额"}'
```

看到进度事件后，继续确认收到结果且没有失败统计。直接在浏览器地址栏访问 `/api/query` 是 GET 请求，不能用于调用该 POST 接口。

## 日常启动与关闭

完成首次安装后，只需按顺序启动以下三部分。

**终端一：基础服务和后端，项目根目录执行。**

```bash
docker compose --env-file .env -f docker/docker-compose.yaml up -d
# 等待基础服务就绪后执行
uv run uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

**终端二：前端，项目根目录执行。**

```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 3000
```

不需要每天重复安装依赖、下载模型或构建元知识。依赖清单更新后重新安装，业务表或元知识定义变化后评估重建。

关闭时，在前后端终端分别按 `Ctrl+C`，再回到项目根目录执行：

```bash
docker compose --env-file .env -f docker/docker-compose.yaml stop
```

`stop` 保留容器和数据。`down` 会移除容器和网络但默认保留命名数据卷。**`down -v` 会删除本项目的数据卷，导致 MySQL、ES、Qdrant 数据丢失，不应作为常规停止命令。**

## 环境配置

| 配置 | 作用 |
| --- | --- |
| `LLM_MODEL_NAME` / `LLM_API_KEY` | 模型名与服务凭据 |
| `MYSQL_ROOT_PASSWORD` | Docker 首次初始化 root 账号的密码 |
| `MYSQL_PASSWORD` | Docker 首次初始化 `data_agent` 的密码 |
| `META_DB_HOST` / `META_DB_USER` / `META_DB_PASSWORD` / `META_DB_NAME` | 元数据库连接 |
| `DW_DB_HOST` / `DW_DB_USER` / `DW_DB_PASSWORD` / `DW_DB_NAME` | 数仓连接 |
| `QDRANT_HOST` / `QDRANT_PORT` | 向量服务地址 |
| `ELASTICSEARCH_HOST` / `ELASTICSEARCH_PORT` / `ES_VALUE_INDEX` | 字段值检索服务与索引 |
| `EMBEDDING_HOST` / `EMBEDDING_PORT` | 向量化服务地址 |
| `EMBEDDING_MODEL_PATH` | Compose 挂载的模型路径 |
| `EMBEDDING_MODEL` / `EMBEDDING_SIZE` | 模型配置与向量维度 |
| `APP_CONFIG_PATH` | 可选，覆盖默认 `conf/app_config.yaml` |
| `DATA_AGENT_API_URL` | 前端服务端代理地址，配置在前端环境中 |

注意：虽然模板定义了 `META_DB_PORT` 和 `DW_DB_PORT`，**当前 `MySQLClientManager._get_url()` 没有将端口加入连接串**。修改端口配置本身不会生效。要换用 3307 等端口，必须同时修改连接串构建逻辑，推荐使用 `URL.create` 并传入 `port`。默认 3306 不受影响。

修改后端密码、Key 或模型配置后重启后端；修改前端代理地址后重启前端。`load_dotenv` 默认不覆盖进程中已经存在的同名环境变量，排查时也要检查启动终端是否设置过旧配置。

## 修改数据库密码

密码属于数据库账号，`meta` 和 `dw` 不各自拥有独立密码。**已有数据卷时，仅修改 `.env` 不会更改 MySQL 内部账号。**

1. 暂停后端查询并备份需要保留的数据。
2. 用当前有效的旧 root 密码登录：

   ```bash
   docker compose --env-file .env -f docker/docker-compose.yaml exec mysql mysql -uroot -p
   ```

3. 查看账号，按实际存在的 `Host` 修改，不要假定所有账号都存在：

   ```sql
   SELECT User, Host FROM mysql.user;
   ALTER USER 'root'@'localhost' IDENTIFIED BY '新的root密码';
   ALTER USER 'data_agent'@'%' IDENTIFIED BY '新的业务密码';
   ```

   若存在 `root@'%'` 且需要保留，也应同步修改它。确认旧账号不再使用后，才执行 `DROP USER '旧账号'@'实际Host';`。

4. 同步根目录 `.env`：更新 `MYSQL_ROOT_PASSWORD`；将业务密码同步到 `MYSQL_PASSWORD`、`META_DB_PASSWORD`、`DW_DB_PASSWORD`。
5. 更新容器环境并重启后端：

   ```bash
   docker compose --env-file .env -f docker/docker-compose.yaml up -d --force-recreate mysql
   ```

重建容器默认保留数据卷，不要添加 `-v`。登录凭据不要写进公开说明、截图或提交历史。

## 接入自己的业务数据

1. 准备 MySQL 业务库和可查询账号，配置 `DW_DB_*`。
2. 保留独立的 `meta` 数据库及其四张元数据表。
3. 编辑 `conf/meta_config.yaml`，定义实际存在的表和字段。
4. 给字段补充业务描述、别名与角色；仅将适合枚举检索的字段设为 `sync: true`。
5. 定义指标时核对 `relevant_columns` 和统计口径。
6. 运行元知识构建，再用已知正确答案的业务问题验证 SQL 和结果。

示例：

```yaml
tables:
  - name: fact_order
    role: fact
    description: 订单事实表
    columns:
      - name: order_amount
        role: measure
        description: 订单金额
        alias: [销售额, 收入]
        sync: false

metrics:
  - name: GMV
    description: 订单成交金额总和
    relevant_columns: [fact_order.order_amount]
    alias: [成交总额]
```

这是配置格式示意，不是对任意业务库都完整可用的配置。实际查询还应提供关联键及必要维度。

Demo 包含 `dim_region`、`dim_customer`、`dim_product`、`dim_date`、`fact_order`。指标定义只是语义辅助，不是经过审计的指标引擎；例如当前 AOV 的描述与关联列需要按业务口径核对后再使用。

## API 与事件协议

### 请求

```http
POST /api/query
Content-Type: application/json
Accept: text/event-stream
```

```json
{"query": "统计华北地区销售总额"}
```

`query` 长度限制为 1～500 个字符。

### SSE 响应

每条事件为 `data: JSON`，以空行结束：

```text
data: {"type":"progress","step":"召回指标","status":"running"}

data: {"type":"log","step":"召回指标","message":"已扩展指标关键词","data":["销售总额"]}

data: {"type":"progress","step":"召回指标","status":"success","data":["GMV"],"duration_ms":1200}

data: {"type":"result","data":[{"销售总额":12345.67}]}

```

以上数值仅为协议示例。

| 类型 | 含义 |
| --- | --- |
| `progress` | 阶段的 `running`、`success`、`error` 状态，可带步骤数据和耗时 |
| `log` | 前端可展示的结构化中间信息 |
| `result` | 数据结果，通常为对象数组 |
| `stats` | SQL 校验、纠错和执行统计 |
| `error` | 查询失败信息 |

流开始后发生异常，HTTP 状态仍可能是 200；客户端必须继续检查 SSE 中的 `error` 和 `stats.execution_success`。

最近六条问题和结果保存在浏览器 `localStorage`，不是服务器会话存储。旧版仅保存问题的历史无法恢复未缓存的结果；存储额度不足或浏览器清理数据后，也可能无法持久保存。不要在共享电脑中保留敏感查询结果。

## 开发与检查

后端语法与基础测试：

```bash
uv run python -m compileall -q app main.py
uv run python -m unittest discover -s test -p 'test_*.py' -v
```

前端依赖与构建，根目录执行：

```bash
npm --prefix frontend ci
npm --prefix frontend run build
```

前端提供 `dev`、`build`、`start` 脚本。`npm run start` 用于运行已构建产物，需先完成构建并配置可访问的后端地址。

测试通过不代表外部模型、数据库、检索服务均可用，完整验证仍需启动服务并实际查询。

## 常见问题

### Docker 无法连接

出现 `Cannot connect to the Docker daemon` 时，先启动 Docker Desktop 或系统 Docker 服务。命令存在不代表引擎已运行。

### 3306 端口被占用

```bash
docker ps --format 'table {{.Names}}\t{{.Ports}}'
lsof -nP -iTCP:3306 -sTCP:LISTEN
```

识别占用来源后再停止明确不需要的服务，不要直接删除未知数据库。若选择更换端口，参见前面的 MySQL 端口实现限制。

### MySQL 连接被拒绝

检查容器、端口映射和日志：

```bash
docker compose --env-file .env -f docker/docker-compose.yaml ps -a
docker port mysql
docker compose --env-file .env -f docker/docker-compose.yaml logs --tail=100 mysql
```

本机访问需要看到类似 `0.0.0.0:3306->3306/tcp` 的映射，仅有 `3306/tcp` 不表示已经发布端口。

### MySQL 提示 Access denied

检查用户名、密码和账号 Host。旧数据卷不会因为 `.env` 改变而重新初始化。可以用有效的 root 账号查看用户；若缺少 `data_agent`，需按项目 SQL 的授权需求创建账号。优先修复账号，避免用删除数据卷解决登录问题。

### npm 提示 EACCES 或 vinext: command not found

依赖安装失败时，后续启动可能找不到 `vinext`。可使用独立缓存重新安装：

```bash
cd frontend
npm ci --cache /tmp/dataquery-npm-cache
npm run dev -- --host 127.0.0.1 --port 3000
```

不要通过 `sudo npm ci` 安装项目依赖。弃用警告不一定导致安装失败，应检查最终退出状态。

### LLM 请求超时

查看后端日志中的模型服务地址及代理。若本地代理不稳定且直连模型服务可用，可以让相关地址绕过代理：

```bash
NO_PROXY=127.0.0.1,localhost,api.deepseek.com \
no_proxy=127.0.0.1,localhost,api.deepseek.com \
uv run uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

该命令仅适合直连可用的环境，不保证解决 Key、额度或模型权限问题。换用其他模型服务时应同步调整域名。

### 前端打开了但查询失败

先用 curl 直接请求后端。如果后端成功，检查 `frontend/.env.local` 里的代理地址并重启前端。如果 curl 也失败，检查后端日志和基础服务，不要重复安装前端依赖。

### Embedding 启动失败

检查完整模型权重、挂载路径、Docker 资源及架构支持：

```bash
docker compose --env-file .env -f docker/docker-compose.yaml logs --tail=100 embedding
```

### 修改初始化 SQL 后没有变化

MySQL 的 `/docker-entrypoint-initdb.d` 只在空数据目录初始化时执行。已有数据应通过迁移或手动审核的 SQL 更新，不能期待重启自动重新导入。

### 流式结果迟迟不出现

检查模型调用、阶段耗时、向量服务和 ES 状态；若经过反向代理，确认关闭响应缓冲并为 SSE 配置合理超时。当前 UI 展示的是执行事件流，不是模型回答逐字流，模型调用期间可能暂时没有新事件。

## 部署说明

当前 Compose 的固定容器名及默认数据卷命名也需要注意：如果从同名 `docker/` 目录启动多份项目，它们可能关联到同一 Compose 项目或发生容器名冲突。需要并行环境时，应设计独立项目名、容器名、端口和数据卷；不要对来源不明的数据卷执行清理。

生产部署前至少需要补充：

- 用户认证、表与字段权限控制、审计与限流。
- 独立只读数仓账号、SQL AST 检查、查询超时和结果行数限制。
- Elasticsearch、Qdrant 等基础服务的认证、网络隔离与备份。
- HTTPS、SSE 代理配置、密钥管理和独立环境配置。
- 对模型接收的表结构、示例值、业务信息进行隐私评估。

当前 SQL 检查基于规则匹配，不等同于完整安全边界；Compose 中 ES 默认关闭认证，服务端口默认发布到所有网卡。不要直接将演示配置暴露公网。远端前端也不能通过 `127.0.0.1` 访问你电脑上的后端，应配置其实际可达的 HTTPS 地址。

模型、IK 插件及其他依赖遵循各自许可证。公开 Demo 数据前确认其来源和可公开性；如需为本项目授权，应由仓库维护者选择并添加合适的 `LICENSE`。

更多说明：[架构文档](docs/architecture.md)、[安全说明](SECURITY.md)、[发布检查清单](docs/release-checklist.md)。
