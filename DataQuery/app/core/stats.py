import threading
from dataclasses import dataclass, field

from app.core.log import logger


@dataclass
class SQLStats:
    """全局SQL统计收集器，线程安全"""

    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    # 全局累计统计
    total_queries: int = 0
    total_validation_attempts: int = 0
    total_validation_failures: int = 0
    total_correction_rounds: int = 0
    total_retry_exhausted: int = 0
    total_execution_success: int = 0
    total_execution_failures: int = 0

    def record_validation_pass(self):
        with self._lock:
            self.total_validation_attempts += 1

    def record_validation_fail(self):
        with self._lock:
            self.total_validation_attempts += 1
            self.total_validation_failures += 1

    def record_correction(self):
        with self._lock:
            self.total_correction_rounds += 1

    def record_retry_exhausted(self):
        with self._lock:
            self.total_retry_exhausted += 1

    def record_execution_success(self):
        with self._lock:
            self.total_queries += 1
            self.total_execution_success += 1

    def record_execution_failure(self):
        with self._lock:
            self.total_queries += 1
            self.total_execution_failures += 1

    def get_stats(self) -> dict:
        """获取全局统计快照"""
        with self._lock:
            va = self.total_validation_attempts
            vf = self.total_validation_failures
            tq = self.total_queries
            return {
                "total_queries": tq,
                "total_validation_attempts": va,
                "total_validation_failures": vf,
                "validation_pass_rate": f"{va - vf}/{va}" if va > 0 else "N/A",
                "total_correction_rounds": self.total_correction_rounds,
                "total_retry_exhausted": self.total_retry_exhausted,
                "execution_success": self.total_execution_success,
                "execution_failures": self.total_execution_failures,
                "execution_success_rate": f"{self.total_execution_success}/{tq}" if tq > 0 else "N/A",
            }

    def log_summary(self):
        """打印全局统计摘要到日志"""
        stats = self.get_stats()
        logger.info(
            f"SQL统计汇总 | 总查询: {stats['total_queries']} | "
            f"校验通过率: {stats['validation_pass_rate']} | "
            f"校正总轮次: {stats['total_correction_rounds']} | "
            f"重试耗尽次数: {stats['total_retry_exhausted']} | "
            f"执行成功率: {stats['execution_success_rate']}"
        )


# 全局单例
sql_stats = SQLStats()