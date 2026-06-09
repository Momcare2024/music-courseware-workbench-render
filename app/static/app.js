let currentProject = null;
let statusTimer = null;
let statusStartedAt = null;
let accessGateVisible = false;

const $ = (id) => document.getElementById(id);

function toast(message) {
  const node = $("toast");
  node.textContent = message;
  node.classList.remove("hidden");
  setTimeout(() => node.classList.add("hidden"), 3600);
}

function configMessage(message, kind = "") {
  const node = $("config-status");
  node.classList.remove("success", "error");
  if (kind) node.classList.add(kind);
  node.innerHTML = message;
}

function setConfigBusy(isBusy, activeText = "") {
  const saveButton = document.querySelector('#config-form button[type="submit"]');
  const testButton = $("test-jimeng");
  if (saveButton) {
    saveButton.disabled = isBusy;
    saveButton.textContent = isBusy && activeText === "save" ? "正在保存..." : "保存 API 设置";
  }
  if (testButton) {
    testButton.disabled = isBusy;
    testButton.textContent = isBusy && activeText === "test" ? "正在测试..." : "测试即梦连接";
  }
}

async function api(path, options = {}) {
  const timeoutMs = options.timeoutMs || 0;
  delete options.timeoutMs;
  let timer = null;
  if (timeoutMs) {
    const controller = new AbortController();
    options.signal = controller.signal;
    timer = setTimeout(() => controller.abort(), timeoutMs);
  }
  try {
    const response = await fetch(path, options);
    if (!response.ok) {
      const text = await response.text();
      if (response.status === 401) {
        showAccessGate("请先输入访问码。");
      }
      throw new Error(text || response.statusText);
    }
    return response.json();
  } finally {
    if (timer) clearTimeout(timer);
  }
}

function showAccessGate(message = "") {
  const gate = $("access-gate");
  const messageNode = $("access-message");
  accessGateVisible = true;
  if (messageNode && message) messageNode.textContent = message;
  if (gate) gate.classList.remove("hidden");
}

function hideAccessGate() {
  const gate = $("access-gate");
  accessGateVisible = false;
  if (gate) gate.classList.add("hidden");
}

async function submitAccess(event) {
  event.preventDefault();
  const formData = new FormData(event.currentTarget);
  const button = event.currentTarget.querySelector("button");
  if (button) {
    button.disabled = true;
    button.textContent = "正在验证...";
  }
  try {
    await api("/api/access", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(Object.fromEntries(formData.entries())),
      timeoutMs: 15000,
    });
    hideAccessGate();
    await loadConfig();
    await loadProjects();
    toast("已进入工作台。");
  } catch (error) {
    showAccessGate("访问码不正确，请重新输入。");
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = "进入工作台";
    }
  }
}

function startStatus(title, detail) {
  const box = $("job-status");
  box.classList.remove("hidden", "success", "error");
  $("job-status-title").textContent = title;
  statusStartedAt = Date.now();
  if (statusTimer) clearInterval(statusTimer);
  const update = () => {
    const seconds = Math.floor((Date.now() - statusStartedAt) / 1000);
    $("job-status-detail").textContent = `${detail}｜已等待 ${seconds} 秒`;
  };
  update();
  statusTimer = setInterval(update, 1000);
}

function finishStatus(title, detail, kind = "success") {
  if (statusTimer) clearInterval(statusTimer);
  statusTimer = null;
  const box = $("job-status");
  box.classList.remove("hidden", "success", "error");
  box.classList.add(kind);
  $("job-status-title").textContent = title;
  $("job-status-detail").textContent = detail;
}

function setButtonsBusy(isBusy) {
  document.querySelectorAll("button").forEach((button) => {
    if (isBusy) {
      if (!button.disabled) button.dataset.wasEnabledBeforeBusy = "1";
      button.disabled = true;
      return;
    }
    if (button.dataset.wasEnabledBeforeBusy === "1" || button.dataset.enabled === "1") {
      button.disabled = false;
    }
    delete button.dataset.wasEnabledBeforeBusy;
  });
}

async function loadConfig() {
  const config = await api("/api/config");
  configMessage([
    `方舟即梦：${config.ark_configured ? "已配置" : "未配置"}`,
    `Base URL：${config.ark_base_url || "未设置"}`,
    `图片模型：${config.ark_image_model || "未设置"}`,
  ].join("<br />"));
  $("ark-api-key").placeholder = config.ark_configured ? "已保存，留空则不修改；复制 API Key 列的 ark-..." : "复制 API Key 列的 ark-...，不要复制资源 ID";
  $("ark-base-url").value = config.ark_base_url || "https://ark.cn-beijing.volces.com/api/v3";
  $("ark-image-model").value = config.ark_image_model || "doubao-seedream-4-0-250828";
  if (config.web_config_enabled === false) {
    configMessage([
      `方舟即梦：${config.ark_configured ? "已通过云端环境变量配置" : "未配置"}`,
      `Base URL：${config.ark_base_url || "未设置"}`,
      `图片模型：${config.ark_image_model || "未设置"}`,
      "云端版本不在网页保存 API Key，请到 Render 环境变量中修改。",
    ].join("<br />"));
    document.querySelectorAll("#config-form input, #config-form button").forEach((node) => {
      node.disabled = true;
    });
  }
}

async function saveConfig(event) {
  if (event) event.preventDefault();
  setConfigBusy(true, "save");
  configMessage("正在保存 API 设置...");
  const formData = new FormData($("config-form"));
  try {
    await api("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(Object.fromEntries(formData.entries())),
    });
    $("ark-api-key").value = "";
    await loadConfig();
    configMessage("即梦 API 设置已保存。可以点击“测试即梦连接”。", "success");
    toast("即梦 API 设置已保存。");
  } catch (error) {
    configMessage(`保存失败：${error.message}`, "error");
    throw error;
  } finally {
    setConfigBusy(false);
  }
}

async function testJimeng() {
  try {
    await saveConfig();
    setConfigBusy(true, "test");
    configMessage("正在测试即梦 API，可能需要 10-30 秒...");
    toast("正在测试即梦 API...");
    const result = await api("/api/config/jimeng/test", { method: "POST", timeoutMs: 45000 });
    configMessage(result.message || (result.ok ? "即梦 API 可用。" : "即梦 API 测试失败。"), result.ok ? "success" : "error");
    toast(result.message || (result.ok ? "即梦 API 可用。" : "即梦 API 测试失败。"));
  } catch (error) {
    configMessage(`测试失败：${error.message}`, "error");
    toast(`测试失败：${error.message}`);
  } finally {
    setConfigBusy(false);
  }
}

function projectSummary(project) {
  const pages = project.pages || [];
  const done = pages.filter((page) => page.image_status === "done").length;
  const remaining = Math.max((pages.length || 0) - done, 0);
  return `${pages.length || 0} 页｜已生成 ${done} 页｜剩余 ${remaining} 页`;
}

async function loadProjects() {
  const projects = await api("/api/projects");
  const list = $("project-list");
  list.innerHTML = "";
  const imageProjects = projects.filter((project) => project.workflow === "image_pptx");
  if (!imageProjects.length) {
    list.innerHTML = `<p class="muted">暂无图片版 PPT 项目。</p>`;
    return;
  }
  for (const project of imageProjects) {
    const card = document.createElement("div");
    card.className = "project-card";
    card.innerHTML = `
      <strong>${project.title}</strong>
      <span class="muted">${project.updated_at || project.created_at || ""}</span><br />
      <span class="muted">${projectSummary(project)}</span>
    `;
    card.addEventListener("click", async () => renderProject(await api(`/api/projects/${project.id}`)));
    list.appendChild(card);
  }
  if (!currentProject && imageProjects.length) {
    renderProject(await api(`/api/projects/${imageProjects[0].id}`));
  }
}

async function createProject(event) {
  event.preventDefault();
  const formData = new FormData(event.currentTarget);
  const payload = Object.fromEntries(formData.entries());
  startStatus("正在创建项目", "正在按第几页拆分你的页面设计稿");
  try {
    const project = await api("/api/image-projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      timeoutMs: 30000,
    });
    renderProject(project);
    await loadProjects();
    finishStatus("项目已创建", "页面已经拆分，可以逐页检查提示词并生成画面。");
  } catch (error) {
    finishStatus("创建失败", error.message, "error");
  }
}

function renderProject(project) {
  currentProject = project;
  const hasProject = Boolean(project);
  $("current-project").textContent = hasProject ? `${project.title}｜${projectSummary(project)}` : "尚未选择任务";
  $("save-pages").disabled = !hasProject;
  $("reparse-pages").disabled = !hasProject;
  $("generate-all").disabled = !hasProject;
  $("export-pptx").disabled = !hasProject;
  $("export-wps-upload").disabled = !hasProject;
  $("save-pages").dataset.enabled = hasProject ? "1" : "0";
  $("reparse-pages").dataset.enabled = hasProject ? "1" : "0";
  $("generate-all").dataset.enabled = hasProject ? "1" : "0";
  $("export-pptx").dataset.enabled = hasProject ? "1" : "0";
  $("export-wps-upload").dataset.enabled = hasProject ? "1" : "0";
  updateDownloads(project);
  renderPages(project);
}

function updateDownloads(project) {
  const mappings = [
    ["download-page-design", "page_design"],
    ["download-pages-json", "pages_json"],
    ["download-pptx", "pptx"],
    ["download-wps-pdf", "wps_upload_pdf"],
    ["download-image-zip", "image_zip"],
    ["download-zip", "zip"],
  ];
  for (const [id, artifact] of mappings) {
    const link = $(id);
    if (!project || !project.artifacts?.[artifact]) {
      link.classList.add("disabled");
      link.removeAttribute("href");
      continue;
    }
    link.href = `/api/projects/${project.id}/download/${artifact}`;
    link.classList.remove("disabled");
  }
}

function renderPages(project) {
  const list = $("page-list");
  list.innerHTML = "";
  if (!project || !(project.pages || []).length) {
    list.className = "page-list empty-state";
    list.textContent = "创建项目后，每页设计会显示在这里。";
    return;
  }
  list.className = "page-list";
  for (const page of project.pages) {
    const card = document.createElement("article");
    card.className = "page-card";
    const imageHtml = page.image_file
      ? `<img class="page-image" src="/api/projects/${project.id}/images/${page.image_file}?v=${encodeURIComponent(project.updated_at || "")}" alt="第${page.index}页画面" />`
      : `<div class="image-placeholder">尚未生成</div>`;
    card.innerHTML = `
      <div class="page-card-head">
        <strong>第 ${page.index} 页</strong>
        <span class="badge ${page.image_status || "not_started"}">${statusText(page.image_status)}</span>
      </div>
      <label>
        页面标题
        <input data-field="title" data-index="${page.index}" value="${escapeAttr(page.title || "")}" />
      </label>
      <label>
        完整页面设计稿
        <textarea data-field="raw_design" data-index="${page.index}" rows="6">${escapeHtml(page.raw_design || "")}</textarea>
      </label>
      <label>
        发给即梦的提示词
        <textarea data-field="prompt" data-index="${page.index}" rows="7">${escapeHtml(page.prompt || "")}</textarea>
      </label>
      <div class="page-preview">
        ${imageHtml}
      </div>
      ${page.error ? `<p class="error-text">失败原因：${escapeHtml(page.error)}</p>` : ""}
      <div class="button-row">
        <button type="button" data-action="generate" data-index="${page.index}">生成/重生成这一页</button>
      </div>
    `;
    card.querySelector('[data-action="generate"]').addEventListener("click", () => generatePage(page.index));
    list.appendChild(card);
  }
}

function statusText(status) {
  return {
    not_started: "未生成",
    generating: "生成中",
    done: "已完成",
    error: "失败",
  }[status || "not_started"] || status;
}

function collectPages() {
  const pages = JSON.parse(JSON.stringify(currentProject.pages || []));
  for (const page of pages) {
    for (const field of ["title", "raw_design", "prompt"]) {
      const el = document.querySelector(`[data-field="${field}"][data-index="${page.index}"]`);
      if (el) page[field] = el.value;
    }
  }
  return pages;
}

async function savePages() {
  if (!currentProject) return null;
  const project = await api(`/api/projects/${currentProject.id}/image-pages`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pages: collectPages() }),
    timeoutMs: 30000,
  });
  renderProject(project);
  await loadProjects();
  toast("页面设计已保存。");
  return project;
}

async function reparsePages() {
  if (!currentProject) return;
  startStatus("正在重新拆分页", "系统会按第1页或 P1/P2 标记重新识别页面");
  try {
    const project = await api(`/api/projects/${currentProject.id}/image-pages/reparse`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        design_text: currentProject.design_text || "",
        global_style: currentProject.global_style || "",
      }),
      timeoutMs: 30000,
    });
    renderProject(project);
    await loadProjects();
    finishStatus("已重新拆分页", `现在共 ${project.pages?.length || 0} 页。`);
  } catch (error) {
    finishStatus("重新拆分页失败", error.message, "error");
  }
}

async function generatePage(index) {
  if (!currentProject) return;
  setButtonsBusy(true);
  startStatus(`正在生成第 ${index} 页`, "即梦生成可能需要几十秒到数分钟");
  try {
    await savePages();
    const project = await api(`/api/projects/${currentProject.id}/image-pages/${index}/generate`, {
      method: "POST",
      timeoutMs: 300000,
    });
    renderProject(project);
    await loadProjects();
    const page = (project.pages || []).find((item) => item.index === index);
    if (page?.image_status === "done") {
      finishStatus(`第 ${index} 页已生成`, "图片已保存，可以继续生成其他页面。");
    } else {
      finishStatus(`第 ${index} 页生成失败`, page?.error || "请查看页面失败原因。", "error");
    }
  } catch (error) {
    finishStatus("生成失败", error.message, "error");
  } finally {
    setButtonsBusy(false);
    renderProject(currentProject);
  }
}

async function generateAll() {
  if (!currentProject) return;
  setButtonsBusy(true);
  const beforeDone = (currentProject.pages || []).filter((page) => page.image_status === "done").length;
  const beforeRemaining = Math.max((currentProject.pages || []).length - beforeDone, 0);
  startStatus("正在生成剩余全部页面", `会跳过已经完成的页面；本次预计生成 ${beforeRemaining} 页`);
  try {
    await savePages();
    const project = await api(`/api/projects/${currentProject.id}/image-pages/generate-all`, {
      method: "POST",
      timeoutMs: 900000,
    });
    renderProject(project);
    await loadProjects();
    const done = (project.pages || []).filter((page) => page.image_status === "done").length;
    const failed = (project.pages || []).filter((page) => page.image_status === "error").length;
    finishStatus("剩余页面生成结束", `${projectSummary(project)}${failed ? `｜失败 ${failed} 页，可单独重生成` : ""}`);
  } catch (error) {
    finishStatus("生成剩余页面失败", error.message, "error");
  } finally {
    setButtonsBusy(false);
    renderProject(currentProject);
  }
}

async function exportPptx() {
  if (!currentProject) return;
  setButtonsBusy(true);
  startStatus("正在导出 PPTX", "正在把已生成图片铺满每张幻灯片");
  try {
    await savePages();
    const project = await api(`/api/projects/${currentProject.id}/export-pptx`, {
      method: "POST",
      timeoutMs: 60000,
    });
    renderProject(project);
    await loadProjects();
    finishStatus("PPTX 已导出", "可以点击下载图片版 PPTX，用 WPS 打开。");
  } catch (error) {
    finishStatus("导出失败", error.message, "error");
  } finally {
    setButtonsBusy(false);
    renderProject(currentProject);
  }
}

async function exportWpsUpload() {
  if (!currentProject) return;
  setButtonsBusy(true);
  startStatus("正在导出WPS上传文件", "正在把已生成页面整理成 PDF 和 JPG 图片包");
  try {
    await savePages();
    const project = await api(`/api/projects/${currentProject.id}/export-wps-upload`, {
      method: "POST",
      timeoutMs: 60000,
    });
    renderProject(project);
    await loadProjects();
    const info = project.wps_upload_export || {};
    const missing = info.missing_pages?.length ? `｜未生成页：${info.missing_pages.join("、")}` : "";
    finishStatus(
      "WPS上传文件已导出",
      `已整理 ${info.image_count || 0} 张页面图。优先下载 PDF 上传 WPS AIPPT；ZIP 解压后可多选图片上传。${missing}`,
    );
  } catch (error) {
    finishStatus("导出失败", error.message, "error");
  } finally {
    setButtonsBusy(false);
    renderProject(currentProject);
  }
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[char]));
}

function escapeAttr(value) {
  return escapeHtml(value).replace(/\n/g, " ");
}

window.addEventListener("DOMContentLoaded", async () => {
  $("access-form").addEventListener("submit", submitAccess);
  $("config-form").addEventListener("submit", saveConfig);
  $("test-jimeng").addEventListener("click", testJimeng);
  $("create-form").addEventListener("submit", createProject);
  $("save-pages").addEventListener("click", savePages);
  $("reparse-pages").addEventListener("click", reparsePages);
  $("generate-all").addEventListener("click", generateAll);
  $("export-pptx").addEventListener("click", exportPptx);
  $("export-wps-upload").addEventListener("click", exportWpsUpload);

  try {
    await loadConfig();
    await loadProjects();
  } catch (error) {
    if (!accessGateVisible) {
      toast(`加载失败：${error.message}`);
    }
  }
});
