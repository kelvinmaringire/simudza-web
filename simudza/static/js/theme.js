(function () {
    var systemDark = window.matchMedia("(prefers-color-scheme: dark)");

    var saved = null;
    try {
        saved = localStorage.getItem("theme");
    } catch (e) {}

    function apply(theme) {
        document.documentElement.setAttribute("data-theme", theme);

        document.querySelectorAll("input.theme-controller").forEach(function (el) {
            el.checked = theme === "dark";
        });
    }

    // An explicit choice wins; otherwise follow the operating system.
    apply(saved || (systemDark.matches ? "dark" : "light"));

    // The inputs do not exist yet at this point in <head>.
    document.addEventListener("DOMContentLoaded", function () {
        apply(document.documentElement.getAttribute("data-theme"));
    });

    // Track the OS only while the visitor has not chosen for themselves.
    systemDark.addEventListener("change", function (e) {
        if (!saved) {
            apply(e.matches ? "dark" : "light");
        }
    });

    document.addEventListener("change", function (e) {
        if (!e.target.classList.contains("theme-controller")) {
            return;
        }

        saved = e.target.checked ? "dark" : "light";
        apply(saved);

        try {
            localStorage.setItem("theme", saved);
        } catch (e) {}
    });
})();