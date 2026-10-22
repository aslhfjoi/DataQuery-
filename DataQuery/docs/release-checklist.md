# GitHub 发布检查清单

## 凭据与数据

- [ ] 已撤销并轮换历史配置中出现过的 LLM API Key。
- [ ] 已修改所有历史数据库密码，并确认旧密码不可用。
- [ ] 全仓库和 Git 历史已完成 secret scan。
- [ ] 没有 `.env`、私钥、签名下载链接、连接串或个人路径。
- [ ] Demo SQL 中的姓名、订单和金额已确认是合成数据；否则已匿名化。
- [ ] 已移除课程原始资料、未授权图片、安装器、日志和部署缓存。

## 仓库边界

- [ ] 根目录是唯一 Git 仓库。
- [ ] `frontend/` 是普通目录，不含嵌套 `.git`。
- [ ] `.venv/`、`node_modules/`、`dist/`、`build/`、`.wrangler/`、`logs/`、`.accelerate/` 和模型权重未被跟踪。
- [ ] `prompts/` 只有一套确定的运行时模板。
- [ ] Demo SQL 来源唯一，文档中的路径与 Compose 一致。

## 配置与运行

- [ ] `.env.example` 不包含真实 secret。
- [ ] `docker compose ... config` 能正确展开变量。
- [ ] `uv sync --locked` 成功。
- [ ] Embedding 模型下载路径和上游许可已写入文档。
- [ ] 元知识构建命令成功执行。
- [ ] 后端 `/api/query` 能返回 SSE。
- [ ] 前端 `npm ci`、`npm run lint`、`npm run build`、`npm test` 成功。

## 安全与许可

- [ ] 生产部署使用 Secret 管理器和只读数据库账号。
- [ ] 生产环境未暴露无认证的 Elasticsearch、Qdrant 和 Kibana。
- [ ] 已确认代码、模型、IK 插件、课程资料、图片和字体的授权。
- [ ] 已补充适用的 `LICENSE`、`NOTICE` 和 `SECURITY.md`。
- [ ] 首次推送前由项目维护者检查 `git diff --cached` 和 `git ls-files`。
