from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.exceptions import OutputParserException
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.log import logger
from app.entities.metric_info import MetricInfo
from app.prompt.prompt_loader import load_prompt


async def recall_metric(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "召回指标", "status": "running"})
    try:
        # 1.通过llm对指标名称扩充 目的：为了得到回答问题需要哪些指标
        prompt = PromptTemplate(template=load_prompt("extend_keywords_for_metric_recall"), input_variables=["query"])
        chain = prompt | llm | JsonOutputParser()
        try:
            result = await chain.ainvoke({"query": state["query"]})
        except OutputParserException as e:
            logger.warning(f"[recall_metric] LLM未返回JSON数组，回退到原始关键词：{e.llm_output}")
            result = []
        if not isinstance(result, list) or not all(isinstance(keyword, str) for keyword in result):
            logger.warning(f"[recall_metric] LLM返回结果不是字符串数组，回退到原始关键词：{result}")
            result = []
        logger.info(f"[recall_metric] 对原查询llm扩展后指标列表：{result}")
        writer({"type": "log", "step": "召回指标", "message": "已扩展指标关键词", "data": result})
        # 2.关键词列表 已抽取关键词+扩充后的
        keywords = state["keywords"]
        keywords = list(set(keywords + result))
        # 3.遍历关键词列表 查询qdrant指标向量集合
        retrieved_metric_map: dict[str, MetricInfo] = {}
        embedding_client = runtime.context["embedding_client"]
        metric_qdrant_repository = runtime.context["metric_qdrant_repository"]
        embeddings = await embedding_client.aembed_documents(keywords) if keywords else []
        for embedding in embeddings:
            metric_infos: list[MetricInfo] = await metric_qdrant_repository.search(embedding)
            for metric_info in metric_infos:
                metric_info_id = metric_info.id
                if metric_info_id not in retrieved_metric_map:
                    retrieved_metric_map[metric_info_id] = metric_info
        writer({"type": "progress", "step": "召回指标", "status": "success", "data": list(retrieved_metric_map.keys())})
        logger.info(f"[recall_metric] 召回指标成功：{list(retrieved_metric_map.keys())}")
        # 4.更新state中召回指标信息列表
        return {"retrieved_metrics": list(retrieved_metric_map.values())}
    except Exception as e:
        logger.error(f"[recall_metric] 召回指标失败, 错误信息: {str(e)}")
        writer({"type": "progress", "step": "召回指标", "status": "error"})
        raise
