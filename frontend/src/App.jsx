import { useCallback, useEffect, useState } from "react";

const views = {
  materials: { label: "素材发现", title: "发现值得写的内容", subtitle: "从行业素材开始，生成可审核、可追溯的内容草稿。" },
  drafts: { label: "内容草稿", title: "管理内容草稿", subtitle: "编辑、审核并保留每次修订，批准后导出 Markdown。" },
  sources: { label: "数据源设置", title: "让素材自动流入工作台", subtitle: "添加并测试 RSS 源，然后一键启动采集。" },
};

const statusLabels = { pending_review: "待审核", approved: "已批准", archived: "已归档" };

const iconPaths = {
  library: <><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5v-15Z" /><path d="M4 20.5A2.5 2.5 0 0 1 6.5 18H20M8 7h8M8 11h6" /></>,
  draft: <><path d="m6 3 12 0a2 2 0 0 1 2 2v14l-8-3-8 3V5a2 2 0 0 1 2-2Z" /><path d="M8 7h8M8 11h8" /></>,
  source: <><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-1.8 1.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-2.5V20a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1-1.8-1.8.1-.1A1.7 1.7 0 0 0 8 15a1.7 1.7 0 0 0-1.6-1H6v-2.5h.4a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9l-.1-.1 1.8-1.8.1.1a1.7 1.7 0 0 0 1.9.3 1.7 1.7 0 0 0 1-1.6V5h2.5v.4a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1 1.8 1.8-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.4V14h-.4a1.7 1.7 0 0 0-1.6 1Z" /></>,
  refresh: <><path d="M20 11a8 8 0 0 0-14.6-4L4 9" /><path d="M4 4v5h5M4 13a8 8 0 0 0 14.6 4L20 15" /><path d="M20 20v-5h-5" /></>,
  arrow: <><path d="M5 12h14M13 6l6 6-6 6" /></>,
  spark: <><path d="m12 3 1.3 5.7L19 10l-5.7 1.3L12 17l-1.3-5.7L5 10l5.7-1.3L12 3Z" /><path d="m19 16 .6 2.4L22 19l-2.4.6L19 22l-.6-2.4L16 19l2.4-.6L19 16Z" /></>,
  shield: <><path d="M12 3 20 6v5c0 5-3.4 8.4-8 10-4.6-1.6-8-5-8-10V6l8-3Z" /><path d="m8.5 12 2.2 2.2 4.8-5" /></>,
  external: <><path d="M14 5h5v5M19 5l-8 8" /><path d="M18 13v5a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" /></>,
};

function Icon({ name, size = 18, strokeWidth = 1.8 }) {
  return <svg className="icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{iconPaths[name]}</svg>;
}

function cookie(name) {
  return document.cookie.split("; ").find((part) => part.startsWith(`${name}=`))?.slice(name.length + 1) || "";
}

async function api(path, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const headers = { ...(options.body ? { "Content-Type": "application/json" } : {}), ...(options.headers || {}) };
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const csrf = cookie("pm_csrf");
    if (csrf) headers["X-CSRF-Token"] = csrf;
  }
  const requestOptions = { ...options, headers };
  if (requestOptions.body && typeof requestOptions.body !== "string") requestOptions.body = JSON.stringify(requestOptions.body);
  const response = await fetch(path, requestOptions);
  let data;
  try { data = await response.json(); } catch { data = await response.text(); }
  if (!response.ok) {
    if (response.status === 401) window.dispatchEvent(new Event("postmaker:unauthorized"));
    throw new Error(data?.detail || data || `请求失败（${response.status}）`);
  }
  return data;
}

function formatDate(value) {
  if (!value) return "时间未知";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value).slice(0, 10) : date.toLocaleDateString("zh-CN", { month: "short", day: "numeric" });
}

function initials(email = "PM") {
  return email.split(/[@.\s]/).filter(Boolean).slice(0, 2).map((part) => part[0].toUpperCase()).join("") || "PM";
}

function App() {
  const [ready, setReady] = useState(false);
  const [authRequired, setAuthRequired] = useState(false);
  const [user, setUser] = useState(null);
  const [view, setView] = useState("materials");
  const [toast, setToast] = useState("");
  const [materials, setMaterials] = useState([]);
  const [materialMode, setMaterialMode] = useState("trending");
  const [selectedMaterial, setSelectedMaterial] = useState(null);
  const [personas, setPersonas] = useState([]);
  const [sources, setSources] = useState([]);
  const [drafts, setDrafts] = useState([]);
  const [draftFilter, setDraftFilter] = useState("all");
  const [selectedDraft, setSelectedDraft] = useState(null);
  const [collection, setCollection] = useState({ status: "idle" });

  const notify = useCallback((message) => {
    setToast(message);
    window.clearTimeout(notify.timer);
    notify.timer = window.setTimeout(() => setToast(""), 2800);
  }, []);

  const loadMaterials = useCallback(async () => {
    const result = await api(`/api/materials?mode=${materialMode}&limit=40`);
    setMaterials(result.items || []);
  }, [materialMode]);

  const loadSources = useCallback(async () => {
    const result = await api("/api/sources");
    setSources(result.items || []);
  }, []);

  const loadDrafts = useCallback(async () => {
    const result = await api(`/api/drafts?status=${encodeURIComponent(draftFilter)}&limit=200`);
    setDrafts(result.items || []);
    return result.items || [];
  }, [draftFilter]);

  const loadCollection = useCallback(async () => {
    const result = await api("/api/collect/status");
    setCollection(result);
    return result;
  }, []);

  const refreshWorkspace = useCallback(async () => {
    try {
      await Promise.all([loadMaterials(), loadSources(), loadDrafts(), loadCollection()]);
    } catch (error) {
      notify(error.message);
    }
  }, [loadCollection, loadDrafts, loadMaterials, loadSources, notify]);

  useEffect(() => {
    const unauthorized = () => { setUser(null); if (authRequired) setReady(true); };
    window.addEventListener("postmaker:unauthorized", unauthorized);
    (async () => {
      try {
        const health = await api("/api/health");
        setAuthRequired(Boolean(health.auth_required));
        const me = await api("/api/auth/me");
        setUser(me.authenticated ? me.user : null);
        if (!health.auth_required || me.authenticated) {
          const personaData = await api("/api/personas");
          setPersonas(personaData || []);
          await refreshWorkspace();
        }
      } catch (error) {
        notify(error.message);
      } finally {
        setReady(true);
      }
    })();
    return () => window.removeEventListener("postmaker:unauthorized", unauthorized);
  }, [notify, refreshWorkspace]);

  useEffect(() => {
    if (!ready || (authRequired && !user)) return;
    loadMaterials().catch((error) => notify(error.message));
  }, [authRequired, loadMaterials, notify, ready, user]);

  useEffect(() => {
    if (!ready || (authRequired && !user)) return;
    loadDrafts().catch((error) => notify(error.message));
  }, [authRequired, draftFilter, loadDrafts, notify, ready, user]);

  useEffect(() => {
    if (collection.status !== "running" || (authRequired && !user)) return undefined;
    const timer = window.setInterval(async () => {
      try {
        const next = await loadCollection();
        if (next.status !== "running") {
          window.clearInterval(timer);
          await loadMaterials();
        }
      } catch { /* 保留上一次状态 */ }
    }, 2000);
    return () => window.clearInterval(timer);
  }, [authRequired, collection.status, loadCollection, loadMaterials, user]);

  const firstRun = sources.length === 0 && materials.length === 0 && drafts.length === 0;
  const page = views[view];

  if (!ready) return <LoadingScreen />;
  if (authRequired && !user) return <AuthScreen onSuccess={async (nextUser) => { setUser(nextUser); const data = await api("/api/personas"); setPersonas(data || []); await refreshWorkspace(); }} />;

  return (
    <div className="app-shell">
      <Sidebar view={view} setView={setView} sourceCount={sources.length} draftCount={drafts.length} />
      <main className="main-content">
        <header className="topbar">
          <div className="crumb"><span className="crumb-kicker">WORKSPACE</span><span className="crumb-divider">/</span><b>{page.label}</b></div>
          <div className="topbar-actions">
            <span className="today"><i />实时工作区 · {new Date().toLocaleDateString("zh-CN", { month: "long", day: "numeric" })}</span>
            <button className="icon-button" onClick={refreshWorkspace} title="刷新工作区" aria-label="刷新工作区"><Icon name="refresh" size={16} /></button>
            {user && <span className="user-email">{user.email}</span>}
            {user && <button className="link-button logout-button" onClick={async () => { await api("/api/auth/logout", { method: "POST" }); setUser(null); }}>退出</button>}
            <span className="avatar">{initials(user?.email)}</span>
          </div>
        </header>
        <section className="page-heading">
          <div className="heading-copy"><div className="heading-kicker"><span className="eyebrow">EDITORIAL WORKFLOW</span><span className="heading-dot" /> <span>{view === "materials" ? "DISCOVER" : view === "drafts" ? "REVIEW" : "CONNECT"}</span></div><h1>{page.title}</h1><p>{page.subtitle}</p></div>
          <div className="heading-actions">{view !== "sources" && <button className="primary-button" onClick={() => setView(view === "materials" ? "drafts" : "materials")}>{view === "materials" ? "查看草稿" : "回到素材"}<Icon name="arrow" size={15} /></button>}<span className="heading-meta"><Icon name="shield" size={15} /> 私密工作区</span></div>
        </section>
        {view === "materials" && <MaterialsView materials={materials} mode={materialMode} setMode={setMaterialMode} onRefresh={() => loadMaterials().catch((error) => notify(error.message))} notify={notify} selected={selectedMaterial} setSelected={setSelectedMaterial} personas={personas} onGenerate={async () => { await loadDrafts(); setView("drafts"); }} firstRun={firstRun} onSetup={() => setView("sources")} />}
        {view === "drafts" && <DraftsView drafts={drafts} filter={draftFilter} setFilter={setDraftFilter} selected={selectedDraft} setSelected={setSelectedDraft} personas={personas} notify={notify} reload={loadDrafts} />}
        {view === "sources" && <SourcesView sources={sources} setSources={setSources} collection={collection} loadSources={loadSources} loadCollection={loadCollection} notify={notify} />}
        <footer className="page-footer"><span><strong>postmaker</strong> · 内容情报与生产工作台</span><span>DataRadar connected <i /></span></footer>
      </main>
      {toast && <div className="toast" role="status" aria-live="polite">{toast}</div>}
    </div>
  );
}

function LoadingScreen() { return <div className="center-screen"><div className="spinner" /><p>正在准备你的工作区…</p></div>; }

function AuthScreen({ onSuccess }) {
  const [register, setRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  async function submit(event) {
    event.preventDefault(); setSubmitting(true); setError("");
    try {
      const data = await api(register ? "/api/auth/register" : "/api/auth/login", { method: "POST", body: JSON.stringify({ email: email.trim(), password }) });
      await onSuccess(data.user);
    } catch (err) { setError(err.message); } finally { setSubmitting(false); }
  }
  return <div className="auth-screen"><div className="auth-orbit orbit-one" /><div className="auth-orbit orbit-two" /><div className="auth-layout"><section className="auth-intro"><div className="auth-badge"><Icon name="spark" size={15} /> PRIVATE CONTENT OS</div><h1>把灵感变成<br /><em>可以交付的内容。</em></h1><p>从信息采集、选题判断到人工审核，让每一次发布都更有依据。</p><div className="auth-proof"><span><b>01</b>发现值得写的内容</span><span><b>02</b>用 persona 生成草稿</span><span><b>03</b>审核后安心交付</span></div></section><div className="auth-card"><Brand compact /><span className="eyebrow">PRIVATE WORKSPACE</span><h2>{register ? "创建你的内容工作区" : "欢迎回来"}</h2><p>{register ? "注册后，你的 RSS、素材和草稿会保存在独立工作区。" : "登录后继续管理你的内容生产流程。"}</p><form onSubmit={submit} className="auth-form"><label>邮箱<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" placeholder="you@example.com" /></label><label>密码<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} minLength="8" required autoComplete={register ? "new-password" : "current-password"} placeholder="至少 8 位字符" /></label>{error && <div className="form-error">{error}</div>}<button className="primary-button full" disabled={submitting}>{submitting ? "处理中…" : register ? "注册并进入" : "登录工作台"}<Icon name="arrow" size={15} /></button></form><button className="link-button auth-switch" onClick={() => { setRegister(!register); setError(""); }}>{register ? "已有账号？登录" : "还没有账号？创建工作区"}</button></div></div></div>;
}

function Brand({ compact = false }) { return <div className={`brand ${compact ? "brand-compact" : ""}`}><span className="brand-mark">P</span><span><strong>postmaker</strong><small>CONTENT STUDIO</small></span></div>; }

function Sidebar({ view, setView, sourceCount, draftCount }) { return <aside className="sidebar"><div className="sidebar-top"><Brand /><div className="workspace-switcher"><span className="workspace-avatar">P</span><span><b>个人工作区</b><small>Private workspace</small></span><span className="switcher-chevron">⌄</span></div></div><div className="sidebar-nav"><span className="sidebar-label">工作区导航</span><NavButton active={view === "materials"} onClick={() => setView("materials")} icon="library" label="素材库" hint="发现" count={sourceCount ? "" : "—"} /><NavButton active={view === "drafts"} onClick={() => setView("drafts")} icon="draft" label="内容草稿" hint="审核" count={draftCount} /><NavButton active={view === "sources"} onClick={() => setView("sources")} icon="source" label="数据源" hint="连接" count={sourceCount} /></div><div className="sidebar-bottom"><div className="online-indicator"><i /><span><b>工作区在线</b><small>数据按账号隔离</small></span></div><a href="/api/health" target="_blank" rel="noreferrer"><Icon name="external" size={13} /> 服务状态</a><div className="sidebar-version">POSTMAKER 0.1 · LOCAL FIRST</div></div></aside>; }
function NavButton({ active, onClick, icon, label, hint, count }) { return <button className={`nav-button ${active ? "active" : ""}`} onClick={onClick}><span className="nav-icon"><Icon name={icon} size={18} /></span><span className="nav-copy"><b>{label}</b><small>{hint}</small></span>{count !== "" && <em>{count}</em>}<span className="nav-arrow">↗</span></button>; }

function MaterialsView({ materials, mode, setMode, onRefresh, notify, selected, setSelected, personas, onGenerate, firstRun, onSetup }) {
  return <>
    {firstRun && <section className="onboarding"><div><span className="eyebrow">GET STARTED</span><h2>三步完成第一篇内容</h2><p>添加 RSS、启动采集，再从素材生成并审核草稿。</p></div><div className="onboarding-steps"><span><b>1</b>配置数据源</span><span><b>2</b>立即采集</span><span><b>3</b>生成并导出</span></div><button className="primary-button" onClick={onSetup}>开始配置 <span>→</span></button></section>}
    <div className="content-grid"><section className="panel"><div className="panel-heading"><div><h2>行业素材</h2><p>来自 DataRadar 的近期内容</p></div><div className="segmented"><button className={mode === "trending" ? "selected" : ""} onClick={() => setMode("trending")}>热门</button><button className={mode === "recent" ? "selected" : ""} onClick={() => setMode("recent")}>最新</button></div></div><div className="scroll-list">{materials.length ? materials.map((item) => <button key={item.id} className={`list-item material-row ${selected?.id === item.id ? "selected" : ""}`} onClick={async () => setSelected(await api(`/api/materials/${item.id}`))}><strong>{item.title || "未命名素材"}</strong><span><i>{item.source_platform || "未知来源"}</i><i>{formatDate(item.published_at)}</i><b>{item.category || "未分类"}</b><b className="score">重要性 {Number(item.importance_score || 0).toFixed(1)}</b></span></button>) : <EmptyState compact text="暂时没有素材，请先配置 RSS 并启动采集。" />}</div><div className="panel-footer"><span>{materials.length} 条素材 · {mode === "trending" ? "热门" : "最新"}</span><button className="link-button" onClick={onRefresh}>刷新列表 ↻</button></div></section><MaterialDetail material={selected} personas={personas} onGenerate={onGenerate} notify={notify} /></div>
  </>;
}

function MaterialDetail({ material, personas, onGenerate, notify }) {
  const [personaId, setPersonaId] = useState(personas[0]?.id || "");
  const [loading, setLoading] = useState(false);
  useEffect(() => { if (!personaId && personas[0]) setPersonaId(personas[0].id); }, [personaId, personas]);
  if (!material) return <section className="panel detail-panel"><EmptyState icon="↖" title="选择一条素材" text="查看摘要与原文来源，然后选择 persona 生成初稿。" /></section>;
  async function generate() { setLoading(true); try { await api("/api/drafts/generate", { method: "POST", body: JSON.stringify({ material_id: Number(material.id), persona_id: personaId }) }); await onGenerate(); } catch (error) { notify(error.message); } finally { setLoading(false); } }
  const sourceUrl = /^https?:\/\//i.test(material.source_url || "") ? material.source_url : "";
  return <section className="panel detail-panel"><div className="detail-kicker">素材详情 <span>·</span> {material.source_platform || "未知来源"} <span>·</span> {formatDate(material.published_at)}</div><h2>{material.title}</h2><div className="chip-row"><span className="chip">{material.category || "未分类"}</span>{(material.tags || []).slice(0, 6).map((tag) => <span className="chip" key={tag}>{tag}</span>)}<span className="chip score">重要性 {Number(material.importance_score || 0).toFixed(1)}</span></div><p className="summary">{material.ai_summary || material.summary || "这条素材暂时没有摘要。"}</p><div className="source-card"><span>原始来源</span>{sourceUrl ? <a href={sourceUrl} target="_blank" rel="noreferrer">{sourceUrl} ↗</a> : <small>未提供有效来源链接</small>}{material.full_text && <p>{material.full_text}</p>}</div><div className="generate-bar"><select value={personaId} onChange={(e) => setPersonaId(e.target.value)} disabled={!personas.length}><option value="">选择写作 persona</option>{personas.map((persona) => <option value={persona.id} key={persona.id}>{persona.name} · {persona.description || persona.id}</option>)}</select><button className="primary-button" disabled={!personaId || loading} onClick={generate}>{loading ? "生成中…" : "生成审核草稿"}<span>→</span></button></div></section>;
}

function SourcesView({ sources, collection, loadSources, loadCollection, notify }) {
  const empty = { name: "", url: "", id: "", max_age_days: 3 };
  const [form, setForm] = useState(empty);
  const [editing, setEditing] = useState(null);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const update = (key, value) => setForm((current) => ({ ...current, [key]: value }));
  function reset() { setForm(empty); setEditing(null); }
  async function test() { setTesting(true); try { const result = await api("/api/sources/rss/test", { method: "POST", body: JSON.stringify(form) }); notify(`测试成功：读取到 ${Number(result.item_count || 0)} 条内容`); } catch (error) { notify(`测试失败：${error.message}`); } finally { setTesting(false); } }
  async function save(event) { event.preventDefault(); setSaving(true); try { if (editing) { await api(`/api/sources/rss/${encodeURIComponent(editing.id)}`, { method: "PUT", body: { ...form, id: undefined, enabled: editing.enabled } }); notify("数据源修改已保存"); } else { await api("/api/sources/rss", { method: "POST", body: form }); notify("数据源已保存并启用"); } reset(); await loadSources(); } catch (error) { notify(`保存失败：${error.message}`); } finally { setSaving(false); } }
  async function toggle(source) { try { await api(`/api/sources/${encodeURIComponent(source.id)}/${source.enabled ? "disable" : "enable"}`, { method: "POST" }); await loadSources(); notify(source.enabled ? "数据源已停用" : "数据源已启用"); } catch (error) { notify(error.message); } }
  async function remove(source) { if (!window.confirm(`确定删除数据源“${source.name || source.id}”吗？`)) return; try { await api(`/api/sources/${encodeURIComponent(source.id)}`, { method: "DELETE" }); await loadSources(); notify("数据源已删除"); } catch (error) { notify(error.message); } }
  async function collect() { try { await api("/api/collect", { method: "POST" }); await loadCollection(); notify("采集任务已启动"); } catch (error) { notify(error.message); } }
  return <div className="content-grid sources-grid"><section className="panel"><div className="panel-heading"><div><h2>已配置的数据源</h2><p>管理 RSS，素材会进入你的独立工作区</p></div><button className="link-button" onClick={loadSources}>刷新 ↻</button></div><div className="scroll-list">{sources.length ? sources.map((source) => <div className="source-row" key={source.id}><div className="source-main"><div><span className={`source-dot ${source.enabled ? "on" : ""}`} /> <strong>{source.name || source.id}</strong><em>{source.kind === "rss" ? "RSS" : "Web"}</em></div><p>{source.url}</p><small>{source.enabled ? "已启用" : "已停用"} · 最近 {Number(source.max_age_days || 0)} 天</small></div><div className="row-actions">{source.kind === "rss" && <button onClick={() => { setEditing(source); setForm({ name: source.name || "", url: source.url || "", id: source.id || "", max_age_days: source.max_age_days ?? 3 }); }}>编辑</button>}<button onClick={() => toggle(source)}>{source.enabled ? "停用" : "启用"}</button><button onClick={() => remove(source)} className="danger">删除</button></div></div>) : <EmptyState compact text="还没有数据源，在右侧填写一个 RSS 地址开始采集。" />}</div><div className="panel-footer"><span>{sources.length} 个数据源 · {collection.status === "running" ? "采集中…" : collection.status === "completed" ? "最近一次采集已完成" : "可随时采集"}</span><button className="primary-button compact" onClick={collect} disabled={collection.status === "running"}>立即采集</button></div></section><section className="panel form-panel"><div className="panel-heading"><div><h2>{editing ? "编辑 RSS 源" : "添加 RSS 源"}</h2><p>{editing ? "源 ID 保持不变，修改后用于下一次采集。" : "只需要填写名称和地址，不必编辑 YAML。"}</p></div></div><form onSubmit={save} className="source-form"><div className="help-box">RSS 地址通常以 <code>.xml</code>、<code>/feed</code> 或 <code>/rss</code> 结尾。</div><label>源名称 <small>可选</small><input value={form.name} onChange={(e) => update("name", e.target.value)} placeholder="例如：少数派" maxLength="200" /></label><label>RSS 地址<input type="url" value={form.url} onChange={(e) => update("url", e.target.value)} placeholder="https://example.com/feed.xml" required maxLength="2000" /></label><label>源 ID <small>可选，留空自动生成</small><input value={form.id} onChange={(e) => update("id", e.target.value)} disabled={Boolean(editing)} pattern="[A-Za-z0-9][A-Za-z0-9_-]*" placeholder="例如：sspai" /></label><label>保留最近多少天的文章<input type="number" min="0" max="3650" value={form.max_age_days} onChange={(e) => update("max_age_days", Number(e.target.value))} /><small>填 0 表示不按时间过滤。</small></label><div className="form-actions"><button type="button" className="secondary-button" onClick={test} disabled={testing}>{testing ? "测试中…" : "测试地址"}</button>{editing && <button type="button" className="secondary-button" onClick={reset}>取消编辑</button>}<button type="submit" className="primary-button" disabled={saving}>{saving ? "保存中…" : editing ? "保存修改" : "保存并启用"}</button></div></form></section></div>;
}

function DraftsView({ drafts, filter, setFilter, selected, setSelected, notify, reload }) {
  const [form, setForm] = useState(null);
  const [revisions, setRevisions] = useState([]);
  useEffect(() => { if (selected) setForm({ title: selected.title, body: selected.body }); }, [selected]);
  async function choose(draft) { setSelected(await api(`/api/drafts/${draft.id}`)); setRevisions([]); }
  async function save(status) { if (!selected || !form?.title.trim() || !form.body.trim()) return; try { const updated = await api(`/api/drafts/${selected.id}`, { method: "PUT", body: { ...form, ...(status ? { status } : {}) } }); setSelected(updated); await reload(); const messages = { approved: "已批准", pending_review: "已退回审核", archived: "已归档" }; notify(status ? messages[status] : "修改已保存并记录修订"); } catch (error) { notify(error.message); } }
  async function showRevisions() { try { const result = await api(`/api/drafts/${selected.id}/revisions`); setRevisions(result.items || []); } catch (error) { notify(error.message); } }
  async function restore(id) { try { const updated = await api(`/api/drafts/${selected.id}/restore`, { method: "POST", body: JSON.stringify({ revision_id: Number(id) }) }); setSelected(updated); await reload(); notify("已恢复版本，并创建新的修订记录"); } catch (error) { notify(error.message); } }
  return <div className="content-grid drafts-grid"><section className="panel"><div className="panel-heading"><div><h2>内容草稿</h2><p>编辑、审核并保留每次修订</p></div><select value={filter} onChange={(e) => setFilter(e.target.value)}><option value="all">全部状态</option><option value="pending_review">待审核</option><option value="approved">已批准</option><option value="archived">已归档</option></select></div><div className="scroll-list">{drafts.length ? drafts.map((draft) => <button key={draft.id} className={`list-item draft-row ${selected?.id === draft.id ? "selected" : ""}`} onClick={() => choose(draft)}><strong>{draft.title}</strong><span><i>{draft.persona_name}</i><i>{formatDate(draft.updated_at)}</i><b className={`status ${draft.status}`}>{statusLabels[draft.status] || draft.status}</b></span></button>) : <EmptyState compact text="还没有草稿。从素材库生成第一篇吧。" />}</div><div className="panel-footer"><span>{drafts.length} 篇草稿</span><button className="link-button" onClick={reload}>刷新 ↻</button></div></section><section className="panel editor-panel">{!selected || !form ? <EmptyState icon="▤" title="选择一篇草稿" text="生成后的草稿会出现在这里。" /> : <><div className="editor-heading"><div><h2>{selected.title}</h2><span>{selected.persona_name} · {selected.model_used || "未记录模型"} · <b className={`status ${selected.status}`}>{statusLabels[selected.status]}</b></span></div><div className="row-actions"><button onClick={() => save()}>保存</button>{selected.status !== "approved" ? <button onClick={() => save("approved")} className="approve">批准</button> : <button onClick={() => save("pending_review")}>退回审核</button>}<button onClick={() => save("archived")}>归档</button>{selected.status === "approved" ? <button className="export" onClick={() => { window.location.href = `/api/drafts/${selected.id}/export.md`; }}>导出 .md</button> : <button disabled title="请先批准草稿">导出 .md</button>}</div></div><div className="editor-content"><label>标题<input value={form.title} maxLength="500" onChange={(e) => setForm({ ...form, title: e.target.value })} /></label><label>正文 <small>Markdown</small><textarea value={form.body} maxLength="200000" onChange={(e) => setForm({ ...form, body: e.target.value })} /></label><div className="source-card"><span>素材来源</span><b>{selected.material?.title || "未知素材"}</b>{selected.material?.source_url && <a href={selected.material.source_url} target="_blank" rel="noreferrer">查看原文 ↗</a>}</div><button className="revision-toggle" onClick={showRevisions}>修订历史 ↗</button>{revisions.length > 0 && <div className="revision-list">{revisions.map((revision) => <div key={revision.id}><span>修订 #{revision.id} · {formatDate(revision.created_at)} · {statusLabels[revision.status]}</span><button onClick={() => restore(revision.id)}>恢复此版本</button></div>)}</div>}</div></>}</section></div>;
}

function EmptyState({ icon = "○", title, text, compact = false }) { return <div className={compact ? "empty-inline" : "empty-state"}>{!compact && <span className="empty-icon">{icon}</span>}{title && <h3>{title}</h3>}<p>{text}</p></div>; }

export default App;
