import unittest

from app.repositories.mysql.dw.dw_mysql_repository import (
    _normalise_read_only_sql,
    _quote_identifier,
)


class SQLSafetyTest(unittest.TestCase):
    def test_identifier_must_be_a_simple_mysql_identifier(self):
        self.assertEqual(_quote_identifier("fact_order", "表名"), "`fact_order`")
        with self.assertRaises(ValueError):
            _quote_identifier("fact_order; DROP TABLE users", "表名")

    def test_read_only_sql_accepts_select_and_with(self):
        self.assertEqual(_normalise_read_only_sql("SELECT 1;"), "SELECT 1")
        self.assertTrue(_normalise_read_only_sql("WITH data AS (SELECT 1) SELECT * FROM data").startswith("WITH"))

    def test_read_only_sql_rejects_writes_and_multiple_statements(self):
        for sql in ("DELETE FROM fact_order", "UPDATE fact_order SET order_amount = 0", "SELECT 1; DROP TABLE fact_order"):
            with self.subTest(sql=sql):
                with self.assertRaises(ValueError):
                    _normalise_read_only_sql(sql)


if __name__ == "__main__":
    unittest.main()
