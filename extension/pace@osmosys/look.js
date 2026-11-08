// status.json → what the top bar draws (B1 in docs/design.html). Pure: no Shell imports, so gjs can test it.

export const VERSION = 1;

// icon → marker: 'dot' is drawn as a filled circle; the rest are glyphs
const MARKERS = {dot: 'dot', triangle: '▲', ring: '◌', check: '✓', circle: '○'};

const QUIET = {marker: '○', colour: 'grey', dim: true, verdict: null, asOf: null};

export function look(json) {
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
