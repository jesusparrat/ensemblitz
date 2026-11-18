document.documentElement.classList.add("js");
try { var t = localStorage.getItem("ens-theme"); if (t === "light" || t === "dark") document.documentElement.dataset.theme = t; } catch (e) {}
