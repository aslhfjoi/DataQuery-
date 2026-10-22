from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.exceptions import OutputParserException
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.log import logger
from app.entities.value_info import ValueInfo
from app.prompt.prompt_loader import load_prompt

"""
用户问题
→ LLM 扩展字段值关键词
→ 合并 Jieba 关键词
→ 逐个查询 ES
→ 得到 ValueInfo
→ 按 ValueInfo.id 去重
→ 写入 retrieved_values
"""
async def recall_value(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "召回字段取值", "status": "running"})
    try:
        # 1.通过大模型扩充关键词
        query = state["query"]
        prompt = PromptTemplate(template=load_prompt("extend_keywords_for_value_recall"), input_variables=["query"])
        chain = prompt | llm | JsonOutputParser()
        try:
            result = await chain.ainvoke({"query": query})
        except OutputParserException as e:
            logger.warning(f"[recall_value] LLM未返回JSON数组，回退到原始关键词：{e.llm_output}")
            result = []
        if not isinstance(result, list) or not all(isinstance(keyword, str) for keyword in result):
            logger.warning(f"[recall_value] LLM返回结果不是字符串数组，回退到原始关键词：{result}")
            result = []
        logger.info(f"[recall_value] 对原查询llm扩展后指标列表：{result}")
        writer({"type": "log", "step": "召回字段取值", "message": "已扩展字段取值关键词", "data": result})
        # 2.关键词列表 已抽取关键词+扩充后的
        keywords = state["keywords"]
        keywords = list(set(keywords + result))

        # 3.遍历关键词列表 采用全文查询ES获取值信息ValueInfo
        retrieved_value_map: dict[str, ValueInfo] = {}
        value_es_repository = runtime.context["value_es_repository"]
        for keyword in keywords:
            value_infos: list[ValueInfo] = await value_es_repository.search(keyword)
            for value_info in value_infos:
                value_info_id = value_info.id
                if value_info_id not in retrieved_value_map:
                    retrieved_value_map[value_info_id] = value_info
        writer({"type": "progress", "step": "召回字段取值", "status": "success", "data": list(retrieved_value_map.keys())})
        logger.info(f"[recall_value] 召回字段取值成功：{list(retrieved_value_map.keys())}")
        # 4.更新state中召回字段信息列表
        return {"retrieved_values": list(retrieved_value_map.values())}
    except Exception as e:
        writer({"type": "progress", "step": "召回字段取值", "status": "error"})
        logger.error(f"[recall_value] 召回字段取值失败, 错误信息: {str(e)}")
        raise
