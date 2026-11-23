// The week runway (direction D), a Canvas port of drawRunway in extension/pace@osmosys/menu.js: a 6 px track, the
// lighter pay-safe band from the pay line to the end, the pending day as a dashed ghost, then the fill.
import QtQuick
import org.kde.kirigami as Kirigami

Canvas {
    id: canvas
    required property var bar
    readonly property int track: 6
    // GNOME draws white on its dark menu; here the theme's text colour, so light and dark Plasma themes both work
    readonly property color ink: Kirigami.Theme.textColor
    function tint(a) {
        return "rgba(" + Math.round(ink.r * 255) + "," + Math.round(ink.g * 255) + "," + Math.round(ink.b * 255) + "," + a + ")";
    }
    onInkChanged: requestPaint()
    implicitHeight: 14
    onBarChanged: requestPaint()
    onWidthChanged: requestPaint()

    function rr(ctx, x0, x1, y, h, r) {
        ctx.beginPath();
        ctx.moveTo(x0 + r, y);
        ctx.lineTo(x1 - r, y);
        ctx.arc(x1 - r, y + r, r, -Math.PI / 2, Math.PI / 2);
        ctx.lineTo(x0 + r, y + h);
        ctx.arc(x0 + r, y + r, r, Math.PI / 2, 3 * Math.PI / 2);
        ctx.closePath();
    }

    onPaint: {
        var ctx = getContext("2d");
        var w = width, h = height, r = bar;
        ctx.reset();
        if (!r || w <= 0)
            return;
        var y = (h - track) / 2, rad = track / 2;
        rr(ctx, 0, w, y, track, rad);
        ctx.fillStyle = tint(0.12);
        ctx.fill();
        ctx.save();
        rr(ctx, 0, w, y, track, rad);
        ctx.clip();
        var bx = Math.round(w * r.band);
        if (bx < w) {
            ctx.fillStyle = r.emphasis ? "rgba(255,123,99,0.28)" : tint(0.2);
            ctx.fillRect(bx, y, w - bx, track);
            ctx.fillStyle = r.emphasis ? "rgba(255,123,99,1)" : tint(0.55);
            ctx.fillRect(bx, y, 1, track);
        }
        ctx.restore();
        if (r.ghost) {
            var g0 = Math.round(w * r.ghost[0]), g1 = Math.round(w * r.ghost[1]);
            ctx.strokeStyle = "#78aeed";
            ctx.lineWidth = 1;
            ctx.setLineDash([2.5, 2]);
            rr(ctx, g0 + 0.5, Math.max(g1 - 0.5, g0 + 1.5), y + 0.5, track - 1, rad - 0.5);
            ctx.stroke();
            ctx.setLineDash([]);
        }
        if (r.fill > 0) {
            ctx.fillStyle = {red: "#ff7b63", green: "#57e389", grey: tint(0.4)}[r.ink] || tint(0.82);
            rr(ctx, 0, Math.min(w, Math.max(track, w * r.fill)), y, track, rad);
            ctx.fill();
        }
    }
}
