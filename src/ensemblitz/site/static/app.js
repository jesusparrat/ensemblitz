// Minimal, optional behaviour: theme, language memory, favorite team, combinable filters,
// copy link, client-side SHA-256 verification, sortable tables, countdown.
// Without JavaScript every page reads in full.
(() => {
  const root = document.documentElement;

  // Theme: follows the system; the button stores the choice.
  document.querySelector(".theme")?.addEventListener("click", () => {
    const next = getComputedStyle(root).colorScheme === "dark" ? "light" : "dark";
    root.dataset.theme = next;
    try { localStorage.setItem("ens-theme", next); } catch (e) { /* private mode */ }
  });

  // Language: the switch is a plain link; remember the choice so the next visit opens in it.
  document.querySelector(".lang")?.addEventListener("click", (e) => {
    try { localStorage.setItem("ens-lang", e.currentTarget.dataset.lang); } catch (err) { /* private mode */ }
  });

  // Sliding indicator of the navigation (decorative).
  const nav = document.querySelector(".nav");
  const ind = nav && nav.querySelector(".ind");
  const cur = nav && nav.querySelector('[aria-current="page"], .parent');
  const place = (a) => {
    if (!a || !ind) return;
    ind.style.width = a.offsetWidth + "px";
    ind.style.transform = "translateX(" + a.offsetLeft + "px)";
  };
  if (nav) {
    place(cur);
    nav.querySelectorAll("a").forEach((a) => {
      a.addEventListener("mouseenter", () => place(a));
      a.addEventListener("focus", () => place(a));
    });
    nav.addEventListener("mouseleave", () => place(cur));
    window.addEventListener("resize", () => place(cur));
  }

  const es = document.documentElement.lang === "es";

  // Favorite team (ens-team) and combinable week filters (discrepancy, day, my team).
  const tools = document.querySelector(".tools");
  const controls = tools && tools.querySelector(".controls");
  const teamSelect = document.getElementById("fav-team");
  const games = Array.from(document.querySelectorAll(".game"));
  const groups = Array.from(document.querySelectorAll(".daygroup"));
  const emptyMsg = document.getElementById("filter-empty");

  if (games.length) {
    const state = { flag: false, day: null, team: false };
    let favTeam = "";
    let dynamicChips = false;

    const getChipsWrap = () => document.querySelector(".chips");
    const getChips = () => Array.from(document.querySelectorAll(".chip"));

    const matchesTeam = (g, tm) => Boolean(tm) && (g.dataset.home === tm || g.dataset.away === tm);

    const applyFilters = () => {
      let visibleCount = 0;
      games.forEach((g) => {
        const okFlag = !state.flag || g.dataset.flag === "1";
        const okDay = !state.day || g.dataset.day === state.day;
        const okTeam = !state.team || matchesTeam(g, favTeam);
        const show = okFlag && okDay && okTeam;
        g.hidden = !show;
        if (show) visibleCount += 1;
      });
      groups.forEach((d) => {
        d.hidden = !Array.from(d.querySelectorAll(".game")).some((g) => !g.hidden);
      });
      if (emptyMsg) emptyMsg.hidden = visibleCount > 0;
      const isAll = !state.flag && !state.day && !state.team;
      getChips().forEach((c) => {
        const f = c.dataset.f;
        let pressed = false;
        if (f === "all") pressed = isAll;
        else if (f === "flag") pressed = state.flag;
        else if (f === "team") pressed = state.team;
        else pressed = state.day === f;
        c.setAttribute("aria-pressed", String(pressed));
      });
    };

    const bindChip = (c) => {
      if (c.dataset.bound === "1") return;
      c.dataset.bound = "1";
      c.addEventListener("click", () => {
        const f = c.dataset.f;
        if (f === "all") {
          state.flag = false;
          state.day = null;
          state.team = false;
        } else if (f === "flag") {
          state.flag = !state.flag;
        } else if (f === "team") {
          state.team = !state.team;
        } else {
          state.day = state.day === f ? null : f;
        }
        applyFilters();
      });
    };

    getChips().forEach(bindChip);

    const makeChip = (f, label, count, pressed) => {
      const b = document.createElement("button");
      b.className = "chip";
      b.type = "button";
      b.dataset.f = f;
      b.setAttribute("aria-pressed", String(pressed));
      b.append(document.createTextNode(label));
      const n = document.createElement("span");
      n.className = "n";
      n.textContent = String(count);
      b.appendChild(n);
      bindChip(b);
      return b;
    };

    const syncTeam = (tm) => {
      favTeam = tm || "";
      let teamCount = 0;
      games.forEach((g) => {
        const hit = matchesTeam(g, favTeam);
        g.classList.toggle("is-fav", hit);
        if (hit) teamCount += 1;
      });
      let wrap = getChipsWrap();
      if (favTeam) {
        if (!wrap && controls) {
          wrap = document.createElement("div");
          wrap.className = "chips";
          wrap.setAttribute("role", "group");
          wrap.setAttribute("aria-label", es ? "Filtrar partidos" : "Filter games");
          wrap.appendChild(makeChip("all", es ? "Todos" : "All", games.length, true));
          wrap.appendChild(makeChip("team", es ? "Mi equipo" : "My team", teamCount, false));
          controls.appendChild(wrap);
          dynamicChips = true;
        }
        const teamChip = wrap && wrap.querySelector('.chip[data-f="team"]');
        if (teamChip) {
          teamChip.hidden = false;
          const n = teamChip.querySelector(".n");
          if (n) n.textContent = String(teamCount);
          bindChip(teamChip);
        }
      } else {
        state.team = false;
        if (wrap) {
          if (dynamicChips) {
            wrap.remove();
            dynamicChips = false;
          } else {
            const teamChip = wrap.querySelector('.chip[data-f="team"]');
            if (teamChip) {
              teamChip.hidden = true;
              teamChip.setAttribute("aria-pressed", "false");
            }
          }
        }
      }
      applyFilters();
    };

    if (teamSelect) {
      let saved = "";
      try { saved = localStorage.getItem("ens-team") || ""; } catch (e) { /* private mode */ }
      if (saved && Array.from(teamSelect.options).some((o) => o.value === saved)) {
        teamSelect.value = saved;
        syncTeam(saved);
      }
      teamSelect.addEventListener("change", () => {
        const val = teamSelect.value;
        try {
          if (val) localStorage.setItem("ens-team", val);
          else localStorage.removeItem("ens-team");
        } catch (e) { /* private mode */ }
        syncTeam(val);
      });
    }
  }

  // Copy link button on game pages (accessible aria-live confirmation).
  document.querySelectorAll("[data-copy-url]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const status = btn.parentElement && btn.parentElement.querySelector(".copy-status");
      const url = window.location.href;
      let ok = false;
      try {
        if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
          await navigator.clipboard.writeText(url);
          ok = true;
        }
      } catch (e) {
        ok = false;
      }
      if (!ok) {
        try {
          const ta = document.createElement("textarea");
          ta.value = url;
          ta.setAttribute("readonly", "");
          ta.style.position = "fixed";
          ta.style.opacity = "0";
          document.body.appendChild(ta);
          ta.select();
          ok = document.execCommand("copy");
          ta.remove();
        } catch (e) {
          ok = false;
        }
      }
      if (status) {
        status.textContent = ok ? (btn.dataset.copied || "") : (btn.dataset.copyFail || "");
      }
    });
  });

  // Client-side SHA-256 verification against embedded predictions/MANIFEST.json (zero network).
  const checker = document.getElementById("verify-checker");
  const fileInput = document.getElementById("verify-file");
  const resultBox = document.getElementById("verify-result");
  const manifestScript = document.getElementById("manifest-data");
  if (checker && fileInput && resultBox && manifestScript) {
    let manifestMap = {};
    try {
      manifestMap = JSON.parse(manifestScript.textContent || "{}");
    } catch (e) {
      manifestMap = {};
    }

    const renderMessage = (statusText, isMatch, details, noteText) => {
      resultBox.textContent = "";
      const head = document.createElement("p");
      head.className = "verify-status " + (isMatch ? "is-match" : "is-mismatch");
      head.textContent = statusText;
      resultBox.appendChild(head);
      if (details.length) {
        const dl = document.createElement("dl");
        dl.className = "facts";
        details.forEach(([k, v, codeClass]) => {
          const dt = document.createElement("dt");
          dt.textContent = k;
          const dd = document.createElement("dd");
          if (codeClass) {
            const c = document.createElement("code");
            c.className = codeClass;
            c.textContent = v;
            dd.appendChild(c);
          } else {
            dd.textContent = v;
          }
          dl.appendChild(dt);
          dl.appendChild(dd);
        });
        resultBox.appendChild(dl);
      }
      if (noteText) {
        const p = document.createElement("p");
        p.className = "small";
        p.textContent = noteText;
        resultBox.appendChild(p);
      }
    };

    fileInput.addEventListener("change", async () => {
      const file = fileInput.files && fileInput.files[0];
      if (!file) return;
      if (!(window.crypto && window.crypto.subtle && typeof window.crypto.subtle.digest === "function")) {
        renderMessage(checker.dataset.error || "Error", false, [], checker.dataset.unsupported || "");
        return;
      }
      try {
        const buf = await file.arrayBuffer();
        const digest = await window.crypto.subtle.digest("SHA-256", buf);
        const hex = Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
        const matches = Object.entries(manifestMap)
          .filter(([, h]) => String(h).toLowerCase() === hex)
          .map(([p]) => p);
        const rows = [
          [checker.dataset.lblFile || "File", file.name, null],
          [checker.dataset.lblSha || "SHA-256", hex, "hash"],
        ];
        if (matches.length) {
          rows.push([checker.dataset.lblPaths || "Path", matches.join(", "), "hash-path"]);
          renderMessage(
            checker.dataset.match || "Match",
            true,
            rows,
            checker.dataset.matchNote || ""
          );
        } else {
          renderMessage(
            checker.dataset.mismatch || "Mismatch",
            false,
            rows,
            checker.dataset.mismatchNote || ""
          );
        }
      } catch (e) {
        renderMessage(checker.dataset.error || "Error", false, [], String(e));
      }
    });
  }

  // Sortable tables with real buttons (keyboard and screen reader).
  document.querySelectorAll("table.sortable").forEach((table) => {
    const heads = Array.from(table.querySelectorAll("thead th"));
    heads.forEach((th, i) => {
      const label = th.textContent.trim();
      th.textContent = "";
      const b = document.createElement("button");
      b.type = "button";
      b.className = "sort";
      b.textContent = label;
      b.setAttribute("aria-label", (es ? "Ordenar por " : "Sort by ") + label);
      th.appendChild(b);
      b.addEventListener("click", () => {
        const dir = th.getAttribute("aria-sort") === "ascending" ? -1 : 1;
        heads.forEach((h) => h.removeAttribute("aria-sort"));
        th.setAttribute("aria-sort", dir === 1 ? "ascending" : "descending");
        const body = table.tBodies[0];
        const val = (r) => {
          const c = r.cells[i];
          const v = c.dataset.v !== undefined ? c.dataset.v : c.textContent.trim();
          const n = parseFloat(v.replace(",", "."));
          return Number.isNaN(n) ? v.toLowerCase() : n;
        };
        Array.from(body.rows)
          .sort((a, b2) => (val(a) > val(b2) ? dir : val(a) < val(b2) ? -dir : 0))
          .forEach((r) => body.appendChild(r));
        const live = document.getElementById("sort-live");
        if (live) {
          live.textContent = es
            ? "Tabla ordenada por " + label + (dir === 1 ? ", de menor a mayor." : ", de mayor a menor.")
            : "Table sorted by " + label + (dir === 1 ? ", ascending." : ", descending.");
        }
      });
    });
  });

  // Countdown to the next kickoff (the HTML already carries the kickoff time).
  const cd = document.querySelector("[data-kick]");
  if (cd) {
    const ms = new Date(cd.dataset.kick) - Date.now();
    if (ms > 0) {
      const h = Math.floor(ms / 36e5);
      const d = Math.floor(h / 24);
      cd.textContent = d ? d + "d " + String(h % 24).padStart(2, "0") + "h" : h + "h " + String(Math.floor((ms % 36e5) / 6e4)).padStart(2, "0") + "m";
      const lab = document.querySelector("[data-kick-label]");
      if (lab) lab.textContent = lab.dataset.kickLabel;
    }
  }
})();
