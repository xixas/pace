// status.json → what the top bar draws (B1 in docs/design.html). Pure: no Shell imports, so gjs can test it.

export const VERSION = 1;

// icon → marker: 'dot' is drawn as a filled circle; the rest are glyphs
const MARKERS = {dot: 'dot', triangle: '▲', ring: '◌', check: '✓', circle: '○'};

// paced polls every 5 min and rewrites status.json each time; 3 missed polls means it has stopped
export const STALE_MS = 15 * 60e3;

const QUIET = {marker: '○', colour: 'grey', dim: true, verdict: null, asOf: null};

// now (ms): when given, numbers older than STALE_MS are greyed with their time, the way OFFLINE is
export function look(json, now = null) {
    let s = null;
    try {
        s = json === null ? null : JSON.parse(json);
    } catch {
        // paced writes atomically, so this is a hand-edited or foreign file: show nothing rather than guess
    }
    if (!s?.state)
        return {...QUIET, state: 'none', text: 'Pace'};
    if (s.version !== VERSION)
        return {...QUIET, state: 'skew', text: 'Update Pace'};
    const at = s.as_of ? new Date(s.as_of) : null; // naive local ISO, as paced writes it
    if (now !== null && at && s.state !== 'offline' && now - at.getTime() > STALE_MS) {
        const hhmm = `${String(at.getHours()).padStart(2, '0')}:${String(at.getMinutes()).padStart(2, '0')}`;
        return {...QUIET, state: 'stale', text: `${s.text} · ${hhmm}`, verdict: s.verdict, asOf: s.as_of};
    }
    return {
        state: s.state,
        marker: MARKERS[s.icon] ?? MARKERS.dot,
        colour: s.colour,
        dim: s.colour === 'grey',
        text: s.text,
        verdict: s.verdict,
        asOf: s.as_of,
    };
}
