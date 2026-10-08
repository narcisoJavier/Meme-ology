(() => {
  const state = { catalog: [], popular: [], offset: 0, query: "", limit: 12 };
  const $ = (selector) => document.querySelector(selector);

  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
  }[char]));

  const sourceName = (item) => {
    const source = String(item?.source_platform || item?.source || "source").toLowerCase();
    return source === "knowyourmeme" ? "Know Your Meme" : source;
  };

  const dateLabel = (timestamp) => {
    if (!timestamp || Number(timestamp) <= 0) return "Date not supplied by source";
    const date = new Date(Number(timestamp) * 1000);
    if (Number.isNaN(date.getTime())) return "Date not supplied by source";
    return new Intl.DateTimeFormat(undefined, { year: "numeric", month: "short", day: "numeric" }).format(date);
  };

  const freshnessLabel = (item) => {
    if (String(item?.data_origin || "") !== "live") return "offline catalog snapshot";
    if (!item?.observed_at) return "retrieval time not supplied";
    return `retrieved ${dateLabel(item.observed_at)}`;
  };

  const mediaUrl = (item) => item?.media_url || item?.url || "";

  const imageBlock = (item, className) => {
    const url = mediaUrl(item);
    if (!url) return `<div class="state-block" data-state="empty">Image unavailable</div>`;
    return `<div class="${className}"><img src="${escapeHtml(url)}" alt="Example image for ${escapeHtml(item.title)}" loading="lazy"></div>`;
  };

  const caption = (item) => `<p class="entry-caption"><span>${escapeHtml(sourceName(item))}</span><span>documented ${escapeHtml(dateLabel(item.created_at))}</span><span>${escapeHtml(freshnessLabel(item))}</span></p>`;
  const detailUrl = (item) => `/meme/${encodeURIComponent(item.id)}`;
  const itemLink = (item) => `<a href="${detailUrl(item)}">${escapeHtml(item.title || "Untitled entry")}</a>`;

  const stateMessage = (kind, text) => `<div class="state-block" data-state="${kind}">${escapeHtml(text)}</div>`;

  async function getJson(url) {
    const response = await fetch(url, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`Request failed with ${response.status}`);
    return response.json();
  }

  function bindImageFallbacks() {
    document.querySelectorAll("img").forEach((image) => {
      image.addEventListener("error", () => {
        const wrapper = image.parentElement;
        if (wrapper) wrapper.innerHTML = '<div class="state-block" data-state="empty">Image unavailable</div>';
      }, { once: true });
    });
  }

  function renderFeature(item) {
    const target = $("#featureEntry");
    if (!item) {
      target.innerHTML = `<p class="eyebrow">Featured from the KYM catalog</p>${stateMessage("empty", "No catalog entry is available right now.")}`;
      return;
    }
    target.innerHTML = `<p class="eyebrow">Featured from the KYM catalog</p><h2>${itemLink(item)}</h2>${imageBlock(item, "feature-image-wrap")}${caption(item)}<p class="feature-description">This is the first eligible entry returned by the Know Your Meme catalog collection. The collection order is source-backed and is not a claim about worldwide momentum.</p>`;
    bindImageFallbacks();
  }

  function renderPopular(items) {
    const target = $("#popularList");
    if (!items?.length) {
      target.innerHTML = stateMessage("empty", "No observed KYM popularity records are available in this response.");
      return;
    }
    target.innerHTML = items.map((item, index) => `<article class="compact-entry"><span class="compact-entry-number">${String(index + 1).padStart(2, "0")}</span><div><h3>${itemLink(item)}</h3><p>${escapeHtml(sourceName(item))} · ${escapeHtml(freshnessLabel(item))}</p></div></article>`).join("");
  }

  function renderArchive(items, append = false) {
    const target = $("#archiveList");
    if (!items?.length && !append) {
      target.innerHTML = stateMessage("empty", state.query ? "No catalog entries match that search." : "No catalog entries are available right now.");
      return;
    }
    const html = items.map((item) => `<article class="archive-entry"><a class="archive-thumb" href="${detailUrl(item)}" aria-label="Open ${escapeHtml(item.title)}">${mediaUrl(item) ? `<img src="${escapeHtml(mediaUrl(item))}" alt="" loading="lazy">` : "<span>Image unavailable</span>"}</a><div><h3>${itemLink(item)}</h3><p>${escapeHtml(item.source_community || sourceName(item))} · ${escapeHtml(freshnessLabel(item))}</p></div><time class="archive-date" datetime="${item.created_at ? new Date(item.created_at * 1000).toISOString() : ""}">${escapeHtml(dateLabel(item.created_at))}</time></article>`).join("");
    target.innerHTML = append ? target.innerHTML + html : html;
    bindImageFallbacks();
  }

  function updateFreshness(items) {
    const banner = $("#freshnessBanner");
    const hasSnapshot = items.some((item) => String(item?.data_origin || "") !== "live");
    if (hasSnapshot) {
      banner.hidden = false;
      banner.textContent = "This view includes an offline catalog snapshot. The source date is shown on each entry; no current popularity claim is being made.";
    } else {
      banner.hidden = true;
    }
  }

  async function loadCollections() {
    try {
      const query = state.query ? `&q=${encodeURIComponent(state.query)}` : "";
      const [catalog, popular] = await Promise.all([
        getJson(`/api/v1/memes/catalog?limit=${state.limit}&offset=${state.offset}${query}`),
        getJson("/api/v1/memes/popular?limit=5")
      ]);
      state.catalog = catalog.items || [];
      state.popular = popular.items || [];
      renderFeature(state.catalog[0]);
      renderPopular(state.popular);
      renderArchive(state.catalog);
      $("#loadMore").hidden = !catalog.has_more;
      updateFreshness([...state.catalog, ...state.popular]);
      $("#archive-heading").textContent = state.query ? `Search results for “${state.query}”` : "Newly documented";
    } catch (error) {
      $("#featureEntry").innerHTML = `<p class="eyebrow">Featured from the KYM catalog</p>${stateMessage("error", "The collection could not be reached. Try again in a moment.")}`;
      $("#popularList").innerHTML = stateMessage("error", "Source status is unavailable.");
      $("#archiveList").innerHTML = stateMessage("error", "The catalog could not be loaded.");
      $("#loadMore").hidden = true;
    }
  }

  async function loadMore() {
    const button = $("#loadMore");
    button.disabled = true;
    button.textContent = "Loading...";
    try {
      const nextOffset = state.offset + state.limit;
      const query = state.query ? `&q=${encodeURIComponent(state.query)}` : "";
      const response = await getJson(`/api/v1/memes/catalog?limit=${state.limit}&offset=${nextOffset}${query}`);
      state.offset = nextOffset;
      state.catalog = state.catalog.concat(response.items || []);
      renderArchive(response.items || [], true);
      button.hidden = !response.has_more;
    } catch (error) {
      button.textContent = "Try again";
    } finally {
      button.disabled = false;
      if (!button.hidden) button.textContent = "Load more entries";
    }
  }

  async function renderDetail(id) {
    document.body.classList.add("detail-mode");
    const section = $("#detailSection");
    section.hidden = false;
    section.innerHTML = stateMessage("loading", "Loading source-backed entry...");
    try {
      const item = await getJson(`/api/v1/memes/${encodeURIComponent(id)}`);
      section.innerHTML = `<div class="detail-layout"><div><p class="eyebrow">${escapeHtml(sourceName(item))} entry</p><h2>${escapeHtml(item.title)}</h2>${imageBlock(item, "detail-media")}${caption(item)}<p class="feature-description">${escapeHtml(item.explanation || "No description was supplied by the collected source.")}</p><div class="detail-actions"><a class="button button-primary" href="${escapeHtml(item.permalink)}" target="_blank" rel="noreferrer">Read on Know Your Meme</a><button class="button button-secondary" type="button" id="copyLink">Copy link</button><button class="button button-secondary" type="button" id="viewJson">View JSON</button></div></div><dl class="detail-facts"><div class="fact"><dt>Source publication</dt><dd>${escapeHtml(dateLabel(item.created_at))}</dd></div><div class="fact"><dt>Retrieved by Meme-ology</dt><dd>${escapeHtml(freshnessLabel(item))}</dd></div><div class="fact"><dt>Author</dt><dd>${escapeHtml(item.author || "Not documented in the collected source")}</dd></div><div class="fact"><dt>Origin</dt><dd>${escapeHtml(item.origin_platform || "Not documented in the collected source")}</dd></div><div class="fact"><dt>Record ID</dt><dd><code>${escapeHtml(item.id)}</code></dd></div></dl></div>`;
      $("#copyLink").addEventListener("click", async () => {
        await navigator.clipboard.writeText(window.location.href);
        $("#copyLink").textContent = "Link copied";
      });
      $("#viewJson").addEventListener("click", () => {
        $("#responseOutput").textContent = JSON.stringify(item, null, 2);
        window.location.hash = "playground";
        $("#playground").scrollIntoView({ behavior: "smooth", block: "start" });
      });
      bindImageFallbacks();
    } catch (error) {
      section.innerHTML = stateMessage("error", "This entry is not available in the current source collection.");
    }
  }

  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("memeology-theme", theme);
    const button = $("#themeToggle");
    button.textContent = theme === "charcoal" ? "Paper theme" : "Reading theme";
    button.setAttribute("aria-pressed", theme === "charcoal" ? "true" : "false");
  }

  function setupApiPlayground() {
    const form = $("#apiForm");
    const updateExamples = () => {
      const endpoint = $("#endpointSelect").value;
      const limit = Number($("#limitInput").value || 5);
      const query = `${endpoint}?limit=${limit}`;
      $("#curlExample").textContent = `curl "${query}"`;
      $("#pythonExample").textContent = `httpx.get("${endpoint}", params={"limit": ${limit}})`;
      $("#jsExample").textContent = `fetch("${query}")`;
    };
    $("#endpointSelect").addEventListener("change", updateExamples);
    $("#limitInput").addEventListener("input", updateExamples);
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const endpoint = $("#endpointSelect").value;
      const limit = Math.min(50, Math.max(1, Number($("#limitInput").value || 5)));
      const status = $("#apiStatus");
      status.textContent = "Requesting...";
      try {
        const payload = await getJson(`${endpoint}?limit=${limit}`);
        $("#responseOutput").textContent = JSON.stringify(payload, null, 2);
        $("#responseLabel").textContent = "200 OK response";
        status.textContent = "Response received.";
      } catch (error) {
        $("#responseOutput").textContent = JSON.stringify({ error: "The endpoint could not be reached." }, null, 2);
        $("#responseLabel").textContent = "Request failed";
        status.textContent = "Request failed. Try again.";
      }
      updateExamples();
    });
    $("#copyResponse").addEventListener("click", async () => {
      await navigator.clipboard.writeText($("#responseOutput").textContent);
      $("#copyResponse").textContent = "Copied";
      window.setTimeout(() => { $("#copyResponse").textContent = "Copy JSON"; }, 1600);
    });
    updateExamples();
  }

  async function loadHealth() {
    try {
      const health = await getJson("/health");
      const status = health.status === "ok" ? "Collection available" : `Collection ${health.status}`;
      $("#sourceStatus").textContent = `${status} · ${health.total_memes || 0} cached records`;
    } catch (error) {
      $("#sourceStatus").textContent = "Collection status unavailable";
    }
  }

  function setupSearch() {
    const params = new URLSearchParams(window.location.search);
    state.query = params.get("q") || "";
    $("#searchInput").value = state.query;
    $("#searchForm").addEventListener("submit", (event) => {
      event.preventDefault();
      state.query = $("#searchInput").value.trim();
      state.offset = 0;
      const next = new URL(window.location.href);
      if (state.query) next.searchParams.set("q", state.query); else next.searchParams.delete("q");
      window.history.pushState({}, "", next);
      loadCollections();
    });
  }

  async function init() {
    applyTheme(localStorage.getItem("memeology-theme") || "paper");
    $("#themeToggle").addEventListener("click", () => applyTheme(document.documentElement.dataset.theme === "charcoal" ? "paper" : "charcoal"));
    $("#loadMore").addEventListener("click", loadMore);
    setupSearch();
    setupApiPlayground();
    loadHealth();
    const detailId = document.body.dataset.detailId || (window.location.pathname.startsWith("/meme/") ? decodeURIComponent(window.location.pathname.split("/meme/")[1]) : "");
    if (detailId) {
      await renderDetail(detailId);
    } else {
      await loadCollections();
    }
  }

  window.addEventListener("popstate", () => window.location.reload());
  document.addEventListener("DOMContentLoaded", init);
})();
