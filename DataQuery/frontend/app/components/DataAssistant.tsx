"use client";

import { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";

type QueryState = "idle" | "running" | "success" | "error" | "stopped";
type ProgressStatus = "running" | "success" | "error";
type ResultRow = Record<string, unknown>;

type ProgressItem = {
  step: string;
  status: ProgressStatus;
};

type Stats = {
  sql_corrections?: number;
  sql_validated?: boolean;
  execution_success?: boolean;
  error?: string;
};

type QuerySnapshot = {
  activity?: string[];
  details?: Record<string, unknown>;
  state: QueryState;
  progress: Record<string, ProgressStatus>;
  rows: ResultRow[] | null;
  stats: Stats | null;
  error: string;
  elapsed: number;
};

type StreamEvent = {
  type?: "progress" | "result" | "stats" | "error" | "log";
  message?: string;
  step?: string;
  stage?: string;
  status?: ProgressStatus;
  data?: unknown;
};

const STAGE_ORDER = [
  "抽取关键字",
  "召回字段",
  "召回指标",
  "召回字段取值",
  "合并信息",
  "过滤表",
  "过滤指标",
  "添加上下文",
  "生成SQL",
  "校验SQL",
  "校正SQL",
  "执行SQL",
];

const SUGGESTIONS = [
  {
    eyebrow: "地区分析",
    question: "统计华北地区销售总额",
    hint: "筛选地区并聚合销售金额",
  },
  {
    eyebrow: "商品洞察",
    question: "统计各商品分类的销售数量",
    hint: "按商品分类查看销量分布",
  },
  {
    eyebrow: "客户分析",
    question: "不同会员等级的订单金额分别是多少",
    hint: "关联客户维度与订单事实",
  },
];

const RECENT_KEY = "shopkeeper-data-recent-queries";
const RESULTS_KEY = "shopkeeper-data-query-results";

function activityText(event: StreamEvent): string | null {
  if (!event.step || (event.type !== "progress" && event.type !== "log")) return null;
  const status = event.status === "success" ? "完成" : event.status === "error" ? "失败" : "正在执行";
  const title = event.message || `${event.step} · ${status}`;
  if (event.data === undefined) return title;
  if (Array.isArray(event.data)) return `${title}：${event.data.length ? event.data.join("、") : "未找到匹配项"}`;
  if (typeof event.data === "string") return `${title}\n${event.data}`;
  return `${title}\n${JSON.stringify(event.data, null, 2)}`;
}

function statusLabel(state: QueryState): string {
  if (state === "running") return "正在分析";
  if (state === "success") return "分析完成";
  if (state === "error") return "需要检查";
  if (state === "stopped") return "已停止";
  return "等待提问";
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function csvValue(value: unknown): string {
  const text = displayValue(value);
  return `"${text.replaceAll('"', '""')}"`;
}

async function responseError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string };
    return body.detail || `请求失败（${response.status}）`;
  } catch {
    return `请求失败（${response.status}）`;
  }
}

export function DataAssistant() {
  const [input, setInput] = useState("");
  const [activeQuestion, setActiveQuestion] = useState("");
  const [queryState, setQueryState] = useState<QueryState>("idle");
  const [progress, setProgress] = useState<Record<string, ProgressStatus>>({});
  const [, setDetails] = useState<Record<string, unknown>>({});
  const [activity, setActivity] = useState<string[]>([]);
  const activityRef = useRef<HTMLDivElement | null>(null);
  const questionRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const panel = activityRef.current;
    if (panel) panel.scrollTop = panel.scrollHeight;
  }, [activity]);
  const [rows, setRows] = useState<ResultRow[] | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState("");
  const [recentQueries, setRecentQueries] = useState<string[]>([]);
  const [elapsed, setElapsed] = useState(0);
  const abortRef = useRef<AbortController | null>(null);
  const snapshotsRef = useRef<Record<string, QuerySnapshot>>({});
  const elapsedRef = useRef(0);

  useEffect(() => {
    if (queryState === "running" || queryState === "success" || queryState === "error") {
      questionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [queryState]);

  useEffect(() => {
    let savedQueries: string[] = [];
    try {
      const saved = JSON.parse(localStorage.getItem(RECENT_KEY) || "[]") as unknown;
      if (Array.isArray(saved)) {
        savedQueries = saved
          .filter((item): item is string => typeof item === "string")
          .slice(0, 6);
      }
    } catch {
      localStorage.removeItem(RECENT_KEY);
    }
    try {
      const saved = JSON.parse(localStorage.getItem(RESULTS_KEY) || "{}");
      if (saved && typeof saved === "object" && !Array.isArray(saved)) {
        snapshotsRef.current = saved;
      }
    } catch {
      snapshotsRef.current = {};
    }

    const hydrationTimer = window.setTimeout(() => setRecentQueries(savedQueries), 0);
    return () => window.clearTimeout(hydrationTimer);
  }, []);

  useEffect(() => {
    if (queryState !== "running") return;
    const timer = window.setInterval(() => {
      elapsedRef.current += 0.1;
      setElapsed((current) => current + 0.1);
    }, 100);
    return () => window.clearInterval(timer);
  }, [queryState]);

  const columns = useMemo(() => {
    if (!rows) return [];
    return Array.from(new Set(rows.flatMap((row) => Object.keys(row))));
  }, [rows]);

  const progressItems = useMemo<ProgressItem[]>(() => {
    return Object.entries(progress)
      .sort(([left], [right]) => {
        const leftIndex = STAGE_ORDER.indexOf(left);
        const rightIndex = STAGE_ORDER.indexOf(right);
        return (leftIndex < 0 ? 999 : leftIndex) - (rightIndex < 0 ? 999 : rightIndex);
      })
      .map(([step, status]) => ({ step, status }));
  }, [progress]);

  function rememberQuery(question: string) {
    setRecentQueries((current) => {
      const next = [question, ...current.filter((item) => item !== question)].slice(0, 6);
      try {
        localStorage.setItem(RECENT_KEY, JSON.stringify(next));
      } catch {}
      return next;
    });
  }

  function restoreQuery(question: string) {
    if (queryState === "running") return;
    const snapshot = snapshotsRef.current[question];
    setInput(snapshot ? "" : question);
    setActiveQuestion(question);
    setQueryState(snapshot?.state || "stopped");
    setProgress(snapshot?.progress || {});
    setDetails(snapshot?.details || {});
    setActivity(snapshot?.activity || []);
    setRows(snapshot?.rows ?? null);
    setStats(snapshot?.stats ?? null);
    setError(snapshot?.error || (snapshot ? "" : "这条旧记录仅保存了问题，没有保存结果。请提交问题重新查询。"));
    setElapsed(snapshot?.elapsed || 0);
  }

  function handleEvent(event: StreamEvent) {
    const message = activityText(event);
    if (message) setActivity((current) => [...current, message].slice(-100));
    if (event.stage) {
      setProgress((current) => ({ ...current, [event.stage as string]: "success" }));
      return;
    }

    if (event.type === "progress" && event.step && event.status) {
      if (event.data !== undefined) {
        setDetails((current) => ({ ...current, [event.step as string]: event.data }));
      }
      setProgress((current) => ({ ...current, [event.step as string]: event.status as ProgressStatus }));
      return;
    }

    if (event.type === "result") {
      setRows(Array.isArray(event.data) ? (event.data as ResultRow[]) : []);
      return;
    }

    if (event.type === "stats" && event.data && typeof event.data === "object") {
      const nextStats = event.data as Stats;
      setStats(nextStats);
      if (nextStats.execution_success === false && nextStats.error) {
        setError(nextStats.error);
      }
    }
  }

  async function runQuery(question: string) {
    const normalized = question.trim();
    if (!normalized || queryState === "running") return;

    const controller = new AbortController();
    elapsedRef.current = 0;
    const snapshot: QuerySnapshot = {
      activity: [],
      details: {},
      state: "running", progress: {}, rows: null, stats: null, error: "", elapsed: 0,
    };
    abortRef.current = controller;
    setInput("");
    setActiveQuestion(normalized);
    setQueryState("running");
    setProgress({});
    setDetails({});
    setActivity([]);
    setRows(null);
    setStats(null);
    setError("");
    setElapsed(0);
    rememberQuery(normalized);

    try {
      const response = await fetch("/api/query", {
        method: "POST",
        headers: {
          Accept: "text/event-stream",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ query: normalized }),
        signal: controller.signal,
      });

      if (!response.ok) throw new Error(await responseError(response));
      if (!response.body) throw new Error("数据服务没有返回可读取的响应流。");

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      let receivedResult = false;
      let streamFailure = "";

      const consumeBlock = (block: string) => {
        const payload = block
          .split(/\r?\n/)
          .filter((line) => line.startsWith("data:"))
          .map((line) => line.slice(5).trimStart())
          .join("\n");

        if (!payload) return;
        try {
          const event = JSON.parse(payload) as StreamEvent;
          const message = activityText(event);
          if (message) snapshot.activity = [...(snapshot.activity || []), message].slice(-100);
          if (event.stage) snapshot.progress[event.stage] = "success";
          if (event.type === "progress" && event.step && event.status) {
            snapshot.progress[event.step] = event.status;
            if (event.data !== undefined) snapshot.details![event.step] = event.data;
          }
          if (event.type === "result") {
            snapshot.rows = Array.isArray(event.data) ? event.data as ResultRow[] : [];
          }
          if (event.type === "stats" && event.data && typeof event.data === "object") {
            snapshot.stats = event.data as Stats;
          }
          handleEvent(event);
          if (event.type === "result") receivedResult = true;
          if (
            event.type === "error" &&
            event.data &&
            typeof event.data === "object" &&
            typeof (event.data as { error?: unknown }).error === "string"
          ) {
            streamFailure = (event.data as { error: string }).error;
          }
          if (
            event.type === "stats" &&
            event.data &&
            typeof event.data === "object" &&
            (event.data as Stats).execution_success === false
          ) {
            streamFailure = (event.data as Stats).error || streamFailure || "SQL 执行没有成功。";
          }
        } catch {
          throw new Error("收到了一条无法识别的分析事件。");
        }
      };

      while (true) {
        const { done, value } = await reader.read();
        buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
        const blocks = buffer.split(/\r?\n\r?\n/);
        buffer = blocks.pop() || "";

        for (const block of blocks) consumeBlock(block);
        if (done) break;
      }

      // A compliant SSE producer ends events with a blank line, but consume a
      // final unterminated block as well so the last result/stats is not lost.
      if (buffer.trim()) consumeBlock(buffer);

      if (streamFailure) throw new Error(streamFailure);
      if (!receivedResult) throw new Error("分析流已经结束，但没有返回数据结果。");
      setQueryState("success");
      snapshot.state = "success";

    } catch (caught) {
      if (caught instanceof DOMException && caught.name === "AbortError") {
        setQueryState("stopped");
        snapshot.state = "stopped";
        snapshot.error = "本次分析已停止，你可以修改问题后重新提交。";
        setError("本次分析已停止，你可以修改问题后重新提交。");
      } else {
        setQueryState("error");
        snapshot.state = "error";
        snapshot.error = caught instanceof Error ? caught.message : "分析过程中发生了未知错误。";
        setError(caught instanceof Error ? caught.message : "分析过程中发生了未知错误。");
      }
    } finally {
      snapshot.elapsed = elapsedRef.current;
      snapshotsRef.current[normalized] = snapshot;
      const savedQuestions = Object.keys(snapshotsRef.current).filter((question) => question !== normalized);
      for (const question of savedQuestions.slice(0, Math.max(0, savedQuestions.length - 5))) {
        delete snapshotsRef.current[question];
      }
      try {
        localStorage.setItem(RESULTS_KEY, JSON.stringify(snapshotsRef.current));
      } catch {}
      abortRef.current = null;
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void runQuery(input);
  }

  function textareaKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void runQuery(input);
    }
  }

  function resetWorkspace() {
    abortRef.current?.abort();
    setInput("");
    setActiveQuestion("");
    setQueryState("idle");
    setProgress({});
    setDetails({});
    setActivity([]);
    setRows(null);
    setStats(null);
    setError("");
    setElapsed(0);
  }

  function exportCsv() {
    if (!rows || !rows.length || !columns.length) return;
    const content = [
      columns.map(csvValue).join(","),
      ...rows.map((row) => columns.map((column) => csvValue(row[column])).join(",")),
    ].join("\n");
    const blob = new Blob(["\uFEFF", content], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `DataQuery数据仓库-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  const hasWorkspace = Boolean(activeQuestion);

  return (
    <main className={`app-frame${queryState === "running" ? " app-frame--running" : ""}`}>
      <header className="topbar">
        <button className="brand" type="button" onClick={resetWorkspace} aria-label="返回DataQuery数据仓库首页">
          <span className="brand-mark" aria-hidden="true">DQ</span>
          <span className="brand-copy">
            <strong>DataQuery数据仓库</strong>
            <small>DATA COPILOT</small>
          </span>
        </button>
        <div className={`service-state service-state--${queryState}`} aria-live="polite">
          <span className="service-dot" />
          {statusLabel(queryState)}
        </div>
      </header>

      <div className="shell">
        <aside className="sidebar">
          <button className="new-query" type="button" onClick={resetWorkspace}>
            <span aria-hidden="true">＋</span>
            新建问题
          </button>

          <section className="side-section" aria-labelledby="recent-title">
            <div className="side-heading">
              <h2 id="recent-title">最近问题</h2>
              <span>仅存于本机</span>
            </div>
            {recentQueries.length ? (
              <ul className="recent-list">
                {recentQueries.map((question) => (
                  <li key={question}>
                    <button type="button" onClick={() => restoreQuery(question)} disabled={queryState === "running"}>
                      <span className="recent-icon" aria-hidden="true">↗</span>
                      <span>{question}</span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="empty-recent">提交过的问题会出现在这里，点击可查看已保存的结果。</p>
            )}
          </section>

          <div className="sidebar-note">
            <span className="note-index">01</span>
            <p>问题越具体，结果越准确。请尽量说明指标、范围和分组方式。</p>
          </div>
        </aside>

        <section className="content">
          {!hasWorkspace ? (
            <div className="welcome">
              <div className="welcome-copy">
                <p className="kicker"><span />自然语言数据分析</p>
                <h1>把问题交给数据，<br /><em>不用手写 SQL。</em></h1>
                <p className="intro">
                  用日常语言描述你想知道的业务问题。系统会完成字段检索、指标理解、SQL 校验与查询执行。
                </p>
              </div>

              <div className="suggestions" aria-label="推荐问题">
                {SUGGESTIONS.map((suggestion, index) => (
                  <button
                    className="suggestion-card"
                    type="button"
                    key={suggestion.question}
                    onClick={() => void runQuery(suggestion.question)}
                  >
                    <span className="suggestion-number">0{index + 1}</span>
                    <span className="suggestion-eyebrow">{suggestion.eyebrow}</span>
                    <strong>{suggestion.question}</strong>
                    <small>{suggestion.hint}</small>
                    <span className="suggestion-arrow" aria-hidden="true">→</span>
                  </button>
                ))}
              </div>

              <div className="capability-strip" aria-label="核心能力">
                <span>字段语义召回</span>
                <span>指标口径识别</span>
                <span>SQL 自动校验</span>
                <span>流式结果呈现</span>
              </div>
            </div>
          ) : (
            <div className={`workspace${queryState === "running" ? " workspace--running" : ""}`}>
              <div className="question-block" ref={questionRef}>
                <span className="question-label">本次问题</span>
                <h1>{activeQuestion}</h1>
                <div className="question-meta">
                  <span>{queryState === "running" ? `${elapsed.toFixed(1)} 秒` : `用时 ${elapsed.toFixed(1)} 秒`}</span>
                  <span>自然语言查询</span>
                </div>
              </div>

              <div className="workspace-grid">
                <section className="result-panel" aria-live="polite">
                  <div className="panel-heading">
                    <div>
                      <span className="panel-index">回答</span>
                      <h2>DataQuery 分析</h2>
                    </div>
                    {rows && rows.length > 0 && (
                      <button className="export-button" type="button" onClick={exportCsv}>
                        导出 CSV <span aria-hidden="true">↓</span>
                      </button>
                    )}
                  </div>

                  <details className="answer-process" open={queryState === "running"}>
                    <summary>
                      <span>{queryState === "running" ? "正在分析" : "查看分析过程"}</span>
                      <small>{progressItems.filter((item) => item.status === "success").length} 个步骤已完成 · {elapsed.toFixed(1)} 秒</small>
                    </summary>
                    <div className="answer-stream" ref={activityRef} role="log" aria-label="实时执行过程" aria-live="polite" aria-relevant="additions" tabIndex={0}>
                      {activity.length === 0 && <p>正在理解你的问题，准备查找相关数据…</p>}
                      {activity.map((message, index) => (
                          <div className="analysis-activity-item" key={index}>
                            <span aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
                            <pre>{message}</pre>
                          </div>
                      ))}
                    </div>
                  </details>

                  {queryState === "running" && rows === null && !error && (
                    <div className="answer-current" role="status">
                      <span className="service-dot" />
                      {progressItems.filter((item) => item.status === "running").map((item) => item.step).join(" · ") || "正在准备分析"}
                      <span className="stream-cursor" aria-hidden="true">▍</span>
                    </div>
                  )}

                  {rows !== null && !error && <h3 className="answer-result-title">查询结果</h3>}

                  {error && (
                    <div className="error-card" role="alert">
                      <span className="error-symbol" aria-hidden="true">!</span>
                      <div>
                        <strong>{queryState === "stopped" ? "分析已停止" : "暂时无法完成查询"}</strong>
                        <p>{error}</p>
                      </div>
                    </div>
                  )}

                  {rows !== null && rows.length === 0 && !error && (
                    <div className="empty-result">
                      <span aria-hidden="true">◇</span>
                      <strong>查询成功，但没有匹配数据</strong>
                      <p>可以尝试扩大时间范围或调整筛选条件。</p>
                    </div>
                  )}

                  {rows && rows.length > 0 && (
                    <div className="table-wrap">
                      <table>
                        <thead>
                          <tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr>
                        </thead>
                        <tbody>
                          {rows.map((row, rowIndex) => (
                            <tr key={rowIndex}>
                              {columns.map((column) => <td key={column}>{displayValue(row[column])}</td>)}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {rows && rows.length > 0 && (
                    <div className="result-footer">
                      <span>共 {rows.length} 条记录</span>
                      {stats && <span>SQL 校正 {stats.sql_corrections ?? 0} 次</span>}
                      {stats?.sql_validated && <span className="verified">已通过校验</span>}
                    </div>
                  )}
                </section>

              </div>
            </div>
          )}

          <form className="composer" onSubmit={submit}>
            <div className="composer-inner">
              <label htmlFor="question">向数据提问</label>
              <textarea
                id="question"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={textareaKeyDown}
                placeholder="例如：统计华北地区销售总额"
                rows={2}
                maxLength={500}
                disabled={queryState === "running"}
              />
              <div className="composer-actions">
                <span>Enter 发送 · Shift + Enter 换行</span>
                {queryState === "running" ? (
                  <button className="stop-button" type="button" onClick={() => abortRef.current?.abort()}>
                    <span aria-hidden="true">■</span> 停止
                  </button>
                ) : (
                  <button className="send-button" type="submit" disabled={!input.trim()}>
                    开始分析 <span aria-hidden="true">↗</span>
                  </button>
                )}
              </div>
            </div>
          </form>
        </section>
      </div>
    </main>
  );
}
