(function () {
    "use strict";

    document.querySelectorAll(".toast").forEach(function (toast) {
        var close = function () { toast.remove(); };
        toast.querySelector(".toast-close").addEventListener("click", close);
        if (!toast.classList.contains("is-warning") && !toast.classList.contains("is-error")) {
            setTimeout(close, 7000);
        }
    });

    var sidebar = document.getElementById("sidebar");
    var menuToggle = document.querySelector(".menu-toggle");
    if (sidebar && menuToggle) {
        menuToggle.addEventListener("click", function () {
            var open = sidebar.classList.toggle("is-open");
            menuToggle.setAttribute("aria-expanded", String(open));
            menuToggle.textContent = open ? "Close" : "Menu";
        });
    }

    document.querySelectorAll(".toggle-config").forEach(function (button) {
        button.addEventListener("click", function () {
            var row = document.getElementById(button.getAttribute("aria-controls"));
            var open = row.hidden;
            row.hidden = !open;
            button.setAttribute("aria-expanded", String(open));
            button.textContent = open ? "Hide" : "Config";
        });
    });

    if (window.ClipboardJS) {
        var clipboard = new ClipboardJS(".copy-button");
        clipboard.on("success", function (event) {
            var button = event.trigger;
            button.textContent = "Copied";
            button.classList.add("is-done");
            event.clearSelection();
            setTimeout(function () {
                button.textContent = "Copy";
                button.classList.remove("is-done");
            }, 1800);
        });
    }
})();
