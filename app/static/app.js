"use strict";
/* TripLens: hash-routed, keyboard-first transit query UI. English default,
   auto-detected from the browser, switchable in the header (saved locally). */

const API = "/api";
const NET = { CR: { color: "#F6891F" }, SM: { color: "#12A5B0" },
              LR: { color: "#EB3843" }, SF: { color: "#5BB84D" } };
const NET_ORDER = ["CR", "SM", "LR", "SF"];
const ROUTE_ORDER = ["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9",
                     "M1", "BMT", "CCN", "SCO", "SHL", "HUN",
                     "L1", "L2", "L3", "L4", "NLR", "LX",
                     "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10",
                     "CCLC", "CRF", "MFF"];
const REAL_LINE = /^(T\d|M\d|L\d|F\d+|BMT|CCN|SCO|SHL|HUN|NLR|LX|CCLC|CRF|MFF)$/;
const TIME_BANDS = [["all", 0, 1440], ["ampeek", 360, 570],
                    ["day", 570, 960], ["pmpeek", 960, 1140], ["night", 1140, 1440]];

const I18N = {
  en: {
    title: "TripLens · Sydney transit", tagline: "Sydney transit · live + full timetables",
    nav_station: "Stations", nav_line: "Line timetables", nav_alerts: "Service notices",
    search_ph: "Search station or line  ( / to focus, ↑↓ to pick, Enter to open )",
    loading_tt: "Loading timetables…",
    loading_board: "Loading departures…", loading_cat: "Loading line catalogue…",
    loading_line: "Loading {0}…", loading_alerts: "Loading notices…", loading_stops: "Loading stops…",
    home_routes: "Popular lines", home_routes_hint: "Tap a line to see the whole day and per-stop times",
    home_stations: "Popular stations", home_stations_hint: "Or just type a station name ( / )",
    all_lines: "All lines →", live_now: "Live now", live_none: "Nothing is being adjusted right now",
    kpi_trips: "Trips today", kpi_lines: "lines", kpi_stations: "stations", kpi_share: "share of trips",
    freq: "Trips per hour", freq_peak: "peak {0} at {1}:00", hour: "Hour",
    date: "Date", today: "Today", all: "All",
    only_live: "Live changes only", show_past: "Show departed",
    dir: "Dir", dir1: "Dir 1", dir2: "Dir 2", jump_now: "⏱ Jump to now",
    band: "Period", band_all: "All day", band_ampeek: "AM peak", band_day: "Daytime",
    band_pmpeek: "PM peak", band_night: "Evening",
    th_time: "Time", th_line: "Line", th_to: "To", th_plat: "Platform", th_status: "Status / trip",
    th_origin: "Departs", th_trip: "Run", th_dest: "Destination", th_stops: "Stops",
    now: "Now", due: "Due", in_min: "in {0} min", in_hm: "in {0} h {1} min",
    departed: "Departed", live_fix: "Live", adjusted: "Trip adjusted",
    departs_at: "departs {0}", stops_n: "{0} stops", trips_n: "{0} trips",
    day_total: "{0} trips on {1}", showing: "{0}–{1} of {2}", per_page: "Per page",
    prev: "Prev", next: "Next", page: "Page {0}/{1}",
    board_empty: "No services match. Try another date, show departed, or clear the filters.",
    from: "from {0}", pax_live: "with live changes",
    alerts_ph: "Filter notices (line code / keyword)",
    alert_interrupt: "Disruption", alert_trackwork: "Trackwork", alert_alert: "Notice", alert_news: "News",
    expand: "Show more", collapse: "Show less", alerts_empty: "No notices match.",
    station_plat: "{0} platforms", routes_here: "Lines at this station",
    err: "Could not load: {0}", err_conn: "Cannot reach the local service: {0}",
    no_match: "No matching station or line",
    ts_sched: "scheduled", tap_row: "Tap a row for the full stop list",
    stops_title: "{0} stops", delay_min: "{0} min",
    net: { CR: "Trains", SM: "Metro", LR: "Light rail", SF: "Ferries" },
    peak_n: "up to {0}/h", all_lines_hint: "full catalogue by network",
    no_more_today: "no more services today",
  },
  zh: {
    title: "TripLens · 悉尼交通查询", tagline: "悉尼交通查询 · 实时 + 完整时刻表",
    nav_station: "站点查询", nav_line: "线路时刻表", nav_alerts: "服务通告",
    search_ph: "搜索车站或线路（按 / 聚焦，↑↓ 选择，Enter 打开）",
    loading_tt: "正在加载时刻表…",
    loading_board: "正在读取班次…", loading_cat: "正在读取线路目录…",
    loading_line: "正在读取 {0}…", loading_alerts: "正在读取通告…", loading_stops: "正在读取停站…",
    home_routes: "常用线路", home_routes_hint: "点线路直接看当日全部班次与逐站时刻",
    home_stations: "常用车站", home_stations_hint: "也可以直接搜站名（按 / 聚焦）",
    all_lines: "全部线路 →", live_now: "实时活跃", live_none: "当前没有被实时修正的班次",
    kpi_trips: "当日班次", kpi_lines: "线路", kpi_stations: "车站", kpi_share: "占全部班次",
    freq: "每小时班次", freq_peak: "峰值 {0} 班（{1}:00）", hour: "时刻",
    date: "日期", today: "今天", all: "全部",
    only_live: "只看实时修正", show_past: "显示已开出",
    dir: "方向", dir1: "方向 1", dir2: "方向 2", jump_now: "⏱ 跳到现在",
    band: "时段", band_all: "全部", band_ampeek: "早高峰", band_day: "白天",
    band_pmpeek: "晚高峰", band_night: "夜间",
    th_time: "时刻", th_line: "线路", th_to: "开往", th_plat: "站台", th_status: "状态 / 车次",
    th_origin: "始发", th_trip: "车次", th_dest: "终点", th_stops: "站数",
    now: "现在", due: "即将", in_min: "{0} 分钟后", in_hm: "{0} 小时 {1} 分后",
    departed: "已开出", live_fix: "实时修正", adjusted: "本班有调整",
    departs_at: "本站 {0} 发车", stops_n: "{0} 站", trips_n: "{0} 班",
    day_total: "{1} 共 {0} 班", showing: "显示 {0}–{1} / {2}", per_page: "每页",
    prev: "上一页", next: "下一页", page: "第 {0}/{1} 页",
    board_empty: "没有符合条件的班次。试试切换日期、打开「显示已开出」或清除筛选。",
    from: "始发 {0}", pax_live: "含实时修正",
    alerts_ph: "筛选通告（线路代码 / 关键词）",
    alert_interrupt: "中断", alert_trackwork: "施工", alert_alert: "通告", alert_news: "新闻",
    expand: "展开全文", collapse: "收起", alerts_empty: "没有匹配的通告。",
    station_plat: "站台 {0} 个", routes_here: "本站线路",
    err: "读取失败：{0}", err_conn: "无法连接本地服务：{0}",
    no_match: "没有匹配的车站或线路",
    ts_sched: "计划", tap_row: "点任意一行查看完整停站",
    stops_title: "{0} 站", delay_min: "{0} 分",
    net: { CR: "火车", SM: "地铁", LR: "轻轨", SF: "渡轮" },
    peak_n: "高峰 {0} 班/时", all_lines_hint: "按网络查看全部线路",
    no_more_today: "今日已无班次",
  },
};

let LANG = (() => {
  const saved = localStorage.getItem("tl.lang");
  if (saved === "zh" || saved === "en") return saved;
  const tags = navigator.languages && navigator.languages.length
    ? navigator.languages : [navigator.language || "en"];
  return tags.some((x) => /^zh/i.test(x)) ? "zh" : "en";
})();
const t = (key, ...args) => {
  let s = (I18N[LANG] && I18N[LANG][key]) || I18N.en[key] || key;
  args.forEach((v, i) => { s = s.replace(`{${i}}`, v); });
  return s;
};
const LOCALE = () => (LANG === "zh" ? "zh-CN" : "en-AU");
const label = (key) => t("band_" + key);

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const hhmm = (min) => {
  const v = ((Math.round(min) % 1440) + 1440) % 1440;
  return String(Math.floor(v / 60)).padStart(2, "0") + ":" + String(v % 60).padStart(2, "0");
};
const sydneyNow = () => {
  const p = new Intl.DateTimeFormat("en-GB", { timeZone: "Australia/Sydney",
    hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }).formatToParts(new Date());
  const g = (x) => +(p.find((y) => y.type === x)?.value || 0);
  return { h: g("hour"), m: g("minute"), s: g("second") };
};
const sydneyDate = () => new Date().toLocaleDateString("en-CA", { timeZone: "Australia/Sydney" });
const svcMinutes = () => { const n = sydneyNow(); const m = n.h * 60 + n.m; return m < 180 ? m + 1440 : m; };
const rel = (d) => d <= 0 ? t("now") : d < 1 ? t("due")
  : d < 60 ? t("in_min", Math.round(d)) : t("in_hm", Math.floor(d / 60), Math.round(d % 60));
const dayLabel = (d) => new Date(d + "T12:00:00").toLocaleDateString(LOCALE(),
  { weekday: "short", month: "short", day: "numeric" }) + (d === sydneyDate() ? ` · ${t("today")}` : "");
const shortLine = (n) => String(n || "").replace(/^[A-Za-z0-9]+\s+/, "").replace(/\s+(Line|Services)$/, "");
const lineLabel = (code, name) => { const s = shortLine(name); return s && s !== code ? `${code} ${s}` : code; };
const json = async (url) => {
  const r = await fetch(url, { cache: "no-store" });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.detail || body.error || `HTTP ${r.status}`);
  return body;
};
const qs = (o) => Object.entries(o).filter(([, v]) => v !== null && v !== undefined && v !== "")
  .map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join("&");

const state = {
  meta: null, route: { name: "station", station: null, line: null },
  day: null, network: null, liveOnly: false, includePast: false, limit: 50,
  board: null, boardErr: null,
  line: null, lineDir: null, lineData: null, band: "all",
  pageSize: 40, page: { 0: 0, 1: 0 }, lineScrolled: null,
  alerts: null, alertNet: null, alertQ: "", alertOpen: new Set(),
  stats: null, rt: null, pollMs: 30000, nextPoll: 0, loading: false, search: { sel: -1 },
};

/* ── language ──────────────────────────────────────────── */
function applyLang(rerender = true) {
  document.documentElement.lang = LANG === "zh" ? "zh-CN" : "en";
  document.title = t("title");
  document.querySelectorAll("#nav a").forEach((a) => { a.textContent = t(a.dataset.i18n); });
  const tag = $("tagline");
  if (tag) tag.textContent = t("tagline");
  $("q").placeholder = t("search_ph");
  document.querySelectorAll("#lang button").forEach((b) =>
    b.classList.toggle("on", b.dataset.lang === LANG));
  if (rerender) render();
}
$("lang").addEventListener("click", (e) => {
  const b = e.target.closest("[data-lang]");
  if (!b || b.dataset.lang === LANG) return;
  LANG = b.dataset.lang;
  localStorage.setItem("tl.lang", LANG);
  applyLang();
});

/* ── routing ───────────────────────────────────────────── */
function parseHash() {
  const raw = location.hash.replace(/^#\/?/, "");
  const [head, ...rest] = raw.split("/");
  const arg = rest.join("/");
  if (head === "line") return { name: "line", line: arg ? decodeURIComponent(arg) : null };
  if (head === "alerts") return { name: "alerts" };
  return { name: "station", station: arg ? decodeURIComponent(arg) : null };
}
window.addEventListener("hashchange", () => {
  state.route = parseHash();
  state.lineScrolled = null;
  state.page = { 0: 0, 1: 0 };
  render();
});

async function boot() {
  setClock();
  setInterval(setClock, 1000);
  applyLang(false);
  try { state.meta = await json(`${API}/meta`); }
  catch (e) { $("view").innerHTML = `<div class="empty err">${esc(t("err_conn", e.message))}</div>`; return; }
  $("buildinfo").textContent = `v${state.meta.version} · ${state.meta.region} · ` +
    `${state.meta.counts.stations} ${t("kpi_stations")} / ${state.meta.counts.lines} ${t("kpi_lines")}`;
  if (!state.meta.ready) {
    $("view").innerHTML = state.meta.error
      ? `<div class="empty err">${esc(t("err", state.meta.error))}</div>`
      : `<div class="splash"><div class="spin"></div>${esc(t("loading_tt"))}</div>`;
    return setTimeout(boot, 1500);
  }
  const dates = state.meta.dates || [];
  state.day = dates.includes(sydneyDate()) ? sydneyDate() : dates[0] || null;
  state.route = parseHash();
  state.nextPoll = Date.now() + state.pollMs;
  render();
  setInterval(tick, 1000);
}
function setClock() {
  const n = sydneyNow();
  $("clock").textContent = `${String(n.h).padStart(2, "0")}:${String(n.m).padStart(2, "0")}`;
}
function tick() {
  setClock();
  const left = Math.max(0, state.nextPoll - Date.now());
  $("cd").textContent = left ? Math.ceil(left / 1000) + "s" : "…";
  if (left <= 0 && !state.loading) refreshLive();
  document.querySelectorAll("[data-ms]").forEach((node) => {
    const min = +node.dataset.ms;
    node.textContent = node.dataset.past === "1" ? t("departed") : rel(min - svcMinutes());
  });
}
async function refreshLive() {
  state.nextPoll = Date.now() + state.pollMs;
  if (state.route.name === "station") {
    if (state.route.station) await loadBoard({ keep: true });
    else await loadRoutes(true);
  }
}

/* ── search ────────────────────────────────────────────── */
let searchTimer = null;
$("q").addEventListener("input", () => {
  clearTimeout(searchTimer);
  const value = $("q").value.trim();
  if (!value) return closeResults();
  searchTimer = setTimeout(() => runSearch(value), 140);
});
$("q").addEventListener("keydown", (e) => {
  const items = $("results").querySelectorAll(".item");
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    e.preventDefault();
    state.search.sel = Math.max(0, Math.min(items.length - 1,
      state.search.sel + (e.key === "ArrowDown" ? 1 : -1)));
    items.forEach((n, i) => n.setAttribute("aria-selected", String(i === state.search.sel)));
    items[state.search.sel]?.scrollIntoView({ block: "nearest" });
  } else if (e.key === "Enter") {
    (items[state.search.sel] || items[0])?.click();
  } else if (e.key === "Escape") { $("q").blur(); closeResults(); }
});
document.addEventListener("keydown", (e) => {
  if (e.key === "/" && document.activeElement !== $("q")) {
    e.preventDefault(); $("q").focus(); $("q").select();
  } else if (e.key === "Escape") closeDrawer();
});
document.addEventListener("click", (e) => {
  if (!$("searchbox").contains(e.target)) closeResults();
});
const closeResults = () => { $("results").classList.remove("open"); state.search.sel = -1; };

async function runSearch(value) {
  let data;
  try { data = await json(`${API}/search?${qs({ q: value, limit: 10 })}`); } catch { return; }
  const items = [
    ...data.stations.map((s) => ({ kind: t("nav_station"), name: s.name,
      meta: s.lines.join(" · "), go: `#/station/${encodeURIComponent(s.name)}` })),
    ...data.lines.map((l) => ({ kind: t("nav_line"), name: lineLabel(l.code, l.name),
      meta: l.id, go: `#/line/${encodeURIComponent(l.id)}` })),
  ];
  state.search.sel = -1;
  $("results").innerHTML = items.length
    ? items.map((it, i) => `<div class="item" role="option" aria-selected="${i === 0}" data-go="${esc(it.go)}">
        <span class="kind">${esc(it.kind)}</span><span class="nm">${esc(it.name)}</span>
        <span class="muted" style="font-size:11.5px">${esc(it.meta)}</span></div>`).join("")
    : `<div class="hint">${esc(t("no_match"))}</div>`;
  $("results").classList.add("open");
  $("results").querySelectorAll(".item").forEach((node) => {
    node.addEventListener("click", () => {
      const target = node.dataset.go;
      $("q").value = ""; closeResults();
      if (location.hash === target) { state.route = parseHash(); render(); } else location.hash = target;
    });
  });
}

/* ── render dispatch ───────────────────────────────────── */
function render() {
  document.querySelectorAll("#nav a").forEach((a) =>
    a.classList.toggle("on", a.dataset.tab === state.route.name));
  if (state.route.name === "station") return state.route.station ? renderStation() : renderHome();
  if (state.route.name === "line") return renderLine();
  return renderAlerts();
}
const panel = (inner) => `<div class="panel">${inner}</div>`;
const head = (title, hint) =>
  `<div class="row spread"><h2>${esc(title)}</h2><span class="sub">${hint || ""}</span></div>`;

/* ── home (with visualisations) ────────────────────────── */
function renderHome() {
  $("view").innerHTML =
    panel(`<div id="stats"><div class="splash"><div class="spin"></div>${esc(t("loading_cat"))}</div></div>`) +
    panel(head(t("home_routes"), esc(t("home_routes_hint"))) +
      `<div class="grid" id="routes" style="margin-top:12px"></div>`) +
    panel(head(t("home_stations"), esc(t("home_stations_hint"))) +
      `<div class="grid" id="quick" style="margin-top:12px"></div>
       <div class="chips" id="livechips" style="margin-top:10px"></div>`);
  loadStats();
  loadRoutes();
  loadQuick();
}

async function loadStats() {
  const box = $("stats");
  try {
    state.stats = await json(`${API}/stats?` + qs({ day: state.day }));
  } catch (e) {
    box.innerHTML = `<div class="empty err">${esc(t("err", e.message))}</div>`;
    return;
  }
  const s = state.stats;
  const peakHour = s.hours.reduce((a, b) => (b.total > a.total ? b : a), s.hours[0]);
  const nowHour = Math.min(23, Math.floor(svcMinutes() / 60));
  const live = s.live || { transpositions: 0, lines: [] };
  const cards = [
    `<div class="kpi"><div class="k">${esc(t("kpi_trips"))} · ${esc(dayLabel(s.day))}</div>
       <div class="v">${s.total.toLocaleString()}</div>
       <div class="s">${esc(t("freq_peak", peakHour.total, String(peakHour.hour).padStart(2, "0")))}</div></div>`,
    ...s.networks.map((n) => `<div class="kpi">
        <div class="k"><span class="sw" style="background:${NET[n.network].color}"></span>${esc(netName(n.network))}</div>
        <div class="v">${n.trips.toLocaleString()}</div>
        <div class="s">${n.lines} ${esc(t("kpi_lines"))} · ${n.stations} ${esc(t("kpi_stations"))} · ${Math.round(n.share * 100)}%</div>
      </div>`),
    `<div class="kpi"><div class="k">${esc(t("live_now"))}</div>
       <div class="v">${live.transpositions || 0}</div>
       <div class="s">${live.lines && live.lines.length
         ? live.lines.slice(0, 4).map((c) => `<a href="#/line/${encodeURIComponent(c)}">${esc(c.split("_")[1] || c)}</a>`).join(" · ")
         : esc(t("live_none"))}</div></div>`,
  ].join("");
  const bars = s.hours.map((h) => {
    const segs = NET_ORDER.filter((k) => h[k]).map((k) =>
      `<div class="seg" style="background:${NET[k].color};height:${(h[k] / (s.peak || 1)) * 100}%"></div>`);
    return `<div class="col" title="${String(h.hour).padStart(2, "0")}:00 · ${h.total}">
      ${h.hour === nowHour ? `<div class="nowline"></div>` : ""}${segs.join("")}</div>`;
  }).join("");
  const ticks = s.hours.map((h) => `<span>${h.hour % 3 === 0 ? String(h.hour).padStart(2, "0") : ""}</span>`).join("");
  box.innerHTML =
    `<div class="cards">${cards}</div>
     <div class="chart">
       <div class="row spread" style="margin:12px 0 6px">
         <h3>${esc(t("freq"))}</h3>
         <span class="sub">${esc(t("freq_peak", peakHour.total, String(peakHour.hour).padStart(2, "0")))}</span>
       </div>
       <div class="bars">${bars}</div>
       <div class="bar-labels">${ticks}</div>
       <div class="legend">${NET_ORDER.filter((k) => s.networks.some((n) => n.network === k))
         .map((k) => `<span><i style="background:${NET[k].color}"></i>${esc(netName(k))}</span>`).join("")}
         <span class="sp"></span><span class="muted">${esc(t("hour"))} 0–23</span></div>
     </div>`;
}

const netName = (k) => (I18N[LANG].net || I18N.en.net)[k] || k;

async function loadRoutes(quiet = false) {
  const box = $("routes");
  if (!box) return;
  if (!quiet) box.innerHTML = `<span class="sub">${esc(t("loading_cat"))}</span>`;
  try {
    const cat = await json(`${API}/lines?` + qs({ day: state.day }));
    const rank = (c) => { const i = ROUTE_ORDER.indexOf(c); return i < 0 ? 99 : i; };
    const list = cat.lines.filter((l) => REAL_LINE.test(l.code))
      .sort((a, b) => rank(a.code) - rank(b.code) || (b.trips[0] + b.trips[1]) - (a.trips[0] + a.trips[1]))
      .slice(0, 18);
    box.innerHTML = list.map((l) => {
      const trips = l.trips[0] + l.trips[1];
      const colour = NET[l.network]?.color || "#888";
      return `<a class="lcard" href="#/line/${encodeURIComponent(l.id)}"
          style="--accent:${colour}" title="${esc(l.name)}">
        <span class="ico">${modeIcon(l.network)}</span>
        <span class="body">
          <span class="tit"><b class="badge" style="background:${colour}">${esc(l.code)}</b>
            <span class="nm">${esc(shortLine(l.name))}</span></span>
          <span class="meta">${esc(t("trips_n", trips))} · ${esc(l.first || "—")}–${esc(l.last || "—")} ·
            ${esc(t("peak_n", l.peak))}</span>
        </span></a>`;
    }).join("") + `<a class="lcard more-card" href="#/line">
        <span class="ico">＋</span><span class="body"><span class="tit"><b>${esc(t("all_lines"))}</b></span>
        <span class="meta">${esc(t("all_lines_hint"))}</span></span></a>`;
  } catch (e) {
    box.innerHTML = `<span class="sub">${esc(t("err", e.message))}</span>`;
  }
}

async function loadQuick() {
  try {
    const [pop, live] = await Promise.all([
      json(`${API}/popular?` + qs({ limit: 12, next: 3, day: state.day })),
      json(`${API}/live/stations?limit=8`).catch(() => ({ stations: [] })),
    ]);
    $("quick").innerHTML = pop.stations.map((s) =>
      `<a class="scard" href="#/station/${encodeURIComponent(s.name)}">
        <span class="tit"><span class="ico">🚉</span><b>${esc(s.name)}</b>
          <span class="meta">${esc(t("station_plat", s.platforms))}</span></span>
        <span class="lines">${s.lines.slice(0, 5).map((c) =>
          `<span class="badge" style="background:${codeColour(c)}">${esc(c)}</span>`).join("")}</span>
        <span class="next">${(s.next || []).map((n) =>
          `<span class="nrow"><b>${esc(n.clock)}</b>
             <span class="badge" style="background:${NET[n.network]?.color || "#888"}">${esc(n.line)}</span>
             <span class="dest">${esc(n.destination)}</span>
             <span class="pf">${n.platform ? "P" + esc(n.platform) : ""}</span></span>`).join("")
          || `<span class="muted">${esc(t("no_more_today"))}</span>`}</span></a>`).join("");
    $("livechips").innerHTML = live.stations.length
      ? `<span class="sub" style="align-self:center">${esc(t("live_now"))}</span>` + live.stations.map((s) =>
        `<a class="chip" href="#/station/${encodeURIComponent(s.station)}">
           <span class="sw" style="background:var(--ok)"></span>${esc(s.station)}
           <span class="n">${s.trips}</span></a>`).join("")
      : "";
  } catch { /* keep the page usable */ }
}
const modeIcon = (k) => ({ CR: "🚆", SM: "🚇", LR: "🚊", SF: "⛴" }[k] || "🚏");
const codeColour = (code) => {
  const fam = { T: "CR", M: "SM", L: "LR", F: "SF" }[String(code)[0]] || "CR";
  return NET[fam]?.color || "#888";
};

/* ── station board ─────────────────────────────────────── */
function renderStation() {
  const name = state.route.station;
  $("view").innerHTML =
    panel(`<div class="row spread">
        <div class="row"><h2>${esc(name)}</h2><span class="sub" id="stMeta"></span></div>
        <div class="row"><label class="f">${esc(t("date"))}<select id="daySel"></select></label>
          <button class="icon" id="reloadStation" title="${esc(t("jump_now"))}">↻</button></div>
      </div><div class="chips" id="stLines" style="margin-top:10px"></div>`) +
    panel(`<div class="row spread">
        <div class="chips" id="netChips"></div>
        <div class="row">
          <label class="f"><input type="checkbox" id="liveOnly"> ${esc(t("only_live"))}</label>
          <label class="f"><input type="checkbox" id="showPast"> ${esc(t("show_past"))}</label>
        </div></div>`) +
    `<div id="board"><div class="splash"><div class="spin"></div>${esc(t("loading_board"))}</div></div>`;
  fillDaySelect($("daySel"), state.day);
  $("daySel").addEventListener("change", (e) => { state.day = e.target.value; loadBoard(); });
  $("reloadStation").addEventListener("click", () => loadBoard());
  $("liveOnly").checked = state.liveOnly;
  $("showPast").checked = state.includePast;
  $("liveOnly").addEventListener("change", (e) => { state.liveOnly = e.target.checked; drawBoard(); });
  $("showPast").addEventListener("change", (e) => { state.includePast = e.target.checked; drawBoard(); });
  loadStationMeta(name);
  loadBoard();
}

function fillDaySelect(sel, value) {
  sel.innerHTML = (state.meta?.dates || []).map((d) =>
    `<option value="${d}"${d === value ? " selected" : ""}>${esc(dayLabel(d))}</option>`).join("");
}

async function loadStationMeta(name) {
  try {
    const st = await json(`${API}/station?${qs({ name })}`);
    $("stMeta").innerHTML = `${esc(t("station_plat", st.platforms.length))} · ` +
      `${esc(st.timetables.join(" / "))} · ${st.lat.toFixed(4)},${st.lon.toFixed(4)}`;
    const seen = new Set();
    $("stLines").innerHTML = st.lines.filter((l) => !seen.has(l.code) && seen.add(l.code))
      .map((l) => {
        const short = shortLine(l.name);
        return `<a class="chip" href="#/line/${encodeURIComponent(l.id)}" title="${esc(l.name)}">
          <span class="sw" style="background:${NET[l.network]?.color || "#888"}"></span>${esc(l.code)}
          ${short && short !== l.code ? `<span class="n">${esc(short)}</span>` : ""}</a>`;
      }).join("");
  } catch { /* leave the header minimal */ }
}

async function loadBoard({ keep = false } = {}) {
  if (!keep) state.limit = 50;
  state.loading = true;
  try {
    state.board = await json(`${API}/departures?` + qs({
      station: state.route.station, day: state.day, limit: state.limit, live: 1,
      include_past: state.includePast ? 1 : 0 }));
    state.boardErr = null;
    if (state.board.realtime?.pollInterval) {
      state.pollMs = Math.max(10, state.board.realtime.pollInterval) * 1000;
      $("dot").className = "dot";
    }
  } catch (e) {
    state.boardErr = e.message; state.board = null; $("dot").className = "dot err";
  } finally {
    state.loading = false;
    state.nextPoll = Date.now() + state.pollMs;
    drawBoard();
  }
}

function drawBoard() {
  if (state.boardErr) {
    $("board").innerHTML = `<div class="empty err">${esc(t("err", state.boardErr))}</div>`;
    return;
  }
  const data = state.board;
  if (!data) return;
  const now = svcMinutes();
  const today = data.day === sydneyDate();
  const counts = {};
  for (const r of data.rows) counts[r.network] = (counts[r.network] || 0) + 1;
  $("netChips").innerHTML = [`<button class="chip ${!state.network ? "on" : ""}" data-net="">${esc(t("all"))}
      <span class="n">${data.rows.length}</span></button>`]
    .concat(NET_ORDER.filter((k) => counts[k]).map((k) =>
      `<button class="chip ${state.network === k ? "on" : ""}" data-net="${k}">
         <span class="sw" style="background:${NET[k].color}"></span>${esc(netName(k))}
         <span class="n">${counts[k]}</span></button>`)).join("");
  $("netChips").querySelectorAll("[data-net]").forEach((b) =>
    b.addEventListener("click", () => { state.network = b.dataset.net || null; drawBoard(); }));

  let rows = data.rows;
  if (state.network) rows = rows.filter((r) => r.network === state.network);
  if (state.liveOnly) rows = rows.filter((r) => r.realtime || r.trip_realtime);
  if (!state.includePast && today) rows = rows.filter((r) => (r.live ?? r.time) >= now - 1);
  const nextIndex = rows.findIndex((r) => (r.live ?? r.time) >= now);
  const headHtml = `<div class="row spread" style="margin-bottom:8px">
      <span class="sub">${esc(t("day_total", data.count, dayLabel(data.day)))}</span>
      <span class="sub">${esc(t("tap_row"))}${data.realtime?.transpositions
        ? ` · ${esc(t("live_now"))} ${data.realtime.transpositions}` : ""}</span></div>`;
  if (!rows.length) {
    $("board").innerHTML = headHtml + `<div class="empty">${esc(t("board_empty"))}</div>`;
    return;
  }
  $("board").innerHTML = headHtml + `<table class="board"><thead><tr>
      <th style="width:92px">${esc(t("th_time"))}</th><th style="width:74px">${esc(t("th_line"))}</th>
      <th>${esc(t("th_to"))}</th><th style="width:70px">${esc(t("th_plat"))}</th>
      <th style="width:170px">${esc(t("th_status"))}</th></tr></thead><tbody>
      ${rows.map((r, i) => rowHTML(r, i === nextIndex, now, today)).join("")}
    </tbody></table>
    ${data.truncated ? `<button class="more" id="moreBtn">${esc(t("expand"))}</button>` : ""}`;
  $("moreBtn")?.addEventListener("click", () => { state.limit += 60; loadBoard({ keep: true }); });
  $("board").querySelectorAll("tr.svc").forEach((tr) =>
    tr.addEventListener("click", () => openTrip(tr.dataset)));
}

function rowHTML(r, isNext, now, today) {
  const eff = r.live ?? r.time;
  const delay = r.delay || 0;
  const past = today && eff < now - 1;
  const colour = NET[r.network]?.color || "#888";
  const tags = [];
  if (r.realtime) {
    tags.push(`<span class="tag live">${esc(t("live_fix"))}</span>`);
    if (delay) tags.push(`<span class="tag">${delay > 0 ? "+" : ""}${esc(t("delay_min", delay))}</span>`);
  } else if (r.trip_realtime) tags.push(`<span class="tag">${esc(t("adjusted"))}</span>`);
  if (past) tags.push(`<span class="tag">${esc(t("departed"))}</span>`);
  if (r.trip) tags.push(`<span class="tag trip">${esc(r.trip)}</span>`);
  const countdown = today && !past ? `<span class="tag now" data-ms="${eff}">${esc(rel(eff - now))}</span>` : "";
  return `<tr class="svc${past ? " past" : ""}${isNext ? " next" : ""}"
      data-line="${esc(r.line_id)}" data-depart="${r.depart}" data-at="${r.time}"
      data-trip="${esc(r.trip)}" data-day="${esc(state.day)}">
    <td class="t">${esc(r.live_clock || r.clock)}${r.realtime && r.live_clock !== r.clock
      ? `<span class="sched">${esc(r.clock)}</span>
         <span class="delay ${delay <= 0 ? "ok" : ""}">${delay > 0 ? "+" : ""}${delay}′</span>` : ""}</td>
    <td><span class="badge" style="background:${colour}" title="${esc(r.line_id)}">${esc(r.line)}</span></td>
    <td class="to"><span class="dest">${esc(r.destination || r.headsign || "—")}</span>
      <span class="lh">${esc(t("from", r.origin || "—"))} · ${esc(shortLine(r.line_name))} ·
        ${esc(r.direction === 0 ? t("dir1") : t("dir2"))} · ${esc(t("stops_n", r.stops))}</span></td>
    <td class="pf">${r.platform ? "P" + esc(r.platform) : "—"}</td>
    <td class="st">${countdown} ${tags.join(" ")}</td></tr>`;
}

/* ── line timetable (paginated) ────────────────────────── */
async function renderLine() {
  if (state.route.line && state.route.line !== state.line) {
    state.line = state.route.line;
    state.lineDir = null; state.lineScrolled = null; state.page = { 0: 0, 1: 0 };
  }
  $("view").innerHTML =
    panel(`<div class="row spread">
        <div class="row"><h2>${esc(t("nav_line"))}</h2><span class="sub" id="lnPick"></span></div>
        <div class="row"><select id="lnSel"></select>
          <label class="f">${esc(t("date"))}<select id="lnDay"></select></label></div>
      </div><div class="chips" id="lnDirs" style="margin-top:10px"></div>`) +
    `<div id="lineBody"><div class="splash"><div class="spin"></div>${esc(t("loading_cat"))}</div></div>`;
  try {
    const cat = await json(`${API}/lines?` + qs({ day: state.day }));
    const byNet = {};
    for (const l of cat.lines) (byNet[l.network] ||= []).push(l);
    $("lnSel").innerHTML = NET_ORDER.filter((k) => byNet[k]).map((k) =>
      `<optgroup label="${esc(netName(k))}">` + byNet[k].map((l) =>
        `<option value="${esc(l.id)}"${l.id === state.line ? " selected" : ""}>` +
        `${esc(lineLabel(l.code, l.name))} (${l.trips[0] + l.trips[1]})</option>`).join("") + `</optgroup>`).join("");
    if (!state.line || !cat.lines.some((l) => l.id === state.line)) {
      const byTrips = [...cat.lines].sort((a, b) => (b.trips[0] + b.trips[1]) - (a.trips[0] + a.trips[1]));
      state.line = (byTrips.find((l) => REAL_LINE.test(l.code)) || byTrips[0])?.id || null;
      if (state.line) history.replaceState(null, "", `#/line/${encodeURIComponent(state.line)}`);
    }
    $("lnSel").value = state.line || "";
    $("lnSel").addEventListener("change", (e) => { location.hash = `#/line/${encodeURIComponent(e.target.value)}`; });
    fillDaySelect($("lnDay"), state.day);
    $("lnDay").addEventListener("change", (e) => {
      state.day = e.target.value; state.page = { 0: 0, 1: 0 }; loadLine();
    });
  } catch (e) {
    $("lineBody").innerHTML = `<div class="empty err">${esc(t("err", e.message))}</div>`;
    return;
  }
  loadLine();
}

async function loadLine() {
  if (!state.line) return;
  state.initialJump = true;      // open on "now" instead of the first trip
  $("lineBody").innerHTML = `<div class="splash"><div class="spin"></div>${esc(t("loading_line", state.line))}</div>`;
  try {
    state.lineData = await json(`${API}/line?` + qs({ line: state.line, day: state.day, limit: 1000, stops: 0 }));
  } catch (e) {
    $("lineBody").innerHTML = `<div class="empty err">${esc(t("err", e.message))}</div>`;
    return;
  }
  drawLine();
}

function drawLine() {
  const d = state.lineData;
  if (!d) return;
  const now = svcMinutes();
  const today = d.day === sydneyDate();
  $("lnPick").innerHTML = `${esc(lineLabel(d.line.code, d.line.name))} · <span class="muted">${esc(d.timetable)}</span>`;
  $("lnDirs").innerHTML = d.tables.map((x) =>
    `<button class="chip ${state.lineDir === x.direction ? "on" : ""}" data-dir="${x.direction}">
      ${esc(x.direction === 0 ? t("dir1") : t("dir2"))} ${esc(x.headsign || "")}
      <span class="n">${x.count}</span></button>`).join("") +
    `<span class="sub" style="align-self:center;margin-left:6px">${esc(t("band"))}</span>` +
    TIME_BANDS.map(([k]) =>
      `<button class="chip ${state.band === k ? "on" : ""}" data-band="${k}">${esc(label(k))}</button>`).join("") +
    (today ? `<button class="chip" data-jump="1">${esc(t("jump_now"))}</button>` : "");
  $("lnDirs").querySelectorAll("[data-dir]").forEach((b) =>
    b.addEventListener("click", () => {
      state.lineDir = state.lineDir === +b.dataset.dir ? null : +b.dataset.dir;
      state.page = { 0: 0, 1: 0 };
      drawLine();
    }));
  $("lnDirs").querySelectorAll("[data-band]").forEach((b) =>
    b.addEventListener("click", () => {
      state.band = b.dataset.band;
      state.page = { 0: 0, 1: 0 };
      drawLine();
    }));
  const band = TIME_BANDS.find(([k]) => k === state.band) || TIME_BANDS[0];
  const tables = (state.lineDir === null || state.lineDir === undefined)
    ? d.tables : d.tables.filter((x) => x.direction === state.lineDir);
  $("lineBody").innerHTML = tables.map((x) => {
    const trips = x.trips.filter((y) => y.depart >= band[1] && y.depart < band[2]);
    if (!trips.length) return "";
    const size = state.pageSize > 0 ? state.pageSize : trips.length;
    const pages = Math.max(1, Math.ceil(trips.length / size));
    const firstUpcoming = trips.findIndex((y) => y.depart >= now);
    const nowPage = firstUpcoming >= 0 ? Math.floor(firstUpcoming / size) : pages - 1;
    if (state.jumpNow === x.direction || (state.initialJump && today && firstUpcoming >= 0)) {
      state.page[x.direction] = nowPage;
      state.jumpNow = null;
    }
    const page = Math.max(0, Math.min(state.page[x.direction] || 0, pages - 1));
    state.page[x.direction] = page;
    const slice = trips.slice(page * size, page * size + size);
    return `<div class="panel" data-block="${x.direction}">
      <div class="row spread"><h3>${esc(x.direction === 0 ? t("dir1") : t("dir2"))} · ${esc(x.headsign || "")}</h3>
        <span class="sub">${esc(t("showing", page * size + 1, page * size + slice.length, trips.length))} · ${esc(t("trips_n", x.count))}</span></div>
      <table class="board" style="margin-top:8px"><thead><tr>
        <th style="width:80px">${esc(t("th_origin"))}</th><th style="width:104px">${esc(t("th_trip"))}</th>
        <th>${esc(t("th_dest"))}</th><th style="width:64px">${esc(t("th_stops"))}</th>
        <th style="width:130px">${esc(t("th_status"))}</th></tr></thead><tbody>
        ${slice.map((y, i) => `<tr class="svc${today && page * size + i === firstUpcoming ? " upcoming next" : ""}"
            data-line="${esc(d.line.id)}" data-depart="${y.depart}" data-trip="${esc(y.trip)}" data-day="${esc(state.day)}">
          <td class="t">${esc(y.clock)}</td><td class="pf">${esc(y.trip || "")}</td>
          <td class="to"><span class="dest">${esc(y.destination || "")}</span>
            <span class="lh">${esc(t("from", y.origin || ""))}</span></td>
          <td class="pf">${y.stop_count}</td>
          <td class="st">${today ? `<span class="tag" data-ms="${y.depart}"
            data-past="${y.depart < now ? 1 : 0}">${esc(y.depart < now ? t("departed") : rel(y.depart - now))}</span>`
            : `<span class="tag trip">${esc(y.service || "")}</span>`}</td></tr>`).join("")}
      </tbody></table>
      <div class="pager">
        <button data-page="${x.direction}" data-to="prev" ${page === 0 ? "disabled" : ""}>${esc(t("prev"))}</button>
        <span>${esc(t("page", page + 1, pages))}</span>
        <button data-page="${x.direction}" data-to="next" ${page >= pages - 1 ? "disabled" : ""}>${esc(t("next"))}</button>
        <span class="sp"></span>
        ${today ? `<button data-page="${x.direction}" data-to="now">${esc(t("jump_now"))}</button>` : ""}
        <label class="f">${esc(t("per_page"))}
          <select data-size="1">${[20, 40, 80, 0].map((n) =>
            `<option value="${n}"${n === state.pageSize ? " selected" : ""}>${n || t("all")}</option>`).join("")}</select>
        </label>
      </div>
    </div>`;
  }).join("") || `<div class="empty">${esc(t("board_empty"))}</div>`;
  const body = $("lineBody");
  body.querySelectorAll("[data-page]").forEach((b) =>
    b.addEventListener("click", () => {
      const dir = +b.dataset.page;
      if (b.dataset.to === "now") {
        state.band = "all";              // "now" must be inside the active filter
        state.jumpNow = dir;             // drawLine picks the page holding it
        state.lineScrolled = state.line; // and then scrolls it into view
        state.scrollNow = true;
      } else {
        state.page[dir] = (state.page[dir] || 0) + (b.dataset.to === "next" ? 1 : -1);
      }
      drawLine();
    }));
  body.querySelectorAll("[data-size]").forEach((s) =>
    s.addEventListener("change", (e) => {
      state.pageSize = +e.target.value;
      state.page = { 0: 0, 1: 0 };
      drawLine();
    }));
  body.querySelectorAll("tr.svc").forEach((tr) =>
    tr.addEventListener("click", () => openTrip(tr.dataset)));
  if (state.initialJump) {
    state.initialJump = false;
    state.lineScrolled = state.line;
    requestAnimationFrame(() =>
      body.querySelector("tr.upcoming")?.scrollIntoView({ block: "center" }));
  } else if (state.scrollNow) {
    state.scrollNow = false;
    requestAnimationFrame(() =>
      body.querySelector("tr.upcoming")?.scrollIntoView({ block: "center" }));
  }
}

/* ── trip drawer ───────────────────────────────────────── */
async function openTrip(dataset) {
  const { line, depart, trip, day } = dataset;
  $("drawerTitle").textContent = "…";
  $("drawerSub").textContent = t("loading_stops");
  $("drawerBody").innerHTML = "";
  $("drawer").classList.add("open");
  $("drawer").setAttribute("aria-hidden", "false");
  $("scrim").classList.add("open");
  try {
    const d = await json(`${API}/trip?` + qs({ line, depart, trip, day, live: 1 }));
    const colour = NET[d.line.network]?.color || "#888";
    const now = svcMinutes();
    const today = d.day === sydneyDate();
    const liveStops = d.stops.filter((s) => s.live != null).length;
    $("drawerTitle").innerHTML = `<span class="badge" style="background:${colour}">${esc(d.line.code)}</span>
      ${esc(d.trip || "")} · ${esc(d.clock)}`;
    $("drawerSub").textContent = `${d.headsign || ""} · ${d.service || ""} · ` +
      `${t("stops_title", d.stops.length)}` + (liveStops ? ` · ${t("pax_live")}` : "");
    $("drawerBody").innerHTML = `<div style="--accent:${colour}">` + d.stops.map((s) => {
      const eff = s.live ?? s.time;
      const past = today && eff < now - 1;
      return `<div class="stop${past ? " past" : ""}">
        <span class="h">${esc(s.live_clock || s.clock)}${s.live != null && s.live_clock !== s.clock
          ? `<span class="sched">${esc(s.clock)}</span>` : ""}</span>
        <span class="s">${esc(s.station)}</span>
        <span class="pf">${s.platform ? "P" + esc(s.platform) : ""}</span></div>`;
    }).join("") + `</div>`;
  } catch (e) {
    $("drawerBody").innerHTML = `<div class="empty err">${esc(t("err", e.message))}</div>`;
  }
}
const closeDrawer = () => {
  $("drawer").classList.remove("open");
  $("drawer").setAttribute("aria-hidden", "true");
  $("scrim").classList.remove("open");
};
$("drawerClose").addEventListener("click", closeDrawer);
$("scrim").addEventListener("click", closeDrawer);
$("refresh").addEventListener("click", () => { state.nextPoll = 0; refreshLive(); });

/* ── alerts ────────────────────────────────────────────── */
async function renderAlerts() {
  $("view").innerHTML =
    panel(`<div class="row spread"><h2>${esc(t("nav_alerts"))}</h2>
        <input type="search" id="aq" placeholder="${esc(t("alerts_ph"))}"
          style="border:1px solid var(--line2);background:rgba(0,0,0,.35);color:var(--fg);
          padding:7px 11px;border-radius:9px;font:inherit;font-size:13px;min-width:240px"></div>
      <div class="chips" id="aNet" style="margin-top:10px"></div>`) +
    `<div id="alist"><div class="splash"><div class="spin"></div>${esc(t("loading_alerts"))}</div></div>`;
  $("aq").addEventListener("input", (e) => { state.alertQ = e.target.value.trim(); drawAlerts(); });
  try { state.alerts = await json(`${API}/alerts`); }
  catch (e) { $("alist").innerHTML = `<div class="empty err">${esc(t("err", e.message))}</div>`; return; }
  drawAlerts();
}

function drawAlerts() {
  const data = state.alerts;
  if (!data) return;
  const counts = data.by_network || {};
  $("aNet").innerHTML = [`<button class="chip ${!state.alertNet ? "on" : ""}" data-net="">${esc(t("all"))}
      <span class="n">${data.count}</span></button>`]
    .concat(NET_ORDER.filter((k) => counts[k]).map((k) =>
      `<button class="chip ${state.alertNet === k ? "on" : ""}" data-net="${k}">
        <span class="sw" style="background:${NET[k].color}"></span>${esc(netName(k))}
        <span class="n">${counts[k]}</span></button>`)).join("");
  $("aNet").querySelectorAll("[data-net]").forEach((b) =>
    b.addEventListener("click", () => { state.alertNet = b.dataset.net || null; drawAlerts(); }));
  let items = data.alerts;
  if (state.alertNet) items = items.filter((a) => a.families.includes(state.alertNet));
  if (state.alertQ) {
    const needle = state.alertQ.toLowerCase();
    items = items.filter((a) => (a.title + a.body).toLowerCase().includes(needle)
      || a.lines.some((l) => l.toLowerCase().includes(needle)));
  }
  const fmt = (ts) => new Date(+ts * 1000).toLocaleString(LOCALE(),
    { timeZone: "Australia/Sydney", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  $("alist").innerHTML = items.length ? items.slice(0, 60).map((a, i) => {
    const chips = a.lines.slice(0, 5).map((l) => {
      const fam = familyOf(l);
      return `<a class="tag" href="#/line/${encodeURIComponent(l)}"
        style="border-color:${NET[fam]?.color || "#888"}66;color:${NET[fam]?.color || "#888"}">${esc(l)}</a>`;
    }).join(" ");
    const open = state.alertOpen.has(i);
    return `<div class="alert${open ? " open" : ""}" data-i="${i}">
      <div class="row"><span class="tag">${esc(t("alert_" + a.type))}</span><h4>${esc(a.title)}</h4></div>
      <div class="body">${esc(a.body)}</div>
      <div class="foot">${chips}${a.start && a.end
        ? `<span>${esc(fmt(a.start))} → ${esc(fmt(a.end))}</span>` : ""}</div>
      <button class="more">${esc(open ? t("collapse") : t("expand"))}</button></div>`;
  }).join("") : `<div class="empty">${esc(t("alerts_empty"))}</div>`;
  $("alist").querySelectorAll(".alert").forEach((node) => {
    const i = +node.dataset.i;
    node.querySelector(".more").addEventListener("click", () => {
      state.alertOpen.has(i) ? state.alertOpen.delete(i) : state.alertOpen.add(i);
      drawAlerts();
    });
  });
}
const familyOf = (id) => ({ CR: "CR", SM: "SM", SF: "SF", CCC: "SF", CRF: "SF",
  MFF: "SF", LR: "LR", SLR: "LR", PLR: "LR", NT: "LR" })[String(id || "").split("_")[0]] || "CR";

boot();
