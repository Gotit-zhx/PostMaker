const state = { view: "materials", mode: "trending", materials: [], personas: [], selectedMaterial: null, drafts: [], draftCount: 0, selectedDraft: null, revisionsOpen: false, sources: [], editingSource: null, collectionPoll: null, user: null };
const $ = (selector) => document.querySelector(selector);
const escapeHtml = (value = "") => String(value).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
const niceDate = (value) => { if (!value) return "时间未知"; const date = new Date(value); return Number.isNaN(date.getTime()) ? String(value).slice(0, 10) : date.toLocaleDateString("zh-CN", { month: "short", day: "numeric" }); };
const toast = (message) => { const node = $("#toast"); node.textContent = message; node.classList.add("show"); clearTimeout(toast.timer); toast.timer = setTimeout(() => node.classList.remove("show"), 2600); };
function cookie(name) { return document.cookie.split("; ").find((part) => part.startsWith(`${name}=`))?.slice(name.length + 1) || ""; }
function showAuthScreen(show) { $("#auth-screen").classList.toggle("hidden", !show); document.querySelector(".shell").classList.toggle("hidden", show); }
async function api(path, options = {}) { const method = (options.method || "GET").toUpperCase(); const headers = { ...(options.body ? { "Content-Type": "application/json" } : {}), ...options.headers }; if (!["GET", "HEAD", "OPTIONS"].includes(method)) { const csrf = cookie("pm_csrf"); if (csrf) headers["X-CSRF-Token"] = csrf; } const response = await fetch(path, { ...options, headers }); let data; try { data = await response.json(); } catch { data = await response.text(); } if (response.status === 401) showAuthScreen(true); if (!response.ok) throw new Error(data?.detail || data || `请求失败 (${response.status})`); return data; }
function setAuthMode(register) { $("#auth-title").textContent = register ? "创建工作区" : "登录工作台"; $("#auth-subtitle").textContent = register ? "注册后即可拥有独立的数据源、素材和草稿。" : "登录后管理你的独立内容工作区。"; $("#auth-submit").textContent = register ? "注册并进入" : "登录"; $("#auth-password").autocomplete = register ? "new-password" : "current-password"; $("#auth-switch").textContent = register ? "已有账号？登录" : "还没有账号？注册"; }
async function submitAuth(event) { event.preventDefault(); const register = $("#auth-submit").textContent.includes("注册"); const result = $("#auth-result"); const button = $("#auth-submit"); button.disabled = true; result.textContent = ""; try { const data = await api(register ? "/api/auth/register" : "/api/auth/login", { method: "POST", body: JSON.stringify({ email: $("#auth-email").value.trim(), password: $("#auth-password").value }) }); state.user = data.user; $("#user-email").textContent = data.user?.email || ""; $("#logout-button").classList.remove("hidden"); showAuthScreen(false); await Promise.all([loadMaterials(), loadDraftCount(), loadSources()]); updateGettingStarted(); toast(register ? "工作区已创建" : "登录成功"); } catch (error) { result.className = "form-result error"; result.textContent = error.message; } finally { button.disabled = false; } }
function setView(view) {
  state.view = view;
  $("#materials-view").classList.toggle("hidden", view !== "materials"); $("#drafts-view").classList.toggle("hidden", view !== "drafts"); $("#sources-view").classList.toggle("hidden", view !== "sources");
  document.querySelectorAll(".nav-item").forEach((button) => button.classList.toggle("active", button.dataset.view === view));
  const labels = { materials: ["素材发现", "发现值得写的内容", "从行业素材开始，生成可审核、可追溯的内容草稿。"], drafts: ["内容草稿", "管理内容草稿", "编辑、审核并保留每次修订，批准后导出 Markdown。"], sources: ["数据源设置", "让素材自动流入工作台", "添加并测试 RSS 源，然后一键启动采集。"] };
  const [crumb, title, subtitle] = labels[view] || labels.materials;
  $("#crumb").textContent = crumb; $("#page-title").textContent = title; $("#page-subtitle").textContent = subtitle;
  $("#toggle-view").innerHTML = view === "materials" ? '查看草稿 <span>→</span>' : '回到素材 <span>→</span>';
  $("#toggle-view").classList.toggle("hidden", view === "sources");
  if (view === "drafts") loadDrafts();
  if (view === "sources") loadSources();
}
function updateGettingStarted() {
  const node = $("#getting-started");
  if (!node) return;
  const firstRun = state.sources.length === 0 && state.materials.length === 0 && state.draftCount === 0;
  node.classList.toggle("hidden", !firstRun || state.view !== "materials");
}
function renderMaterials() {
  const host = $("#material-list"); $("#material-count").textContent = state.materials.length;
  $("#material-meta").textContent = `${state.materials.length} 条素材 · ${state.mode === "trending" ? "热门" : "最新"}`;
  if (!state.materials.length) { host.innerHTML = '<div class="empty-inline">暂时没有素材。请确认 DataRadar 已启动并完成采集。</div>'; return; }
  host.innerHTML = state.materials.map((item) => `<button class="material-item ${state.selectedMaterial?.id === item.id ? "selected" : ""}" data-material-id="${Number(item.id)}"><span class="item-title">${escapeHtml(item.title || "未命名素材")}</span><span class="item-meta"><span>${escapeHtml(item.source_platform || "未知来源")}</span><span>·</span><span>${niceDate(item.published_at)}</span><span class="tag">${escapeHtml(item.category || "未分类")}</span><span class="score">重要性 ${Number(item.importance_score || 0).toFixed(1)}</span></span></button>`).join("");
  host.querySelectorAll("[data-material-id]").forEach((button) => button.addEventListener("click", () => selectMaterial(Number(button.dataset.materialId))));
  updateGettingStarted();
}
async function loadMaterials() {
  const host = $("#material-list"); host.innerHTML = '<div class="loading">正在连接 DataRadar…</div>';
  try { const result = await api(`/api/materials?mode=${state.mode}&limit=40`); state.materials = result.items || []; renderMaterials(); if (state.selectedMaterial) await selectMaterial(state.selectedMaterial.id); }
  catch (error) { host.innerHTML = `<div class="empty-inline">${escapeHtml(error.message)}<br>启动 DataRadar API 后可加载素材。</div>`; $("#material-meta").textContent = "连接失败"; }
  updateGettingStarted();
}

function sourceStatusLabel(source) { return source.enabled ? "已启用" : "已停用"; }
function renderSources() {
  const host = $("#source-list"); $("#source-count").textContent = state.sources.length; $("#source-meta").textContent = `${state.sources.length} 个数据源 · RSS 可视化配置`;
  if (!state.sources.length) { host.innerHTML = '<div class="empty-inline">还没有数据源。<br>在右侧填写一个 RSS 地址开始采集。</div>'; return; }
  host.innerHTML = state.sources.map((source) => `<div class="source-item"><div class="source-item-main"><div class="source-item-title"><span class="source-dot ${source.enabled ? "on" : "off"}"></span>${escapeHtml(source.name || source.id)}<span class="source-kind">${source.kind === "rss" ? "RSS" : "Web"}</span></div><div class="source-item-url">${escapeHtml(source.url || "")}</div><div class="source-item-meta">${sourceStatusLabel(source)} · ${source.kind === "rss" ? `最近 ${Number(source.max_age_days || 0)} 天` : "网页目标"}</div></div><div class="source-actions">${source.kind === "rss" ? `<button class="small-button" data-source-edit="${escapeHtml(source.id)}">编辑</button>` : ""}<button class="small-button" data-source-test="${escapeHtml(source.id)}">测试</button><button class="small-button" data-source-toggle="${escapeHtml(source.id)}" data-enabled="${source.enabled}">${source.enabled ? "停用" : "启用"}</button><button class="small-button danger" data-source-delete="${escapeHtml(source.id)}">删除</button></div></div>`).join("");
  host.querySelectorAll("[data-source-edit]").forEach((button) => button.addEventListener("click", () => editSource(button.dataset.sourceEdit)));
  host.querySelectorAll("[data-source-test]").forEach((button) => button.addEventListener("click", () => testSavedSource(button.dataset.sourceTest, button)));
  host.querySelectorAll("[data-source-toggle]").forEach((button) => button.addEventListener("click", () => toggleSource(button.dataset.sourceToggle, button.dataset.enabled === "true")));
  host.querySelectorAll("[data-source-delete]").forEach((button) => button.addEventListener("click", () => deleteSource(button.dataset.sourceDelete)));
  updateGettingStarted();
}
async function loadSources() {
  const host = $("#source-list"); host.innerHTML = '<div class="loading">正在读取数据源…</div>';
  try { const result = await api("/api/sources"); state.sources = result.items || []; renderSources(); await loadCollectionStatus(); }
  catch (error) { host.innerHTML = `<div class="empty-inline">读取数据源失败：${escapeHtml(error.message)}<br>请确认 DataRadar API 已启动。</div>`; $("#source-meta").textContent = "连接失败"; $("#source-count").textContent = "!"; updateGettingStarted(); }
}
function sourcePayload() {
  const id = $("#source-id").value.trim();
  return { ...(id ? { id } : {}), name: $("#source-name").value.trim(), url: $("#source-url").value.trim(), max_age_days: Number($("#source-age").value || 0), enabled: state.editingSource ? Boolean(state.editingSource.enabled) : true };
}
function resetSourceForm() {
  state.editingSource = null;
  $("#source-form").reset();
  $("#source-age").value = "3";
  $("#source-id").disabled = false;
  $("#source-form-title").textContent = "添加 RSS 源";
  $("#source-form-help").textContent = "只需要填写名称和 RSS 地址，不必编辑 YAML";
  $("#save-source").textContent = "保存并启用";
  $("#cancel-source-edit").classList.add("hidden");
  showSourceTestResult("");
}
function editSource(sourceId) {
  const source = state.sources.find((item) => item.id === sourceId);
  if (!source || source.kind !== "rss") return;
  state.editingSource = source;
  $("#source-id").value = source.id;
  $("#source-id").disabled = true;
  $("#source-name").value = source.name || "";
  $("#source-url").value = source.url || "";
  $("#source-age").value = String(source.max_age_days ?? 3);
  $("#source-form-title").textContent = "编辑 RSS 源";
  $("#source-form-help").textContent = "修改后会立即用于下一次采集，源 ID 保持不变。";
  $("#save-source").textContent = "保存修改";
  $("#cancel-source-edit").classList.remove("hidden");
  $("#source-url").focus();
}
function showSourceTestResult(message, success = false) { const node = $("#source-test-result"); node.textContent = message; node.className = `form-result ${success ? "success" : "error"}`; }
async function testNewSource() {
  const button = $("#test-source"); button.disabled = true; showSourceTestResult("正在读取 RSS…");
  try { const result = await api("/api/sources/rss/test", { method: "POST", body: JSON.stringify(sourcePayload()) }); showSourceTestResult(`测试成功：读取到 ${Number(result.item_count || 0)} 条内容。`, true); toast("RSS 地址可以使用"); }
  catch (error) { showSourceTestResult(`测试失败：${error.message}`); }
  finally { button.disabled = false; }
}
async function saveSource(event) {
  event.preventDefault(); const button = $("#source-form button[type=submit]"); button.disabled = true;
  try {
    const payload = sourcePayload();
    if (state.editingSource) {
      delete payload.id;
      await api(`/api/sources/rss/${encodeURIComponent(state.editingSource.id)}`, { method: "PUT", body: JSON.stringify(payload) });
      toast("数据源修改已保存");
    } else {
      await api("/api/sources/rss", { method: "POST", body: JSON.stringify(payload) });
      toast("数据源已保存并启用");
    }
    resetSourceForm();
    await loadSources();
  }
  catch (error) { showSourceTestResult(`保存失败：${error.message}`); }
  finally { button.disabled = false; }
}
async function testSavedSource(sourceId, button) {
  button.disabled = true; button.textContent = "测试中…";
  try { const result = await api(`/api/sources/${encodeURIComponent(sourceId)}/test`, { method: "POST" }); if (!result.success) throw new Error(result.error || "测试失败"); toast(`测试成功：读取到 ${Number(result.item_count || 0)} 条内容`); }
  catch (error) { toast(`测试失败：${error.message}`); }
  finally { button.disabled = false; button.textContent = "测试"; }
}
async function toggleSource(sourceId, enabled) {
  try { await api(`/api/sources/${encodeURIComponent(sourceId)}/${enabled ? "disable" : "enable"}`, { method: "POST" }); toast(enabled ? "数据源已停用" : "数据源已启用"); await loadSources(); }
  catch (error) { toast(error.message); }
}
async function deleteSource(sourceId) {
  if (!window.confirm(`确定删除数据源“${sourceId}”吗？`)) return;
  try { await api(`/api/sources/${encodeURIComponent(sourceId)}`, { method: "DELETE" }); toast("数据源已删除"); await loadSources(); }
  catch (error) { toast(error.message); }
}
function collectionLabel(status) { return ({ idle: "尚未运行采集", running: "采集进行中…", completed: "最近一次采集已完成", failed: "最近一次采集失败" })[status] || status; }
async function loadCollectionStatus() {
  try { const result = await api("/api/collect/status"); const panel = $("#collection-status-panel"); panel.classList.remove("hidden"); $("#collection-status-text").textContent = `${collectionLabel(result.status)}${result.error ? `：${result.error}` : ""}`; if (result.status === "running" && !state.collectionPoll) { state.collectionPoll = window.setInterval(async () => { try { const next = await api("/api/collect/status"); $("#collection-status-text").textContent = `${collectionLabel(next.status)}${next.error ? `：${next.error}` : ""}`; if (next.status !== "running") { window.clearInterval(state.collectionPoll); state.collectionPoll = null; await loadMaterials(); } } catch { /* retain last state */ } }, 2000); } }
  catch { /* DataRadar unavailable is already shown by loadSources */ }
}
async function collectNow() {
  const button = $("#collect-now"); button.disabled = true;
  try { await api("/api/collect", { method: "POST" }); toast("采集任务已启动"); await loadCollectionStatus(); }
  catch (error) { toast(error.message); }
  finally { button.disabled = false; }
}
async function selectMaterial(id) {
  const basic = state.materials.find((item) => Number(item.id) === id); if (!basic) return;
  state.selectedMaterial = basic; renderMaterials();
  const panel = $("#material-detail"); panel.innerHTML = '<div class="loading">正在读取素材详情…</div>';
  try {
    const detail = await api(`/api/materials/${id}`); state.selectedMaterial = detail;
    const personaOptions = state.personas.map((persona) => `<option value="${escapeHtml(persona.id)}">${escapeHtml(persona.name)} · ${escapeHtml(persona.description || persona.id)}</option>`).join("");
    const safeUrl = /^https?:\/\//i.test(detail.source_url || "") ? detail.source_url : "";
    panel.innerHTML = `<div class="detail-top"><span>素材详情</span><span>·</span><span>${escapeHtml(detail.source_platform || "未知来源")}</span><span>·</span><span>${niceDate(detail.published_at)}</span></div><h2 class="detail-title">${escapeHtml(detail.title)}</h2><div class="chips"><span class="tag">${escapeHtml(detail.category || "未分类")}</span>${(detail.tags || []).slice(0, 6).map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join("")}<span class="tag score">重要性 ${Number(detail.importance_score || 0).toFixed(1)}</span></div><div class="detail-summary">${escapeHtml(detail.ai_summary || detail.summary || "这条素材暂时没有摘要。")}</div><div class="source-box"><label>原始来源</label>${safeUrl ? `<a href="${escapeHtml(safeUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(safeUrl)} ↗</a>` : '<span class="item-meta">未提供有效来源链接</span>'}${detail.full_text ? `<div class="full-text">${escapeHtml(detail.full_text)}</div>` : ""}</div><div class="generate-row"><select class="select" id="persona-select" aria-label="选择写作 persona">${personaOptions || '<option value="">没有可用 persona</option>'}</select><button class="button primary" id="generate-button" ${state.personas.length ? "" : "disabled"}>生成审核草稿　→</button></div>`;
    $("#generate-button")?.addEventListener("click", generateDraft);
  } catch (error) { panel.innerHTML = `<div class="empty-state"><h3>读取素材失败</h3><p>${escapeHtml(error.message)}</p></div>`; }
}
async function generateDraft() {
  const button = $("#generate-button"); const personaId = $("#persona-select")?.value;
  if (!state.selectedMaterial || !personaId) return;
  button.disabled = true; button.textContent = "正在生成草稿…";
  try { await api("/api/drafts/generate", { method: "POST", body: JSON.stringify({ material_id: Number(state.selectedMaterial.id), persona_id: personaId }) }); toast("草稿已生成，进入待审核列表"); await loadDraftCount(); setView("drafts"); }
  catch (error) { toast(error.message); button.disabled = false; button.textContent = "生成审核草稿　→"; }
}
async function loadDraftCount() { try { const result = await api("/api/drafts?status=all&limit=300"); state.draftCount = result.items.length; $("#draft-count").textContent = state.draftCount; } catch { /* keep the last visible count */ } updateGettingStarted(); }
async function loadDrafts() {
  const host = $("#draft-list"); host.innerHTML = '<div class="loading">正在读取本地草稿…</div>';
  try { const filter = $("#status-filter").value; const result = await api(`/api/drafts?status=${encodeURIComponent(filter)}&limit=200`); state.drafts = result.items || []; $("#draft-count").textContent = (await api("/api/drafts?status=all&limit=300")).items.length; renderDrafts(); }
  catch (error) { host.innerHTML = `<div class="empty-inline">读取失败：${escapeHtml(error.message)}</div>`; }
}
function statusLabel(status) { return ({ pending_review: "待审核", approved: "已批准", archived: "已归档" })[status] || status; }
function renderDrafts() {
  const host = $("#draft-list"); $("#draft-meta").textContent = `${state.drafts.length} 篇 · 本地 SQLite`;
  if (!state.drafts.length) { host.innerHTML = '<div class="empty-inline">这里还没有草稿。<br>先去素材库挑选一条内容开始。</div>'; $("#draft-detail").innerHTML = '<div class="empty-state"><div class="empty-icon">▤</div><h3>选择一篇草稿</h3><p>生成后的草稿会出现在这里。</p></div>'; return; }
  host.innerHTML = state.drafts.map((draft) => `<button class="draft-item ${state.selectedDraft?.id === draft.id ? "selected" : ""}" data-draft-id="${draft.id}"><span class="item-title">${escapeHtml(draft.title)}</span><span class="item-meta"><span>${escapeHtml(draft.persona_name)}</span><span>·</span><span>${niceDate(draft.updated_at)}</span><span class="draft-badge ${draft.status}">${statusLabel(draft.status)}</span></span></button>`).join("");
  host.querySelectorAll("[data-draft-id]").forEach((button) => button.addEventListener("click", () => selectDraft(Number(button.dataset.draftId))));
  if (state.selectedDraft && state.drafts.some((draft) => draft.id === state.selectedDraft.id)) selectDraft(state.selectedDraft.id);
  else selectDraft(state.drafts[0].id);
}
async function selectDraft(id) {
  try { state.selectedDraft = await api(`/api/drafts/${id}`); renderDraftDetail(); renderDraftsSelection(); }
  catch (error) { toast(error.message); }
}
function renderDraftsSelection() { document.querySelectorAll(".draft-item").forEach((node) => node.classList.toggle("selected", Number(node.dataset.draftId) === state.selectedDraft?.id)); }
function renderDraftDetail() {
  const d = state.selectedDraft; if (!d) return;
  const material = d.material || {}; const safeUrl = /^https?:\/\//i.test(material.source_url || "") ? material.source_url : "";
  const exportButton = d.status === "approved"
    ? '<button class="small-button export" id="export-draft">导出 .md</button>'
    : '<button class="small-button export" id="export-draft" disabled title="请先批准草稿">导出 .md</button>';
  $("#draft-detail").innerHTML = `<div class="editor-head"><div><h2>${escapeHtml(d.title)}</h2><div class="editor-meta"><span>${escapeHtml(d.persona_name)}</span><span>·</span><span>${escapeHtml(d.model_used || "未记录模型")}</span><span class="draft-badge ${d.status}">${statusLabel(d.status)}</span></div></div><div class="editor-actions"><button class="small-button" id="save-draft">保存修改</button>${d.status !== "approved" ? '<button class="small-button approve" id="approve-draft">批准</button>' : '<button class="small-button" id="unapprove-draft">退回待审核</button>'}<button class="small-button" id="archive-draft">归档</button>${exportButton}</div></div><div class="editor-body"><div class="editor-section"><label class="field-label" for="edit-title">标题</label><input id="edit-title" maxlength="500" value="${escapeHtml(d.title)}"></div><div class="editor-section"><label class="field-label" for="edit-body">正文 <span>Markdown</span></label><textarea id="edit-body" maxlength="200000">${escapeHtml(d.body)}</textarea></div><div class="source-compact"><b>素材来源：</b> ${escapeHtml(material.title || "未知素材")}　${safeUrl ? `<a href="${escapeHtml(safeUrl)}" target="_blank" rel="noopener noreferrer">查看原文 ↗</a>` : ""}<div class="detail-summary">${escapeHtml(material.ai_summary || material.summary || "")}</div></div><div id="revision-area" class="revision-list ${state.revisionsOpen ? "" : "hidden"}"></div></div><div class="editor-footer"><span>最近保存 ${niceDate(d.updated_at)} · ${d.status === "pending_review" ? "修改后请完成审核" : `当前状态：${statusLabel(d.status)}`}</span><span id="revision-toggle" class="revision-link">${state.revisionsOpen ? "收起修订" : "修订历史 ↗"}</span></div>`;
  $("#save-draft").addEventListener("click", () => saveDraft());
  $("#approve-draft")?.addEventListener("click", () => saveDraft("approved"));
  $("#unapprove-draft")?.addEventListener("click", () => saveDraft("pending_review"));
  $("#archive-draft").addEventListener("click", () => saveDraft("archived"));
  $("#export-draft").addEventListener("click", () => { window.location.href = `/api/drafts/${d.id}/export.md`; });
  $("#revision-toggle").addEventListener("click", async () => { state.revisionsOpen = !state.revisionsOpen; await renderDraftDetail(); if (state.revisionsOpen) loadRevisions(); });
  if (state.revisionsOpen) loadRevisions();
}
async function saveDraft(status) {
  const d = state.selectedDraft; if (!d) return;
  const button = $("#save-draft"); button.disabled = true;
  try { state.selectedDraft = await api(`/api/drafts/${d.id}`, { method: "PUT", body: JSON.stringify({ title: $("#edit-title").value.trim(), body: $("#edit-body").value, ...(status ? { status } : {}) }) }); toast(status ? `已${statusLabel(status)}` : "修改已保存并记录修订"); await loadDrafts(); }
  catch (error) { toast(error.message); button.disabled = false; }
}
async function loadRevisions() {
  const area = $("#revision-area"); if (!area || !state.selectedDraft) return;
  try { const result = await api(`/api/drafts/${state.selectedDraft.id}/revisions`); area.innerHTML = result.items.map((revision) => `<div class="revision-row"><span>修订 #${revision.id} · ${niceDate(revision.created_at)} · ${statusLabel(revision.status)}</span><button data-restore="${revision.id}">恢复此版本</button></div>`).join("") || "没有修订记录"; area.querySelectorAll("[data-restore]").forEach((button) => button.addEventListener("click", async () => { try { state.selectedDraft = await api(`/api/drafts/${state.selectedDraft.id}/restore`, { method: "POST", body: JSON.stringify({ revision_id: Number(button.dataset.restore) }) }); toast("已恢复版本，并创建新的修订记录"); await loadDrafts(); } catch (error) { toast(error.message); } })); }
  catch (error) { area.textContent = error.message; }
}
async function boot() {
  $("#today").textContent = new Date().toLocaleDateString("zh-CN", { year: "numeric", month: "long", day: "numeric" });
  document.querySelectorAll(".nav-item").forEach((button) => button.addEventListener("click", () => setView(button.dataset.view)));
  $("#toggle-view").addEventListener("click", () => setView(state.view === "materials" ? "drafts" : "materials"));
  $("#refresh").addEventListener("click", () => state.view === "materials" ? loadMaterials() : state.view === "drafts" ? loadDrafts() : loadSources());
  $("#load-more").addEventListener("click", loadMaterials); $("#refresh-drafts").addEventListener("click", loadDrafts); $("#refresh-sources").addEventListener("click", loadSources); $("#collect-now").addEventListener("click", collectNow); $("#test-source").addEventListener("click", testNewSource); $("#source-form").addEventListener("submit", saveSource); $("#cancel-source-edit").addEventListener("click", resetSourceForm); $("#setup-sources").addEventListener("click", () => setView("sources"));
  $("#status-filter").addEventListener("change", loadDrafts);
  document.querySelectorAll("[data-mode]").forEach((button) => button.addEventListener("click", () => { state.mode = button.dataset.mode; document.querySelectorAll("[data-mode]").forEach((item) => item.classList.toggle("selected", item === button)); loadMaterials(); }));
  $("#auth-form").addEventListener("submit", submitAuth);
  $("#auth-switch").addEventListener("click", () => setAuthMode($("#auth-submit").textContent.includes("登录")));
  $("#logout-button").addEventListener("click", async () => { try { await api("/api/auth/logout", { method: "POST" }); state.user = null; $("#logout-button").classList.add("hidden"); showAuthScreen(true); setAuthMode(false); } catch (error) { toast(error.message); } });
  let authRequired = false;
  try { authRequired = Boolean((await api("/api/health")).auth_required); } catch { /* API unavailable is shown by the data panels. */ }
  try { const me = await api("/api/auth/me"); if (me.authenticated) { state.user = me.user; $("#user-email").textContent = me.user?.email || ""; $("#logout-button").classList.remove("hidden"); } else if (authRequired) showAuthScreen(true); } catch { if (authRequired) showAuthScreen(true); }
  if (!authRequired || state.user) { try { state.personas = await api("/api/personas"); } catch (error) { toast(`读取 persona 失败：${error.message}`); } await Promise.all([loadMaterials(), loadDraftCount(), loadSources()]); updateGettingStarted(); }
}
boot();
