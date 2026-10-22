from sqlalchemy import ScalarResult
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.sql.expression import text, select

from app.entities.column_info import ColumnInfo
from app.entities.column_metric import ColumnMetric
from app.entities.metric_info import MetricInfo
from app.entities.table_info import TableInfo
from app.mappers.column_info_mapper import ColumnInfoMapper
from app.mappers.column_metric_mapper import ColumnMetricMapper
from app.mappers.metric_info_mapper import MetricInfoMapper
from app.mappers.table_info_mapper import TableInfoMapper
from app.models.column_info_mysql import ColumnInfoMySQL
from app.models.table_info_mysql import TableInfoMySQL
"""
它操作的是 meta 数据库。
meta 里保存的不是订单，而是“数据库相关的知识”：
    表	保存内容
    table_info	有哪些表、表的含义、表的角色
    column_info	有哪些字段、字段类型、描述、别名、示例值
    metric_info	GMV、AOV 等业务指标
    column_metric	指标与字段之间的关系
"""

"""
Entity 业务对象
→ Mapper 转换
→ SQLAlchemy Model
→ session.add_all()
→ 保存到 Meta MySQL
"""
class MetaMySQLRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_table_infos(self, table_infos: list[TableInfo]):
        # 1. 将业务对象转为ORM模型对象
        models = [TableInfoMapper.to_model(table_info) for table_info in table_infos]
        # 2. 调用框架提供批量保存函数
        for model in models:
            await self.session.merge(model)

    async def save_column_infos(self, column_infos: list[ColumnInfo]):
        models = [ColumnInfoMapper.to_model(column_info) for column_info in column_infos]
        for model in models:
            await self.session.merge(model)

    async def save_metric_infos(self, metric_infos: list[MetricInfo]):
        models = [MetricInfoMapper.to_model(metric_info) for metric_info in metric_infos]
        for model in models:
            await self.session.merge(model)

    async def save_column_metric_infos(self, column_metric_infos: list[ColumnMetric]):
        models = [ColumnMetricMapper.to_model(column_metric_info) for column_metric_info in column_metric_infos]
        for model in models:
            await self.session.merge(model)

    async def get_column_info_by_id(self, column_id: str) -> ColumnInfo:
        """
        查询根据当前字段的id查询meta库中的column_info
        :param column_id: 字段ID
        :return:
        """
        column_info_mysql: ColumnInfoMySQL | None = await self.session.get(ColumnInfoMySQL, column_id)
        return ColumnInfoMapper.to_entity(column_info_mysql)

    async def get_key_column_by_table_id(self, table_id: str) -> list[ColumnInfo]:
        # sql = select * from column_info where table_id = ? and role in ("primary_key","foreign_key")
        stmt = select(ColumnInfoMySQL).where(ColumnInfoMySQL.table_id == table_id,
                                             ColumnInfoMySQL.role.in_(["primary_key", "foreign_key"]))
        # ORM方式执行查库操作，底层将多列结果封装到一个对象中，scalars处理是单个元素
        result: ScalarResult = await self.session.scalars(stmt)
        return [ColumnInfoMapper.to_entity(column_info_mysql) for column_info_mysql in result]

    async def get_table_info_by_id(self, table_id: str) -> TableInfo:
        table_info_mysql: TableInfoMySQL | None = await self.session.get(TableInfoMySQL, table_id)
        return TableInfoMapper.to_entity(table_info_mysql)
