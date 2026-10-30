const state = { view: "materials", mode: "trending", materials: [], personas: [], selectedMaterial: null, drafts: [], selectedDraft: null, revisionsOpen: false };
const $ = (selector) => document.querySelector(selector);
const escapeHtml = (value = "") => String(value).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
const niceDate = (value) => { if (!value) return "时间未知"; const date = new Date(value); return Number.isNaN(date.getTime()) ? String(value).slice(0, 10) : date.toLocaleDateString("zh-CN", { month: "short", day: "numeric" }); };
const toast = (message) => { const node = $("#toast"); node.textContent = message; node.classList.add("show"); clearTimeout(toast.timer); toast.timer = setTimeout(() => node.classList.remove("show"), 2600); };
async function api(path, options = {}) { const response = await fetch(path, { ...options, headers: { ...(options.body ? { "Content-Type": "application/json" } : {}), ...options.headers } }); let data; try { data = await response.json(); } catch { data = await response.text(); } if (!response.ok) throw new Error(data?.detail || data || `请求失败 (${response.status})`); return data; }
function setView(view) {
  state.view = view;
  $("#materials-view").classList.toggle("hidden", view !== "materials"); $("#drafts-view").classList.toggle("hidden", view !== "drafts");
  document.querySelectorAll(".nav-item").forEach((button) => button.classList.toggle("active", button.dataset.view === view));
  $("#crumb").textContent = view === "materials" ? "素材发现" : "内容草稿";
  $("#page-title").textContent = view === "materials" ? "发现值得写的内容" : "管理内容草稿";
  $("#page-subtitle").textContent = view === "materials" ? "从行业素材开始，生成可审核、可追溯的内容草稿。" : "编辑、审核并保留每次修订，批准后导出 Markdown。";
  $("#toggle-view").innerHTML = view === "materials" ? '查看草稿 <span>→</span>' : '回到素材 <span>→</span>';
  if (view === "drafts") loadDrafts();
}
function renderMaterials() {
  const host = $("#material-list"); $("#material-count").textContent = state.materials.length;
  $("#material-meta").textContent = `${state.materials.length} 条素材 · ${state.mode === "trending" ? "热门" : "最新"}`;
  if (!state.materials.length) { host.innerHTML = '<div class="empty-inline">暂时没有素材。请确认 DataRadar 已启动并完成采集。</div>'; return; }
  host.innerHTML = state.materials.map((item) => `<button class="material-item ${state.selectedMaterial?.id === item.id ? "selected" : ""}" data-material-id="${Number(item.id)}"><span class="item-title">${escapeHtml(item.title || "未命名素材")}</span><span class="item-meta"><span>${escapeHtml(item.source_platform || "未知来源")}</span><span>·</span><span>${niceDate(item.published_at)}</span><span class="tag">${escapeHtml(item.category || "未分类")}</span><span class="score">重要性 ${Number(item.importance_score || 0).toFixed(1)}</span></span></button>`).join("");
  host.querySelectorAll("[data-material-id]").forEach((button) => button.addEventListener("click", () => selectMaterial(Number(button.dataset.materialId))));
}
async function loadMaterials() {
  const host = $("#material-list"); host.innerHTML = '<div class="loading">正在连接 DataRadar…</div>';
  try { const result = await api(`/api/materials?mode=${state.mode}&limit=40`); state.materials = result.items || []; renderMaterials(); if (state.selectedMaterial) await selectMaterial(state.selectedMaterial.id); }
  catch (error) { host.innerHTML = `<div class="empty-inline">${escapeHtml(error.message)}<br>启动 DataRadar API 后可加载素材。</div>`; $("#material-meta").textContent = "连接失败"; }
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
async function loadDraftCount() { try { const result = await api("/api/drafts?status=all&limit=300"); $("#draft-count").textContent = result.items.length; } catch { /* keep the last visible count */ } }
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
  $("#refresh").addEventListener("click", () => state.view === "materials" ? loadMaterials() : loadDrafts());
  $("#load-more").addEventListener("click", loadMaterials); $("#refresh-drafts").addEventListener("click", loadDrafts);
  $("#status-filter").addEventListener("change", loadDrafts);
  document.querySelectorAll("[data-mode]").forEach((button) => button.addEventListener("click", () => { state.mode = button.dataset.mode; document.querySelectorAll("[data-mode]").forEach((item) => item.classList.toggle("selected", item === button)); loadMaterials(); }));
  try { state.personas = await api("/api/personas"); } catch (error) { toast(`读取 persona 失败：${error.message}`); }
  await Promise.all([loadMaterials(), loadDraftCount()]);
}
boot();
