# 导入 FastAPI 核心类
import uuid

from fastapi import FastAPI, Request

from app.api.routers.query_router import query_router
from app.core.context import request_id_ctx_var
from app.core.lifespan import lifespan

# 创建 FastAPI 应用实例
app = FastAPI(lifespan=lifespan)

# 绑定查询 router
app.include_router(query_router)


# 添加中间件，在每个请求中生成唯一的 request_id
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id_ctx_var.set(uuid.uuid4())
    return await call_next(request)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
