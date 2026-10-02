// Interactive engine shared by the three KAN-28 mock sets.
//
// Filter values are seeded from config/jobs.local.json (title_match.level,
// title_match.domain, locations.remote). Jobs, salaries and dates are illustrative.
// Each set supplies only its own `render(S, ui)`; state, fake API, and events live here.
(function () {
  const FILTERS = {
    Title: ["Engineering Manager", "Sr. Engineering Manager", "Senior Engineering Manager",
      "Head of Engineering", "Director of Engineering", "Engineering Director"],
    Domain: ["Mobile", "iOS", "Android", "App Experience", "Client", "Consumer App", "Engineering"],
    Location: ["Remote", "Work from home", "WFH", "Anywhere", "Distributed",
      "United States remote", "US remote", "Remote US", "Remote-US"],
  };
  const CATS = Object.keys(FILTERS);

  // `age` = hours since posted (mock "now" is Oct 1, 2026 9pm). Newest first. < 48h gets "New".
  const JOBS = [
    { title: "Software Engineering Manager, Mobile Products", company: "NerdWallet", location: "Remote (US)",
      salary: "$210k – $245k", age: 3, url: "https://jobs.ashbyhq.com/nerdwallet/3973abc7-1f2e" },
    { title: "Engineering Manager, Android Notifications", company: "Discord", location: "Remote",
      salary: "$198k – $223k", age: 9, url: "https://job-boards.greenhouse.io/discord/jobs/8537955002" },
    { title: "Director of Engineering, Trading Apps (iOS)", company: "Alpaca", location: "Remote – North America",
      salary: "", age: 28, url: "https://job-boards.greenhouse.io/alpaca/jobs/6007223004" },
    { title: "Head of Engineering, Consumer App", company: "Calm", location: "Work from home (US)",
      salary: "$240k – $280k", age: 40, url: "https://jobs.lever.co/calm/5b1e7c20-91aa" },
    { title: "Engineering Manager, Client Experience", company: "Apollo.io", location: "Remote, United States",
      salary: "$185k – $220k", age: 52, url: "https://job-boards.greenhouse.io/apolloio/jobs/6173927004" },
    { title: "Sr. Engineering Manager, Client Platform", company: "Cribl", location: "US Remote",
      salary: "", age: 76, url: "https://cribl.io/job-detail/?gh_jid=6173732004" },
    { title: "Senior Engineering Manager, App Experience", company: "Duolingo", location: "Remote US",
      salary: "$215k – $260k", age: 98, url: "https://job-boards.greenhouse.io/duolingo/jobs/7123456" },
    { title: "Engineering Director, Mobile", company: "Strava", location: "Anywhere",
      salary: "$230k – $270k", age: 120, url: "https://jobs.ashbyhq.com/strava/9c4d1f02-77be" },
    { title: "Engineering Manager, Android SDK", company: "Customer.io", location: "Distributed (Americas)",
      salary: "$170k – $200k", age: 150, url: "https://job-boards.greenhouse.io/customerio/jobs/8104418" },
    { title: "Director of Engineering, Database Excellence", company: "GitLab", location: "Remote, Canada / US",
      salary: "", age: 170, url: "https://job-boards.greenhouse.io/gitlab/jobs/8853843002" },
    { title: "Head of Engineering, iOS", company: "Headspace", location: "WFH – US",
      salary: "$250k – $290k", age: 210, url: "https://jobs.lever.co/headspace/0d33ab19-5c10" },
    { title: "Engineering Manager, Mobile Growth", company: "Robinhood", location: "Remote-US",
      salary: "$188k – $220k", age: 300, url: "https://job-boards.greenhouse.io/robinhood/jobs/6402291" },
    { title: "Senior Engineering Manager, Consumer App", company: "Plaid", location: "United States Remote",
      salary: "", age: 400, url: "https://jobs.lever.co/plaid/7a0f6e55-2d9c" },
  ];

  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const NOW = Date.UTC(2026, 9, 1, 21);
  function posted(age) {
    if (age < 1) return "Just now";
    if (age < 24) return Math.round(age) + "h ago";
    if (age < 48) return "Yesterday";
    if (age < 168) return Math.floor(age / 24) + "d ago";
    const d = new Date(NOW - age * 3600e3);
    return MONTHS[d.getUTCMonth()] + " " + d.getUTCDate();
  }
  const group = (age) => age < 24 ? "Today" : age < 48 ? "Yesterday" : age < 168 ? "This week" : "Earlier";

  // Fake server: OR inside a category, AND across categories. Title/Domain match the
  // listing title, Location matches the listing location (same as the scraper's config).
  const hay = (j, cat) => (cat === "Location" ? j.location : j.title).toLowerCase();
  const matches = (j, sel) => CATS.every((c) => !sel[c].length || sel[c].some((v) => hay(j, c).includes(v.toLowerCase())));

  const S = {
    sel: { Title: [], Domain: [], Location: [] },
    open: null, draft: [], query: "", enter: false,
    status: "ok", results: JOBS.slice(), force: null, failNext: false,
    device: "phone", toast: "", applied: "", resetList: false,
  };
  S.applied = JSON.stringify(S.sel);
  let cfg, col, stage, token = 0, timer = null, debounce = null, toastTimer = null;

  const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");
  const total = () => CATS.reduce((n, c) => n + S.sel[c].length, 0);

  const ui = {
    FILTERS, cats: CATS, esc, total, posted: (j) => posted(j.age), group: (j) => group(j.age),
    isNew: (j) => j.age < 48,
    newTag: '<span class="new">New</span>',
    host: (j) => j.url.replace(/^https?:\/\//, "").split("/")[0],
    url: (j) => j.url.replace(/^https?:\/\//, ""),
    status: () => S.force || S.status,
    jobs: () => (S.force === "empty" ? [] : S.results),
    sub() {
      const st = ui.status();
      if (st === "loading") return "Loading…";
      if (st === "error") return "Couldn't refresh";
      const n = ui.jobs().length;
      return n + (n === 1 ? " job" : " jobs") + " · Newest first";
    },
    // Pills wrap onto extra rows with "Clear all" inline after the last pill. Each set can cap
    // the height in its own CSS (the area then scrolls vertically).
    pills() {
      const items = CATS.flatMap((cat) => S.sel[cat].map((v) =>
        `<span class="pill">${esc(v)}<button class="x" data-act="rm" data-cat="${cat}" data-val="${esc(v)}" aria-label="Remove ${esc(v)}">×</button></span>`)).join("");
      return items ? `<div class="pillwrap" data-scroll="pills" role="group" aria-label="Active filters">${items}<button class="clear-all" data-act="clearAll">Clear all</button></div>` : "";
    },
    errorBlock: () => `<div class="state"><div class="glyph err">!</div><h3>Couldn't load jobs</h3>
      <p>Check your connection and try again. Your filters are saved.</p>
      <button class="btn primary" data-act="retry">Try again</button></div>`,
    emptyBlock: () => `<div class="state"><div class="glyph">0</div><h3>No jobs match</h3>
      <p>${total() ? "Try removing a filter to see more results." : "Nothing posted yet. Check back soon."}</p>
      ${total() ? '<button class="btn outline" data-act="clearAll">Clear all filters</button>' : ""}</div>`,
  };

  // ----- fake API -----
  function load() {
    clearTimeout(timer); clearTimeout(debounce);
    const t = ++token;
    S.force = null; S.status = "loading"; S.resetList = true; syncCtl(); paint();
    timer = setTimeout(() => {
      if (t !== token) return; // stale response
      if (S.failNext) { S.failNext = false; S.status = "error"; }
      else {
        S.results = JOBS.filter((j) => matches(j, S.sel)).sort((a, b) => a.age - b.age);
        S.status = S.results.length ? "ok" : "empty";
        S.applied = JSON.stringify(S.sel);
      }
      syncCtl(); paint();
    }, 900);
  }
  const changed = () => JSON.stringify(S.sel) !== S.applied;
  const toggleIn = (arr, v) => { const i = arr.indexOf(v); i < 0 ? arr.push(v) : arr.splice(i, 1); };
  const close = () => { S.open = null; };

  // ----- actions (bound via data-act) -----
  const A = {
    open(el) {
      const cat = el.dataset.cat;
      if (S.open === cat) return cfg.live ? close() : A.done();
      if (S.open && !cfg.live) S.sel[S.open] = S.draft.slice(); // switching: keep what was picked
      S.open = cat; S.draft = S.sel[cat].slice(); S.query = ""; S.enter = true;
    },
    toggle(el) {
      if (cfg.live) { toggleIn(S.sel[S.open], el.dataset.val); clearTimeout(debounce); debounce = setTimeout(load, 450); }
      else toggleIn(S.draft, el.dataset.val);
    },
    clearDraft() {
      if (cfg.live) { S.sel[S.open] = []; clearTimeout(debounce); debounce = setTimeout(load, 450); }
      else S.draft = [];
    },
    done() { if (!S.open) return; if (!cfg.live) S.sel[S.open] = S.draft.slice(); close(); changed() ? load() : 0; },
    cancel() { close(); },
    scrim() { cfg.live ? close() : (cfg.scrimApplies ? A.done() : A.cancel()); },
    rm(el) { toggleIn(S.sel[el.dataset.cat], el.dataset.val); load(); },
    clearAll() { CATS.forEach((c) => (S.sel[c] = [])); close(); load(); },
    retry() { load(); },
    openlink(el) {
      S.toast = "Opens " + el.dataset.val + " in your browser";
      clearTimeout(toastTimer); toastTimer = setTimeout(() => { S.toast = ""; paint(); }, 2200);
    },
  };

  // ----- painting -----
  function paint() {
    if (!col) return;
    const ae = document.activeElement;
    let fk = null, pos = null;
    if (ae && col.contains(ae) && ae.dataset.act) { fk = [ae.dataset.act, ae.dataset.cat || "", ae.dataset.val || ""]; pos = ae.selectionStart; }
    const scrolls = {};
    col.querySelectorAll("[data-scroll]").forEach((el) => (scrolls[el.dataset.scroll] = [el.scrollTop, el.scrollLeft]));
    if (S.resetList) delete scrolls.list;

    col.innerHTML = cfg.render(S, ui) + (S.toast ? `<div class="toast" role="status">${esc(S.toast)}</div>` : "");

    col.querySelectorAll("[data-scroll]").forEach((el) => { if (scrolls[el.dataset.scroll] != null) { el.scrollTop = scrolls[el.dataset.scroll][0]; el.scrollLeft = scrolls[el.dataset.scroll][1]; } });
    if (fk) {
      const el = [...col.querySelectorAll("[data-act]")].find((x) => x.dataset.act === fk[0] && (x.dataset.cat || "") === fk[1] && (x.dataset.val || "") === fk[2]);
      if (el) { el.focus({ preventScroll: true }); if (pos != null && el.setSelectionRange) try { el.setSelectionRange(pos, pos); } catch (e) {} }
    }
    S.enter = false;
    if (S.status !== "loading") S.resetList = false;
  }

  function frame() {
    const bar = '<div class="statusbar"><span>9:41</span><span>5G ▮▮▮</span></div>';
    stage.innerHTML = S.device === "phone"
      ? `<div class="phone">${bar}<div class="screen"><div class="col" id="app"></div></div></div>`
      : `<div class="browser"><div class="bar"><i></i><i></i><i></i><span>jobs.example.com</span></div><div class="screen"><div class="col" id="app"></div></div></div>`;
    col = stage.querySelector("#app");
    document.body.classList.toggle("is-web", S.device === "web");
    paint();
  }

  // ----- mock page chrome -----
  function syncCtl() {
    document.querySelectorAll("[data-ctl]").forEach((b) => {
      const [k, v] = b.dataset.ctl.split(":");
      b.setAttribute("aria-pressed", String(k === "device" ? S.device === v : (S.force || "live") === v));
    });
    const f = document.getElementById("failNext"); if (f) f.checked = S.failNext;
  }

  function start(config) {
    cfg = config;
    const sets = [["a", "set-a-dropdown-cards.html", "Set A · Dropdowns + cards"],
      ["b", "set-b-filter-sheet-feed.html", "Set B · Bottom sheet + dense feed"],
      ["c", "set-c-inline-panel-rows.html", "Set C · Inline panel + compact rows"]];
    document.getElementById("root").innerHTML = `
      <div class="doc">
        <nav class="sets">${sets.map(([k, f, n]) => `<a href="${f}" ${k === cfg.id ? 'aria-current="page"' : ""}>${n}</a>`).join("")}<a href="index.html">Overview</a></nav>
        <header><h1>KAN-28 · ${esc(cfg.title)}</h1><p>${cfg.intro}</p>
          <ul class="tradeoffs">${cfg.tradeoffs.map((t) => `<li>${t}</li>`).join("")}</ul></header>
        <section class="controls" aria-label="Mock controls">
          <div class="grp"><span class="lbl">Device</span><div class="seg">
            <button data-ctl="device:phone">Phone (iOS / Android)</button><button data-ctl="device:web">Web</button></div></div>
          <div class="grp"><span class="lbl">Force state</span><div class="seg">
            ${["live", "loading", "error", "empty"].map((s) => `<button data-ctl="state:${s}">${s[0].toUpperCase() + s.slice(1)}</button>`).join("")}</div></div>
          <label><input type="checkbox" id="failNext"> Next request fails</label>
        </section>
        <div class="stagewrap"><div id="stage"></div>
          <aside class="notes"><h2>Try this</h2><ol>${cfg.tryIt.map((t) => `<li>${t}</li>`).join("")}</ol></aside></div>
      </div>`;
    stage = document.getElementById("stage");

    stage.addEventListener("click", (e) => {
      const el = e.target.closest("[data-act]");
      if (!el || !stage.contains(el) || !A[el.dataset.act]) return;
      A[el.dataset.act](el); paint();
    });
    stage.addEventListener("input", (e) => {
      if (e.target.dataset.act === "query") { S.query = e.target.value; paint(); }
    });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && S.open) { A.cancel(); paint(); } });
    document.querySelector(".controls").addEventListener("click", (e) => {
      const b = e.target.closest("[data-ctl]"); if (!b) return;
      const [k, v] = b.dataset.ctl.split(":");
      if (k === "device") { S.device = v; frame(); }
      else { S.force = v === "live" ? null : v; close(); paint(); }
      syncCtl();
    });
    document.getElementById("failNext").addEventListener("change", (e) => (S.failNext = e.target.checked));
    syncCtl(); frame();
  }

  window.KAN28 = { start };
})();
