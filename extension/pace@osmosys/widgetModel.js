// The shell widget's decisions as plain functions (no St, no Shell): what a card shows, where it may sit, what is remembered.

const COLOURS = ['green', 'amber', 'red', 'blue', 'grey'];
const MARGIN = 16;

function section(s) {
    const fill = typeof s.fill === 'number' ? Math.max(0, Math.min(100, Math.round(s.fill * 100))) : null;
    return {
        label: s.label ?? '',
        word: s.word ?? '',
        colour: COLOURS.includes(s.colour) ? s.colour : 'grey',
        big: s.big ?? '',
        unit: s.unit ?? '',
        fill,
        lines: s.lines ?? [],
    };
}

const plain = line => ({label: 'PACE', word: '', colour: 'grey', big: '', unit: '', fill: null, lines: [line]});

// status.json text → {week, project} for the card. paced's own `widget` key is the source; without one, one plain line.
export function widgetModel(json) {
    let s = null;
    try {
        s = json ? JSON.parse(json) : null;
    } catch {
        // garbled: same as nothing yet
    }
    if (!s)
        return {week: plain('Waiting for paced'), project: null};
    if (!s.widget?.week)
        return {week: plain(s.text || 'Waiting for paced'), project: null};
    return {week: section(s.widget.week), project: s.widget.project ? section(s.widget.project) : null};
}

// Keep the whole card inside the area (a work area: {x, y, width, height})
export function clampToArea(x, y, w, h, area) {
    return [
        Math.max(area.x, Math.min(x, area.x + area.width - w)),
        Math.max(area.y, Math.min(y, area.y + area.height - h)),
    ];
}

// The monitor under the card's centre; the first one when the card is off every monitor
export function monitorAt(x, y, w, h, monitors) {
    const cx = x + w / 2, cy = y + h / 2;
    return monitors.find(m => cx >= m.x && cx < m.x + m.width && cy >= m.y && cy < m.y + m.height) ?? monitors[0];
}

// Where to put the card: the remembered spot pulled back on screen, else the top right corner of the area
export function startPosition(saved, w, h, area) {
    if (saved && Number.isFinite(saved.x) && Number.isFinite(saved.y))
        return clampToArea(saved.x, saved.y, w, h, area);
    return clampToArea(area.x + area.width - w - MARGIN, area.y + MARGIN, w, h, area);
}

// shell-widget.json in Pace's state dir: whether the card is shown and where. The shell can drop the widget
// (lock screen disables the extension) and rebuild it afterwards from this.
export function parseSaved(text) {
    let o = null;
    try {
        o = JSON.parse(text);
    } catch {
        // junk reads as hidden
    }
    const num = v => (Number.isFinite(v) ? v : null);
    return {visible: o?.visible === true, x: num(o?.x), y: num(o?.y)};
}

export const serializeSaved = state => JSON.stringify({visible: !!state.visible, x: state.x ?? null, y: state.y ?? null});

// org.gnome.desktop.interface color-scheme: 'default' means the system's light look
export const isLight = scheme => scheme !== 'prefer-dark';
