from dataclasses import asdict

from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState, MetricInfoState, TableInfoState, ColumnInfoState
from app.core.log import logger
from app.entities.column_info import ColumnInfo
from app.entities.table_info import TableInfo


async def merge_retrieved_info(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "合并信息", "status": "running"})
    try:
        # 1. 合并所有字段 将已召回指标、字段取值 列表中包含字段信息 合并到 已召回字段 tips:记得去重、字段取值加入到字段examples中
        # 1.1 从state中获取已召回数据
        retrieved_columns = state["retrieved_columns"]
        retrieved_metrics = state["retrieved_metrics"]
        retrieved_values = state["retrieved_values"]

        # 1.2 将已召回**字段**列表转为字典 {"column_id":"ColumnInfo"}
        retrieved_columns_map: dict[str, ColumnInfo] = {retrieved_column.id: retrieved_column for retrieved_column in
                                                        retrieved_columns}

        # 1.3 处理已召回**指标**信息，将包含相关字段保存到字段字典中
        # 1.3.1 从上下文中获取meta库持久层对象
        meta_mysql_repository = runtime.context["meta_mysql_repository"]
        for retrieved_metric in retrieved_metrics:
            for metric_column_id in retrieved_metric.relevant_columns:
                if metric_column_id not in retrieved_columns_map:
                    # 1.3.2 说明字典中没有指标中字段信息 需要查询字段信息
                    column_info: ColumnInfo = await meta_mysql_repository.get_column_info_by_id(metric_column_id)
                    retrieved_columns_map[metric_column_id] = column_info

        # 1.4 处理已召回字段取值信息，将对应字段保存到字段字典中
        # 1.4.1 遍历字段取值列表，判断字段取值对象中的字段id是否在字典中
        for value_info in retrieved_values:
            column_id = value_info.column_id

            # 1.4.2 如果不在字典中，则从meta库持久层中查询字段信息，加入到字段字典中
            if column_id not in retrieved_columns_map:
                # 根据字段ID查询字段信息
                column_info: ColumnInfo = await meta_mysql_repository.get_column_info_by_id(column_id)
                retrieved_columns_map[column_id] = column_info

            # 1.4.3 如果“取值”不存在字段信息中examples中，将字段取值对象加入到字段事例说明examples中 解决最终生成SQL中where 字段=?的问题
            # 即使一个值不在example中 也不能说明它不在数据库中 可能是新值 也可能是旧值 但不在example中
            value = value_info.value
            if value not in retrieved_columns_map[column_id].examples:
                retrieved_columns_map[column_id].examples.append(value)

        # 2.按table_id分组 得到表跟字段列表映射字典 {"table_id1":[{ColumnInfo1},{ColumnInfo1}],"table_id2":[]}
        # 2.1 创建存放表ID以及包含字段列表的字典
        table_id_to_columns_map: dict[str, list[ColumnInfo]] = {}

        # 2.2 遍历**字段字典**的值列表
        for column_info in retrieved_columns_map.values():
            # 2.2.1 如果字段的table_id 不在字典中，则创建一个字段列表
            table_id = column_info.table_id
            if table_id not in table_id_to_columns_map:
                table_id_to_columns_map[table_id] = []
            # 2.2.2 将字段加入字段列表
            table_id_to_columns_map[table_id].append(column_info)

        # 3.对相关表显式增加主外键字段信息 为上面字典中字段列表中补充主外键字段信息
        for table_id in table_id_to_columns_map.keys():

            # 3.1 获取现有字典 包含字段ID 列表
            columns: list[str] = [column_info.id for column_info in table_id_to_columns_map[table_id]]

            # 3.2 根据表ID查询该表中所有主键或者外键字段信息 TODO
            key_columns: list[ColumnInfo] = await meta_mysql_repository.get_key_column_by_table_id(table_id)

            # 3.3 遍历主键或者外键字段列表 如果主外键字段不在字典值中，将字段加入字段列表
            for key_column in key_columns:
                key_column_id = key_column.id
                if key_column_id not in columns:
                    table_id_to_columns_map[table_id].append(key_column)

        # 4.将table_id ---->list[ColumnInfo]   封装state中表信息列表：list[TableInfoState]
        table_infos: list[TableInfoState] = []

        # 4.1 遍历table_id_to_columns_map 封装TableInfoState对象
        # 前面步骤负责找到和补全字段；这一步负责将这些字段包装成“完整的候选表结构”，写入 LangGraph 状态并提供给下游大模型。
        for table_id, column_infos in table_id_to_columns_map.items():
            # 4.2 处理表：根据table_id查询meta数据库中表信息
            table_info: TableInfo = await meta_mysql_repository.get_table_info_by_id(table_id)
            table_info_state = TableInfoState(
                name=table_info.name,
                role=table_info.role,
                description=table_info.description,
                # 4.2 处理表中字段：将列表list[ColumnInfo]转为list[ColumnInfoState] 它把每个 ColumnInfo 实体转换成普通字典，并去掉内部字段：id和table_id
                columns=[ColumnInfoState(
                    name=column_info.name,
                    type=column_info.type,
                    role=column_info.role,
                    examples=column_info.examples,
                    description=column_info.description,
                    alias=column_info.alias
                ) for column_info in column_infos]
            )
            """
            {
                "name": "fact_order",
                "role": "fact",
                "description": "订单事实表，记录订单数量和金额等核心指标。",
                "columns": [
                    {
                        "name": "order_amount",
                        "type": "decimal",
                        "role": "measure",
                        "examples": [100, 200],
                        "description": "订单金额",
                        "alias": ["销售额", "订单金额", "收入"]
                    },
                    {
                        "name": "region_id",
                        "type": "varchar",
                        "role": "foreign_key",
                        "examples": [],
                        "description": "关联地区维度的外键",
                        "alias": ["地区ID", "区域ID"]
                    }
                ]
            }
            """
            table_infos.append(table_info_state)
        logger.info(f"[merge_retrieved_info] 合并信息，表列表：{[table['name'] for table in table_infos]}")
        logger.info(f"[merge_retrieved_info] 合并信息，字段列表：{[column['name'] for table in table_infos for column in table['columns']]}")

        # 5.封装state中指标信息列表：list[MetricInfoState]
        metric_infos: list[MetricInfoState] = [MetricInfoState(
            name=retrieved_metric.name,
            description=retrieved_metric.description,
            relevant_columns=retrieved_metric.relevant_columns,
            alias=retrieved_metric.alias
        ) for retrieved_metric in retrieved_metrics]

        writer({"type": "progress", "step": "合并信息", "status": "success", "data": {table['name']: [column['name'] for column in table['columns']] for table in table_infos}})
        logger.info(f"[merge_retrieved_info] 合并信息，指标列表：{[metric_info['name'] for metric_info in metric_infos]}")

        # 6.更新state中表信息列表、指标信息列表
        return {"metric_infos": metric_infos, "table_infos": table_infos}
    except Exception as e:
        writer({"type": "progress", "step": "合并信息", "status": "error"})
        logger.error(f"[merge_retrieved_info] 合并信息失败, 错误信息: {str(e)}")
        raise
