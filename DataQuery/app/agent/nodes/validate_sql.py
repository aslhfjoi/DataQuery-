from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger
from app.core.stats import sql_stats

MAX_RETRY = 3  # SQL校正最大重试次数

async def validate_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "校验SQL", "status": "running"})
    # 获取重试次数
    retry_count = state.get("retry_count", 0)

    # 1.获取状态中SQL和重试次数
    try:
        sql = state["sql"]
        # 2.验证SQL
        dw_mysql_repository = runtime.context["dw_mysql_repository"]
        await dw_mysql_repository.validate_sql(sql)

        sql_stats.record_validation_pass()
        writer({"type": "progress", "step": "校验SQL", "status": "success"})
        return {"error": None}
    except Exception as e:
        if retry_count >= MAX_RETRY:
            # 超过最大重试次数，强制放行，在execute_sql中以最终异常兜底
            sql_stats.record_retry_exhausted()
            logger.warning(f"SQL校验已重试{retry_count}次，达到上限{MAX_RETRY}，强制放行执行。最后错误: {str(e)}")
            writer({"type": "progress", "step": "校验SQL", "status": "success"})
            return {"error": None}
        sql_stats.record_validation_fail()
        writer({"type": "progress", "step": "校验SQL", "status": "error"})
        logger.error(f"校验SQL失败(第{retry_count + 1}次), 错误信息: {str(e)}")
        return {"error": str(e)}


"""
# 执行计划，SQL性能分析关键词
EXPLAIN SELECT SUM(fo.order_amount) AS GMV
FROM fact_order fo
JOIN dim_region dr ON fo.region_id = dr.region_id
WHERE dr.region_name = '华北';

#SQL好坏指标 type 取值性能从低到高：all(全表扫描)<index(全索引扫描)<range(范围查询)<ref(普通索引等值)<const(主键等值)<system

EXPLAIN SELECT * from fact_order WHERE order_id = 'ORD20250103001';

EXPLAIN SELECT * from fact_order WHERE region_id = 'ORD20250103001'

EXPLAIN SELECT * from fact_order WHERE order_amount BETWEEN 10 and 1000

EXPLAIN SELECT order_id from fact_order;
EXPLAIN SELECT * from fact_order;
"""