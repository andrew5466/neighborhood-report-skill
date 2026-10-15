// Map Lite data retrieval: read the Matrix results grid as compact tab-separated lines, 12 rows per call
// (browser tools truncate long results; about 45 characters per listing).
// Run with the browser's javascript tool on a Matrix Results page after a speed-bar search of comma-separated MLS
// numbers. First call as is; if the output ends with "#more <n>", set window.MLSTART = <n> and run it again.
// Columns: MLS, St (A active / R rented / P pending...), LP (list price, digits), PER (M month / Y year),
// F (F furnished / U unfurnished / O optional), beds, full baths, half baths, sq ft, style code, year built.
// Save every chunk to one file (append) and run: python3 -I ingest_matrix.py "<client folder>" grid.tsv
(() => {
  const WANT = ["ML #", "St", "LP$", "PER", "F$", "#Beds", "#FB", "#HB", "SqFt LA", "Style", "YR"];
  const start = window.MLSTART || 0, size = 12;
  for (const t of document.querySelectorAll("table")) {
    const rows = [...t.querySelectorAll("tr")];
    const hi = rows.findIndex((r) => [...r.cells].some((c) => c.innerText.trim() === "ML #"));
    if (hi < 0) continue;
    const head = [...rows[hi].cells].map((c) => c.innerText.trim());
    const idx = WANT.map((w) => head.indexOf(w));
    const all = [];
    for (const r of rows.slice(hi + 1)) {
      const cells = [...r.cells].map((c) => c.innerText.replace(/\s+/g, " ").replace(/^¤/, "").trim());
      if (!/^A\w?\d{7,}$/.test(cells[idx[0]] || "")) continue;
      const v = idx.map((i) => (i < 0 ? "" : cells[i] || ""));
      v[2] = v[2].replace(/[$,]/g, ""); v[3] = v[3].slice(0, 1); v[4] = v[4].slice(0, 1); v[8] = v[8].replace(/,/g, "");
      all.push(v.join("\t"));
    }
    if (!all.length) continue;
    const chunk = all.slice(start, start + size);
    const out = start ? chunk : ["#seen " + new Date().toISOString().slice(0, 10), "MLS\tSt\tLP\tPER\tF\tBeds\tFB\tHB\tSqFt\tStyle\tYR", ...chunk];
    if (start + size < all.length) out.push("#more " + (start + size));
    return out.join("\n");
  }
  return "#error no Matrix results grid on this page";
})();
