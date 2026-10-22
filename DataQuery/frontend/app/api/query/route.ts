const LOCAL_BACKEND_URL = "http://127.0.0.1:8000/api/query";

function backendUrl(): string | null {
  const configured = process.env.DATA_AGENT_API_URL?.trim();
  if (configured) return configured;
  if (process.env.NODE_ENV !== "production") return LOCAL_BACKEND_URL;
  return null;
}

export async function POST(request: Request): Promise<Response> {
  const url = backendUrl();
  if (!url) {
    return Response.json(
      {
        detail:
          "服务尚未配置数据接口，请设置 DATA_AGENT_API_URL 后重新部署。",
      },
      { status: 503 },
    );
  }

  let payload: unknown;
  try {
    payload = await request.json();
  } catch {
    return Response.json({ detail: "请求内容不是有效的 JSON。" }, { status: 400 });
  }

  try {
    const upstream = await fetch(url, {
      method: "POST",
      headers: {
        Accept: "text/event-stream",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
      signal: request.signal,
      cache: "no-store",
    });

    if (!upstream.ok || !upstream.body) {
      const detail = await upstream.text();
      return Response.json(
        { detail: detail || `数据服务返回了 ${upstream.status}。` },
        { status: upstream.status || 502 },
      );
    }

    return new Response(upstream.body, {
      status: 200,
      headers: {
        "Cache-Control": "no-cache, no-transform",
        "Content-Type": "text/event-stream; charset=utf-8",
        Connection: "keep-alive",
        "X-Accel-Buffering": "no",
      },
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "未知连接错误";
    return Response.json(
      { detail: `无法连接数据服务：${message}` },
      { status: 502 },
    );
  }
}
