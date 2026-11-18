// Minimal, optional behaviour: theme, language memory, filters, sortable tables, countdown.
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

  // Week filters (the markup only exists when there is something to filter).
  const chips = Array.from(document.querySelectorAll(".chip"));
  const games = Array.from(document.querySelectorAll(".game"));
  const groups = Array.from(document.querySelectorAll(".daygroup"));
  chips.forEach((c) => c.addEventListener("click", () => {
    chips.forEach((x) => x.setAttribute("aria-pressed", String(x === c)));
    const f = c.dataset.f;
    games.forEach((g) => {
      g.hidden = !(f === "all" || (f === "flag" && g.dataset.flag === "1") || g.dataset.day === f);
    });
    groups.forEach((d) => { d.hidden = !Array.from(d.querySelectorAll(".game")).some((g) => !g.hidden); });
  }));

  // Sortable tables with real buttons (keyboard and screen reader).
  const es = document.documentElement.lang === "es";
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
