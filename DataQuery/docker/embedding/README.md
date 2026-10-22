# Embedding 模型

项目使用 `BAAI/bge-large-zh-v1.5`，向量维度为 1024。

## 准备方式

仓库不提交模型权重（约 1.2 GB）。请从上游模型仓库下载完整目录：

<https://huggingface.co/BAAI/bge-large-zh-v1.5>

默认放置位置：

```text
docker/embedding/bge-large-zh-v1.5/
```

也可以在根 `.env` 中设置：

```dotenv
EMBEDDING_MODEL_PATH=/absolute/path/to/bge-large-zh-v1.5
```

然后从仓库根目录启动 Compose：

```bash
docker compose -f docker/docker-compose.yaml up -d --build embedding
```

请遵守模型上游许可证和使用条款，并在生产环境为下载文件做来源、版本和校验和记录。不要把模型缓存、权重或访问凭据提交到 Git。
