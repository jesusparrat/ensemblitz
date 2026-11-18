document.documentElement.classList.add("js");
try {
  var t = localStorage.getItem("ens-theme");
  if (t === "light" || t === "dark") document.documentElement.dataset.theme = t;
  // Language: a saved choice wins over the page that was opened, so the switch persists.
  var want = localStorage.getItem("ens-lang");
  var here = document.documentElement.lang;
  if ((want === "es" || want === "en") && want !== here) {
    var alt = document.querySelector('link[rel="alternate"][hreflang="' + want + '"]');
    if (alt) location.replace(alt.href);
  }
} catch (e) {}
