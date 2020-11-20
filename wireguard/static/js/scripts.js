$(document).ready(function () {
    $("button.show-config").click(function (e) {
        e.preventDefault();
        $(this).find("span").text(function (i, v) {
            return v === "Show Config" ? "Hide Config" : "Show Config";
        });
        $(this).next().next().next().find(".item").fadeToggle();
    });

    $("button.show-qrcode").click(function (e) { e.preventDefault();
        e.preventDefault();
        $(this).find("span").text(function (i, v) {
            return v === "Show QR Code" ? "Hide QR Code" : "Show QR Code";
        });
        $(this).parent().prev().prev('.qr').fadeToggle(200);
    });

    $("#modalShow").click(function() {
        $(".modal").addClass("is-active");
    });

    $("#modalClose").click(function() {
        $(".modal").removeClass("is-active");
    });

    let clipboard = new ClipboardJS('.copy-clipboard');

    clipboard.on('success', function(e) {
        $('.notification-copied').fadeIn().fadeOut(5000);

        e.clearSelection();
    });

    $(".navbar-link").click(function () {
        $(this).next().toggleClass("dropdown-hidden");
    })

    $(".navbar-burger").click(function() {

        // Toggle the "is-active" class on both the "navbar-burger" and the "navbar-menu"
        $(".navbar-burger").toggleClass("is-active");
        $(".navbar-menu").toggleClass("is-active");

    });
});
