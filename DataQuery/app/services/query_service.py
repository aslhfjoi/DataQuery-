import json
from time import perf_counter

from langchain_huggingface import HuggingFaceEndpointEmbeddings

from app.agent.context import DataAgentContext
from app.agent.graph import graph
from app.agent.state import DataAgentState
from app.core.log import logger
from app.repositories.es.value_es_repository import ValueESRepository
from app.repositories.mysql.dw.dw_mysql_repository import DWMySQLRepository
from app.repositories.mysql.meta.meta_mysql_repository import MetaMySQLRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository


class QueryService:

    def __init__(
            self,
            embedding_client: HuggingFaceEndpointEmbeddings,
            column_qdrant_repository:ColumnQdrantRepository,
            metric_qdrant_repository:MetricQdrantRepository,
            value_es_repository:ValueESRepository,
            meta_mysql_repository:MetaMySQLRepository,
            dw_mysql_repository:DWMySQLRepository
    ):
        self.embedding_client = embedding_client
        self.column_qdrant_repository = column_qdrant_repository
        self.metric_qdrant_repository = metric_qdrant_repository
        self.value_es_repository = value_es_repository
        self.meta_mysql_repository = meta_mysql_repository
        self.dw_mysql_repository = dw_mysql_repository

    async def query_answer(self, question: str):
        context = DataAgentContext(
            embedding_client=self.embedding_client,
            column_qdrant_repository=self.column_qdrant_repository,
            metric_qdrant_repository=self.metric_qdrant_repository,
            value_es_repository=self.value_es_repository,
            meta_mysql_repository=self.meta_mysql_repository,
            dw_mysql_repository=self.dw_mysql_repository,
        )
        try:
            stage_starts = {}
            async for chunk in graph.astream(
                input=DataAgentState(query=question),
                context=context,
                stream_mode="custom",
            ):
                if chunk.get("type") == "progress":
                    step = chunk.get("step")
                    if chunk.get("status") == "running":
                        stage_starts[step] = perf_counter()
                    elif step in stage_starts:
                        chunk["duration_ms"] = round((perf_counter() - stage_starts.pop(step)) * 1000)
                        logger.info("查询阶段 {} 耗时 {} ms", step, chunk["duration_ms"])
                yield f"data: {json.dumps(chunk, ensure_ascii=False, default=str)}\n\n"
        except Exception as exc:
            # Headers are already sent when a streaming graph fails. Emit a final
            # structured event so the proxy and browser can show a stable error
            # event instead of reporting a generic connection reset.
            logger.exception("数据查询流执行失败")
            message = "数据查询执行失败，请检查服务日志和 request_id"
            yield (
                "data: "
                + json.dumps(
                    {
                        "type": "error",
                        "data": {"error": message},
                    },
                    ensure_ascii=False,
                )
                + "\n\n"
            )
            yield (
                "data: "
                + json.dumps(
                    {
                        "type": "stats",
                        "data": {
                            "sql_validated": False,
                            "execution_success": False,
                            "error": message,
                        },
                    },
                    ensure_ascii=False,
                )
                + "\n\n"
            )
