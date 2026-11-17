// Comportamiento mínimo y opcional: tema, filtros, tablas ordenables, cuenta atrás. Sin JS la página se lee entera.
(() => {
  const root = document.documentElement;

  // Tema: respeta el del sistema; el botón fija la elección.
  document.querySelector(".theme")?.addEventListener("click", () => {
    const next = getComputedStyle(root).colorScheme === "dark" ? "light" : "dark";
    root.dataset.theme = next;
    try { localStorage.setItem("ens-theme", next); } catch (e) { /* modo privado */ }
  });

  // Indicador deslizante de la navegación (decorativo).
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

  // Filtros de la jornada.
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

  // Tablas ordenables con botones reales (teclado y lector de pantalla).
  document.querySelectorAll("table.sortable").forEach((table) => {
    const heads = Array.from(table.querySelectorAll("thead th"));
    heads.forEach((th, i) => {
      const label = th.textContent.trim();
      th.textContent = "";
      const b = document.createElement("button");
      b.type = "button";
      b.className = "sort";
      b.textContent = label;
      b.setAttribute("aria-label", "Ordenar por " + label);
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
        if (live) live.textContent = "Tabla ordenada por " + label + (dir === 1 ? ", de menor a mayor." : ", de mayor a menor.");
      });
    });
  });

  // Cuenta atrás al próximo partido (el HTML ya trae la hora de saque).
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

  // Marcador: los dígitos giran una vez al entrar en pantalla, como un tablero de estadio.
  if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches && "IntersectionObserver" in window) {
    const io = new IntersectionObserver((es) => es.forEach((e) => {
      if (!e.isIntersecting) return;
      io.unobserve(e.target);
      e.target.querySelectorAll("b[data-v]").forEach((b, k) => {
        const end = b.dataset.v;
        let n = 0;
        const t = setInterval(() => {
          b.textContent = ++n < 6 ? String(Math.floor(Math.random() * 40)) : end;
          if (n >= 6) clearInterval(t);
        }, 45 + k * 15);
      });
    }), { threshold: 0.6 });
    document.querySelectorAll(".s").forEach((s) => io.observe(s));
  }
})();
