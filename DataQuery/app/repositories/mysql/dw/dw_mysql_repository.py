import re

from sqlalchemy import Result
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.sql.expression import text


_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_READ_ONLY_PATTERN = re.compile(r"^(?:SELECT|WITH)\b", re.IGNORECASE)
_FORBIDDEN_PATTERN = re.compile(
    r"\b(?:INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|REPLACE|GRANT|REVOKE|CALL|LOAD|SET)\b",
    re.IGNORECASE,
)


def _quote_identifier(value: str, kind: str) -> str:
    if not _IDENTIFIER_PATTERN.fullmatch(value):
        raise ValueError(f"非法{kind}标识符")
    return f"`{value}`"


def _normalise_read_only_sql(sql: str) -> str:
    statement = sql.strip()
    if statement.endswith(";"):
        statement = statement[:-1].rstrip()
    if not statement or ";" in statement:
        raise ValueError("仅允许执行单条只读 SQL")
    if not _READ_ONLY_PATTERN.match(statement) or _FORBIDDEN_PATTERN.search(statement):
        raise ValueError("仅允许执行 SELECT 或 WITH 查询")
    return statement
"""
这个 Repository 同时服务于：
    构建知识库阶段：读取字段类型、字段值
    在线问答阶段：验证 SQL、执行 SQL

它操作的是 dw 数据库，也就是存放**真实业务数据**的数据仓库。
例如：
    dim_region：地区信息
    dim_customer：客户信息
    dim_product：商品信息
    fact_order：订单事实数据
它不负责保存知识库描述，而是负责读取真实表结构、真实字段值，以及执行最终生成的 SQL。
"""

class DWMySQLRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_column_types(self, table_name: str) -> dict[str, str]:
        # 定义sql
        quoted_table = _quote_identifier(table_name, "表名")
        sql = f"show columns from {quoted_table}"
        # 执行sql
        result = await self.session.execute(text(sql))
        # 解析结果[(),()]
        return {row.Field: row.Type for row in result.fetchall()}

    async def get_column_values(self, table_name: str, column_name: str, limit: int = 10) -> list[str]:
        # 定义sql
        if limit < 1 or limit > 100_000:
            raise ValueError("字段取值采样数量必须在 1 到 100000 之间")
        quoted_table = _quote_identifier(table_name, "表名")
        quoted_column = _quote_identifier(column_name, "字段名")
        sql = f"select distinct {quoted_column} from {quoted_table} limit :limit"
        # 执行sql
        result: Result = await self.session.execute(text(sql), {"limit": limit})
        # 解析结果
        return result.scalars().fetchall()

    async def get_db_info(self):
        """
        查询数据库环境信息，版本、方言
        :return:
        """
        # 查询数据版本
        result = await self.session.execute(text("select version()"))
        # 解析结果
        version = result.scalar()

        # 查询数据方言
        dialect = self.session.get_bind().dialect.name
        return {"version": version, "dialect": dialect}

    async def validate_sql(self, sql: str):
        """
        验证执行sql
        :param sql:
        :return: 如果sql语法不合法，会抛出异常
        """
        statement = _normalise_read_only_sql(sql)
        await self.session.execute(text(f"explain {statement}"))

    async def execute_sql(self, sql: str):
        statement = _normalise_read_only_sql(sql)
        result: Result = await self.session.execute(text(statement))
        return [dict(row_mapping) for row_mapping in result.mappings().fetchall()]
