import { useEffect, useState } from "react";
import {
  ArrowUpRight,
  BadgeCheck,
  ChartNoAxesCombined,
  FileSearch,
  FileText,
  GitCompareArrows,
  Globe,
  History,
  ScanSearch,
  Search,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

import "./App.css";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/+$/, "");
const apiUrl = (path) => `${API_BASE_URL}${path}`;

async function readApiResponse(response) {
  const contentType = response.headers.get("content-type") || "";
  const body = await response.text();
  let data;

  if (!contentType.includes("application/json")) {
    throw new Error(
      `API returned a non-JSON response (HTTP ${response.status}). Check that the backend API URL is correct.`,
    );
  }

  try {
    data = JSON.parse(body);
  } catch {
    throw new Error(`API returned invalid JSON (HTTP ${response.status}).`);
  }

  if (!response.ok) {
    const detail = data.detail;
    const message = typeof detail === "string"
      ? detail
      : Array.isArray(detail)
        ? detail.map((item) => item.msg).filter(Boolean).join("; ")
        : response.statusText;
    throw new Error(message || `Request failed (HTTP ${response.status}).`);
  }

  return data;
}

function SourceReferences({ sourceIds, sources }) {
  if (!Array.isArray(sourceIds)) {
    return <p className="report-empty">Source references not provided.</p>;
  }
  if (sourceIds.length === 0) {
    return <p className="report-empty">No source references returned.</p>;
  }

  return (
    <div className="report-source-refs">
      <strong>Sources: </strong>
      {sourceIds.map((sourceId, index) => {
        const source = sources.find((item) => item.id === sourceId);
        return (
          <span key={`${sourceId}-${index}`}>
            {index > 0 && ", "}
            {source ? <SourceCitation source={source} /> : <span>[{sourceId}]</span>}
          </span>
        );
      })}
    </div>
  );
}

function SourceCitation({ source }) {
  const title = source.title || "Title unavailable";
  const domain = source.domain || "Domain unavailable";

  if (!source.url) {
    return <span className="source-citation-label">Source {source.id}</span>;
  }

  return (
    <span className="source-citation">
      <a
        className="source-citation-label"
        href={source.url}
        target="_blank"
        rel="noreferrer"
        title={`${title} · ${domain}`}
        aria-label={`Source ${source.id}: ${title} (${domain}); opens in a new tab`}
      >
        Source {source.id}
      </a>
      <span className="source-citation-tooltip" role="tooltip">
        <strong>{title}</strong>
        <small>{domain}</small>
      </span>
    </span>
  );
}

function ReportSection({ title, children }) {
  return (
    <section className="report-section">
      <h4>{title}</h4>
      {children}
    </section>
  );
}

function ReportItems({ items, emptyMessage, renderItem }) {
  if (!Array.isArray(items)) {
    return <p className="report-empty">Not provided.</p>;
  }
  if (items.length === 0) {
    return <p className="report-empty">{emptyMessage}</p>;
  }

  return <ul className="report-list">{items.map(renderItem)}</ul>;
}

function ReportChat({ report }) {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const sources = Array.isArray(report.sources) ? report.sources : [];

  const handleSubmit = async (event) => {
    event.preventDefault();
    const submittedQuestion = question.trim();
    if (!submittedQuestion || loading) return;

    setLoading(true);
    setError(null);
    setMessages((items) => [...items, { role: "user", text: submittedQuestion }]);
    setQuestion("");
    try {
      const response = await fetch(apiUrl(`/api/research/${encodeURIComponent(report.research_id)}/ask`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: submittedQuestion }),
      });
      const data = await readApiResponse(response);
      setMessages((items) => [
        ...items,
        {
          role: "assistant",
          text: data.answer,
          sourceIds: Array.isArray(data.source_ids) ? data.source_ids : [],
        },
      ]);
    } catch (requestError) {
      setQuestion(submittedQuestion);
      setError(
        requestError instanceof TypeError
          ? `Could not reach the backend: ${requestError.message}`
          : requestError.message,
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="report-chat">
      <div className="chat-heading">
        <div>
          <p className="report-kicker">REPORT FOLLOW-UP</p>
          <h4>Ask VeriScope</h4>
        </div>
        <span className="chat-evidence-label">Answers use this report’s evidence</span>
      </div>
      <div className="chat-messages" aria-live="polite">
        {messages.length === 0 && (
          <p className="chat-empty">
            Ask about a finding, claim or source. VeriScope will say when this report doesn’t contain enough evidence.
          </p>
        )}
        {messages.map((message, index) => (
          <article className={`chat-message ${message.role}`} key={`${message.role}-${index}`}>
            <span>{message.role === "user" ? "You" : "Ask VeriScope"}</span>
            <p>{message.text}</p>
            {message.role === "assistant" && (
              <SourceReferences sourceIds={message.sourceIds} sources={sources} />
            )}
          </article>
        ))}
        {loading && <p className="chat-loading" role="status">Reviewing the report evidence…</p>}
      </div>
      {error && <p className="chat-error" role="alert">{error}</p>}
      <form className="chat-form" onSubmit={handleSubmit}>
        <label className="sr-only" htmlFor={`report-question-${report.research_id}`}>Ask a follow-up question</label>
        <input
          id={`report-question-${report.research_id}`}
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Ask a follow-up about this report…"
          maxLength={2000}
          disabled={loading}
        />
        <button type="submit" disabled={loading || !question.trim()}>
          Send <ArrowUpRight size={15} />
        </button>
      </form>
    </section>
  );
}

function ResearchReportView({ report }) {
  const sources = Array.isArray(report.sources) ? report.sources : [];
  const verificationUnavailable = report.agents_status?.verification?.status === "unavailable";
  const partialResearch = verificationUnavailable
    || report.agents_status?.conflict?.status === "unavailable";
  const agentNames = {
    research: "Source discovery",
    verification: "Claim verification",
    conflict: "Conflict detection",
    report: "Report generation",
  };

  return (
    <article className="research-report">
      <header className="report-header">
        <div className="report-title-row">
          <div>
            <p className="report-kicker">RESEARCH REPORT</p>
            <h3>{report.original_question || "Evidence review"}</h3>
          </div>
          {partialResearch && <span className="report-status">Partial Research</span>}
        </div>
        <p className="report-meta">
          {report.generated_at ? new Date(report.generated_at).toLocaleString() : "Date unavailable"}
          {" · "}
          {sources.length} source{sources.length === 1 ? "" : "s"}
        </p>
      </header>

      <ReportSection title="Agent execution">
        <div className="report-agent-grid">
          {Object.entries(agentNames).map(([key, name]) => {
            const agent = report.agents_status?.[key];
            return (
              <div className="report-agent" key={key}>
                <span>{name}</span>
                <strong className={agent?.status === "unavailable" ? "unavailable" : ""}>
                  {agent?.status || "Status not returned"}
                </strong>
                <p>{agent?.message || "No status message was returned."}</p>
              </div>
            );
          })}
        </div>
      </ReportSection>

      <ReportSection
        title={verificationUnavailable
          ? "System-generated status (not an AI-generated research summary)"
          : "Summary"}
      >
        <p>{report.summary ?? "Not provided."}</p>
      </ReportSection>

      <ReportSection title="Findings">
        <ReportItems
          items={report.findings}
          emptyMessage="No findings returned."
          renderItem={(finding, index) => (
            <li className="report-list-item" key={`${finding.title}-${index}`}>
              <h5>{finding.title}</h5>
              <p>{finding.detail}</p>
              <SourceReferences sourceIds={finding.source_ids} sources={sources} />
            </li>
          )}
        />
      </ReportSection>

      <ReportSection title="Claims">
        <ReportItems
          items={report.claims}
          emptyMessage="No claims returned."
          renderItem={(claim, index) => (
            <li className="report-list-item" key={`${claim.text}-${index}`}>
              <p className="claim-text">{claim.text}</p>
              <p><strong>Status:</strong> <span className="claim-status">{claim.status}</span></p>
              <p>{claim.explanation}</p>
              <SourceReferences sourceIds={claim.source_ids} sources={sources} />
            </li>
          )}
        />
      </ReportSection>

      <ReportSection title="Conflicts">
        <ReportItems
          items={report.conflicts}
          emptyMessage="No conflicts returned."
          renderItem={(conflict, index) => (
            <li className="report-list-item" key={`${conflict.title}-${index}`}>
              <h5>{conflict.title}</h5>
              <p>{conflict.explanation}</p>
              <SourceReferences sourceIds={conflict.source_ids} sources={sources} />
            </li>
          )}
        />
      </ReportSection>

      <ReportSection title="Sources">
        <ReportItems
          items={sources}
          emptyMessage="No sources returned."
          renderItem={(source, index) => (
            <li className="report-list-item source-item" key={`${source.id}-${index}`}>
              <SourceCitation source={source} />
              {source.published_at && <p>Published: {source.published_at}</p>}
              {source.retrieved_at && <p>Retrieved: {source.retrieved_at}</p>}
              {source.snippet && <p>{source.snippet}</p>}
            </li>
          )}
        />
      </ReportSection>

      <ReportSection title="Evidence assessment">
        <p>{report.evidence_assessment ?? "Not provided."}</p>
      </ReportSection>

      <ReportSection title="Limitations">
        <ReportItems
          items={report.limitations}
          emptyMessage="No limitations returned."
          renderItem={(limitation, index) => (
            <li className="report-list-item" key={`${limitation}-${index}`}>
              {limitation}
            </li>
          )}
        />
      </ReportSection>
      <ReportChat key={report.research_id} report={report} />
    </article>
  );
}

function App() {
  const [query, setQuery] = useState("");
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState(null);
  const [selectedReport, setSelectedReport] = useState(null);
  const [selectedLoading, setSelectedLoading] = useState(false);
  const [selectedError, setSelectedError] = useState(null);
  const [activeNav, setActiveNav] = useState("top");

  const processSteps = [
    {
      name: "Discover",
      detail: "Find credible sources and surface the evidence worth examining.",
      icon: FileSearch,
    },
    {
      name: "Verify",
      detail: "Evaluate claims against what the retrieved evidence actually says.",
      icon: BadgeCheck,
    },
    {
      name: "Compare",
      detail: "Look for direct disagreements and understand where sources differ.",
      icon: GitCompareArrows,
    },
    {
      name: "Report",
      detail: "Review findings, source links, limitations and agent status together.",
      icon: FileText,
    },
  ];

  const features = [
    {
      name: "Source Discovery",
      detail: "Find relevant material and keep each result close to the report it informs.",
      icon: Globe,
    },
    {
      name: "Claim Verification",
      detail: "Review claims against retrieved excerpts, with statuses and explanations.",
      icon: BadgeCheck,
    },
    {
      name: "Conflict Detection",
      detail: "Bring direct disagreements into view and retain the sources on both sides.",
      icon: GitCompareArrows,
    },
    {
      name: "Evidence Reports",
      detail: "Explore findings, linked sources, agent status and limitations together.",
      icon: ChartNoAxesCombined,
    },
  ];

  const navigateTo = (section, label = section) => {
    setActiveNav(label);
    document.getElementById(section)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const focusResearch = () => {
    navigateTo("research-form", "top");
    document.getElementById("research-query")?.focus({ preventScroll: true });
  };

  useEffect(() => {
    const loadHistory = async () => {
      setHistoryLoading(true);
      setHistoryError(null);
      try {
        const response = await fetch(apiUrl("/api/history"));
        const data = await readApiResponse(response);
        if (!Array.isArray(data)) {
          throw new Error("History endpoint returned an unexpected response.");
        }
        setHistory(data);
      } catch (requestError) {
        setHistoryError(
          requestError instanceof TypeError
            ? `Could not reach the backend: ${requestError.message}`
            : requestError.message,
        );
      } finally {
        setHistoryLoading(false);
      }
    };
    loadHistory();
  }, []);

  const loadReport = async (id) => {
    setSelectedLoading(true);
    setSelectedError(null);
    setSelectedReport(null);
    setReport(null);
    setError(null);
    try {
      const response = await fetch(apiUrl(`/api/research/${id}`));
      setSelectedReport(await readApiResponse(response));
    } catch (requestError) {
      setSelectedError(
        requestError instanceof TypeError
          ? `Could not reach the backend: ${requestError.message}`
          : requestError.message,
      );
    } finally {
      setSelectedLoading(false);
    }
  };

  const handleResearch = async (event) => {
    event.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError(null);
    setReport(null);
    setSelectedReport(null);
    setSelectedError(null);
    try {
      const response = await fetch(apiUrl("/api/research"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: query.trim() }),
      });
      const data = await readApiResponse(response);
      setReport(data);
      setHistory((items) => [
        {
          research_id: data.research_id,
          original_question: data.original_question,
          generated_at: data.generated_at,
          source_count: Array.isArray(data.sources) ? data.sources.length : 0,
        },
        ...items.filter((item) => item.research_id !== data.research_id),
      ]);
      requestAnimationFrame(() => navigateTo("workspace", "workspace"));
    } catch (requestError) {
      setError(
        requestError instanceof TypeError
          ? `Could not reach the backend: ${requestError.message}`
          : requestError.message,
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="site-shell">
      <header className="site-header">
        <a className="brand" href="#top" onClick={() => setActiveNav("top")}>
          <span className="brand-mark"><ShieldCheck size={19} /></span>
          <span>VeriScope<span className="brand-accent"> AI</span></span>
        </a>
        <nav className="main-nav" aria-label="Main navigation">
          {[
            ["about", "About"],
            ["process", "How it works"],
            ["features", "Features"],
            ["workspace", "Workspace"],
          ].map(([id, label]) => (
            <a
              className={activeNav === id ? "active" : ""}
              href={`#${id}`}
              key={id}
              onClick={() => setActiveNav(id)}
            >
              {label}
            </a>
          ))}
        </nav>
        <button className="header-cta" type="button" onClick={focusResearch}>
          Start researching <ArrowUpRight size={16} />
        </button>
      </header>

      <main>
        <section className="hero section-container" id="top">
          <div className="hero-copy">
            <p className="eyebrow"><span className="eyebrow-line" /> EVIDENCE-FIRST AI RESEARCH</p>
            <h1>Go Beyond Answers.<br /><span>Discover the Evidence.</span></h1>
            <p className="hero-description">
              Investigate complex questions, examine credible sources and understand what the evidence actually supports.
            </p>
            <form className="research-form" id="research-form" onSubmit={handleResearch}>
              <label className="sr-only" htmlFor="research-query">Research question</label>
              <Search size={19} aria-hidden="true" />
              <input
                id="research-query"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="What would you like to investigate?"
              />
              <button type="submit" disabled={loading}>
                {loading ? "Researching…" : "Start Research"}
                {!loading && <ArrowUpRight size={17} />}
              </button>
            </form>
            <p className="form-note">Explore the evidence. Keep the sources in reach.</p>
            {loading && <p className="inline-status" role="status">Research in progress…</p>}
            {error && <p className="inline-error" role="alert">{error}</p>}
          </div>

          <div className="hero-visual" aria-hidden="true">
            <div className="visual-orbit orbit-one" />
            <div className="visual-orbit orbit-two" />
            <div className="visual-glow" />
            <div className="evidence-card">
              <div className="evidence-card-top">
                <span className="evidence-icon"><Sparkles size={18} /></span>
                <span className="evidence-label">A clearer view of the evidence</span>
              </div>
              <div className="evidence-lines">
                <span className="line line-wide" />
                <span className="line line-medium" />
                <span className="line line-short" />
              </div>
              <div className="evidence-divider" />
              <div className="evidence-source">
                <span className="source-dot"><Globe size={14} /></span>
                <span><b>Sources stay connected</b><small>Trace findings back to the evidence</small></span>
                <ArrowUpRight size={15} />
              </div>
              <div className="evidence-source">
                <span className="source-dot source-purple"><ScanSearch size={14} /></span>
                <span><b>Claims get examined</b><small>See what is supported and what is not</small></span>
                <ArrowUpRight size={15} />
              </div>
            </div>
            <div className="visual-caption"><span /> Independent thinking starts with better evidence.</div>
          </div>
        </section>

        <section className="about-section section-container" id="about">
          <div className="section-intro">
            <p className="eyebrow"><span className="eyebrow-line" /> WHY VERISCOPE</p>
            <h2>Information is everywhere.<br /><span>Confidence takes evidence.</span></h2>
          </div>
          <div className="about-copy">
            <p>
              Confident-sounding answers can hide weak sources, missing context or claims that do not agree. VeriScope helps you look beyond the headline and examine the evidence behind an answer.
            </p>
            <p>
              By connecting research to sources, verification and limitations, it gives you a clearer basis for evaluating claims—without asking you to take an AI response on faith.
            </p>
          </div>
        </section>

        <section className="process-section section-container" id="process">
          <div className="section-heading">
            <div>
              <p className="eyebrow"><span className="eyebrow-line" /> A TRANSPARENT WORKFLOW</p>
              <h2>From question to <span>evidence.</span></h2>
            </div>
            <p className="section-aside">A focused process designed to keep sources and uncertainty visible.</p>
          </div>
          <div className="process-grid">
            {processSteps.map((step, index) => {
              const Icon = step.icon;
              return (
                <article className="process-card" key={step.name}>
                  <div className="process-card-top">
                    <span className="step-number">0{index + 1}</span>
                    <span className="process-icon"><Icon size={20} /></span>
                  </div>
                  <h3>{step.name}</h3>
                  <p>{step.detail}</p>
                  {index < processSteps.length - 1 && <span className="step-connector" aria-hidden="true" />}
                </article>
              );
            })}
          </div>
        </section>

        <section className="features-section section-container" id="features">
          <div className="section-heading">
            <div>
              <p className="eyebrow"><span className="eyebrow-line" /> BUILT FOR CLEARER RESEARCH</p>
              <h2>Evidence, not just <span>answers.</span></h2>
            </div>
            <p className="section-aside">Each capability supports a different part of a careful review.</p>
          </div>
          <div className="feature-grid">
            {features.map((feature, index) => {
              const Icon = feature.icon;
              return (
                <article className="feature-card" key={feature.name}>
                  <div className="feature-card-heading">
                    <span className="feature-icon"><Icon size={19} /></span>
                    <span className="feature-number">0{index + 1}</span>
                  </div>
                  <h3>{feature.name}</h3>
                  <p>{feature.detail}</p>
                  <span className="feature-accent" />
                </article>
              );
            })}
          </div>
        </section>

        <section className="workspace-section section-container" id="workspace">
          <div className="section-heading workspace-heading">
            <div>
              <p className="eyebrow"><span className="eyebrow-line" /> YOUR RESEARCH, IN ONE PLACE</p>
              <h2>Research <span>workspace.</span></h2>
            </div>
            <p className="section-aside">Saved reports and history from your VeriScope workspace.</p>
          </div>
          <div className="workspace-layout">
            <aside className="history-panel">
              <div className="panel-heading">
                <div><History size={17} /><h3>Research history</h3></div>
                <span>{historyLoading ? "Loading" : history.length}</span>
              </div>
              {historyLoading && <p className="panel-message">Loading saved research…</p>}
              {historyError && <p className="panel-error" role="alert">{historyError}</p>}
              {!historyLoading && !historyError && history.length === 0 && (
                <div className="history-empty">
                  <span><FileSearch size={20} /></span>
                  <p>No saved research yet.</p>
                  <small>Start with a question above to build your workspace.</small>
                </div>
              )}
              {history.length > 0 && (
                <ul className="history-list">
                  {history.map((item) => (
                    <li key={item.research_id}>
                      <button
                        type="button"
                        className={`history-item${selectedReport?.research_id === item.research_id ? " selected" : ""}`}
                        onClick={() => loadReport(item.research_id)}
                      >
                        <span className="history-item-icon"><FileText size={16} /></span>
                        <span className="history-item-copy">
                          <strong>{item.original_question}</strong>
                          <small>
                            {item.generated_at ? new Date(item.generated_at).toLocaleString() : "Date unavailable"}
                            {Number.isInteger(item.source_count) && ` · ${item.source_count} source${item.source_count === 1 ? "" : "s"}`}
                          </small>
                        </span>
                        <ArrowUpRight size={15} />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </aside>
            <div className="report-panel">
              {(selectedLoading || selectedError) && (
                <div className="panel-state">
                  {selectedLoading && <p className="panel-message" role="status">Loading report…</p>}
                  {selectedError && <p className="panel-error" role="alert">{selectedError}</p>}
                </div>
              )}
              {report && !selectedReport && <ResearchReportView report={report} />}
              {selectedReport && !selectedLoading && <ResearchReportView report={selectedReport} />}
              {!report && !selectedReport && !selectedLoading && !selectedError && (
                <div className="report-placeholder">
                  <span className="placeholder-icon"><FileText size={23} /></span>
                  <p className="eyebrow">READY WHEN YOU ARE</p>
                  <h3>Your evidence, clearly presented.</h3>
                  <p>Run a research question or select a saved report to see its findings, sources and limitations here.</p>
                  <button type="button" className="text-link" onClick={focusResearch}>
                    Start a research question <ArrowUpRight size={16} />
                  </button>
                </div>
              )}
            </div>
          </div>
        </section>
      </main>

      <footer className="site-footer">
        <div className="footer-main section-container">
          <div className="footer-brand">
            <a className="brand" href="#top" onClick={() => setActiveNav("top")}>
              <span className="brand-mark"><ShieldCheck size={19} /></span>
              <span>VeriScope<span className="brand-accent"> AI</span></span>
            </a>
            <p>Evidence-first research for questions that deserve more than a quick answer.</p>
          </div>
          <div className="footer-links">
            <span>EXPLORE</span>
            <a href="#about">About</a>
            <a href="#process">How it works</a>
            <a href="#features">Features</a>
          </div>
          <div className="footer-links">
            <span>WORKSPACE</span>
            <a href="#workspace">Research history</a>
            <a href="#research-form">Start researching</a>
          </div>
        </div>
        <div className="footer-bottom section-container">
          <span>VeriScope AI</span>
          <span>Look closer. Follow the evidence.</span>
        </div>
      </footer>
    </div>
  );
}

export default App;
