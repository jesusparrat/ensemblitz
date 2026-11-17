// Minimal behaviour: sortable tables. Everything else is plain HTML/CSS.
document.querySelectorAll("table.sortable").forEach((table) => {
  const heads = table.querySelectorAll("thead th");
  heads.forEach((th, i) => {
    th.addEventListener("click", () => {
      const dir = th.dataset.dir === "1" ? -1 : 1;
      heads.forEach((h) => delete h.dataset.dir);
      th.dataset.dir = String(dir);
      const body = table.tBodies[0];
      const rows = Array.from(body.rows);
      const val = (r) => {
        const c = r.cells[i];
        const v = c.dataset.v !== undefined ? c.dataset.v : c.textContent.trim();
        const n = parseFloat(v.replace(",", "."));
        return Number.isNaN(n) ? v.toLowerCase() : n;
      };
      rows.sort((a, b) => (val(a) > val(b) ? dir : val(a) < val(b) ? -dir : 0));
      rows.forEach((r) => body.appendChild(r));
    });
  });
});
