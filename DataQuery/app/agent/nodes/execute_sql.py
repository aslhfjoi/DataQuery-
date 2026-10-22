from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger
from app.core.stats import sql_stats


async def execute_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "执行SQL", "status": "running"})
    retry_count = state.get("retry_count", 0)
    try:
        # 1.获取state中SQL语句
        sql = state["sql"]
        # 2.调用数仓持久层执行SQL查询
        dw_mysql_repository = runtime.context["dw_mysql_repository"]
        data = await dw_mysql_repository.execute_sql(sql)
        sql_stats.record_execution_success()
        writer({"type": "progress", "step": "执行SQL", "status": "success"})
        logger.info("SQL 查询执行成功，结果已通过 SSE 返回")
        # 3.将查询结果实时返回
        writer({"type": "result", "data": data})
        # 4.推送本次请求的统计摘要
        writer({"type": "stats", "data": {
            "sql_corrections": retry_count,
            "sql_validated": True,
            "execution_success": True,
        }})
        sql_stats.log_summary()
    except Exception as e:
        sql_stats.record_execution_failure()
        writer({"type": "progress", "step": "执行SQL", "status": "error"})
        logger.exception("SQL 执行失败")
        message = "数据查询执行失败，请检查服务日志和 request_id"
        writer({"type": "stats", "data": {
            "sql_corrections": retry_count,
            "sql_validated": False,
            "execution_success": False,
            "error": message,
        }})
        sql_stats.log_summary()
        # The failure has already been sent as an SSE stats event. Returning
        # keeps the stream well-formed so the frontend can display that error.
        return
