(function () {
    function getCookie(name) {
        var match = document.cookie.match(
            new RegExp("(?:^|; )" + name.replace(/([.$?*|{}()[\]\\/+^])/g, "\\$1") + "=([^;]*)")
        );
        return match ? decodeURIComponent(match[1]) : "";
    }

    document.body.addEventListener("htmx:configRequest", function (event) {
        var verb = (event.detail.verb || "").toLowerCase();
        if (verb && verb !== "get") {
            event.detail.headers["X-CSRFToken"] = getCookie("csrftoken");
        }
    });

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

    /*
     * Image protection (deterrent): block image context menu / drag / open-in-new-tab
     * gestures without disabling normal page navigation or text selection.
     */
    function isProtectedMedia(node) {
        if (!node || node.nodeType !== 1) {
            return false;
        }
        // Never block clicks / context menu on links (mailto, tel, http).
        if (node.closest && node.closest("a[href]")) {
            return false;
        }
        if (node.matches("img, picture, svg.media-protected")) {
            return true;
        }
        return Boolean(node.closest && node.closest("img, picture, svg.media-protected"));
    }

    function hardenImages(root) {
        var scope = root && root.querySelectorAll ? root : document;
        scope.querySelectorAll("img").forEach(function (img) {
            img.setAttribute("draggable", "false");
            // Avoid leaking direct file names via the native tooltip where unused.
            if (!img.getAttribute("title")) {
                img.removeAttribute("title");
            }
        });
    }

    function onProtectedGesture(event) {
        if (isProtectedMedia(event.target)) {
            event.preventDefault();
        }
    }

    document.addEventListener("contextmenu", onProtectedGesture, true);
    document.addEventListener("dragstart", onProtectedGesture, true);

    hardenImages(document);
    document.addEventListener("DOMContentLoaded", function () {
        hardenImages(document);
    });
    document.body.addEventListener("htmx:afterSettle", function (event) {
        hardenImages(event.target);
    });
})();
