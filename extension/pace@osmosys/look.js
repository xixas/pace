// status.json → what the top bar and the dropdown draw (B1-B6, B12, C10, C12 in docs/design.html).
// Pure: no Shell imports, so gjs can test it.

export const VERSION = 1;

// icon → marker: 'dot' is drawn as a filled circle; the rest are glyphs
const MARKERS = {dot: 'dot', triangle: '▲', ring: '◌', check: '✓', circle: '○'};

// Fallback when status.json has no stale_after: paced polls every 5 min, 3 missed polls means it has stopped
export const STALE_MS = 15 * 60e3;

const QUIET = {marker: '○', colour: 'grey', dim: true, verdict: null, asOf: null};

const hhmm = d => `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;

function parse(json) {
    try {
        return json === null ? null : JSON.parse(json);
    } catch {
        // paced writes atomically, so this is a hand-edited or foreign file: show nothing rather than guess
        return null;
    }
}

// now (ms): when given, numbers past stale_after are greyed with their time, the way OFFLINE is
export function look(json, now = null) {
    const s = parse(json);
    if (!s?.state)
        return {...QUIET, state: 'none', text: 'Pace'};
    if (s.version !== VERSION)
        return {...QUIET, state: 'skew', text: 'Update Pace'};
    const at = s.as_of ? new Date(s.as_of) : null; // naive local ISO, as paced writes it
    const staleAt = s.stale_after ? new Date(s.stale_after).getTime() : at && at.getTime() + STALE_MS;
    // Offline already carries its fetch time in `text`, so it never gets the stale suffix on top
    if (now !== null && at && s.state !== 'offline' && now > staleAt) {
        // icon-only (text "") stays icon-only
        const text = s.text === '' ? '' : `${s.text} · ${hhmm(at)}`;
        return {...QUIET, state: 'stale', text, verdict: s.verdict, asOf: s.as_of};
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

const HEX = {green: '#57e389', amber: '#ffbe6f', red: '#ff7b63', blue: '#78aeed', grey: '#9a9996'};
export const NO_PACED = 'Pace isn\'t running';

export function agoText(at, now) {
    const min = Math.max(0, Math.floor((now - at.getTime()) / 60e3));
    if (min < 1)
        return 'just now';
    return min < 60 ? `${min} min ago` : `${Math.floor(min / 60)} h ago`;
}

const hours = min => String(Math.round(min / 6) / 10).replace(/\.0$/, '');
const hoursFixed = min => `${(Math.round(min / 6) / 10).toFixed(1)} h`;

// Everything the dropdown draws, as plain data. Null/absent keys drop their block.
export function menuModel(json, now) {
    const l = look(json, now);
    const s = parse(json);
    const m = {
        state: l.state,
        notice: {
            none: 'Waiting for paced',
            skew: 'Pace schema mismatch',
            signed_out: s?.problem ? null : 'Your DhiHRMS session expired',
            stale: 'paced has stopped updating: these numbers are old',
        }[l.state] ?? null,
        noticeDetail: l.state === 'skew' ? 'Log out and back in to show numbers' : null,
        signIn: l.state === 'signed_out',
        pinestemUrl: s?.pinestem_url ?? 'https://pinestem.com/dashboard.html#/tasks',
        snoozed: false,
        dim: l.dim,
    };
    if (l.state === 'none' || l.state === 'skew')
        return m;

    const at = s.as_of ? new Date(s.as_of) : null;
    const old = s.state === 'offline' || l.state === 'stale';
    m.updated = at ? (old ? `Last updated ${hhmm(at)}` : `Updated ${agoText(at, now)}`) : null;
    m.snoozed = !!s.snoozed_until;
    if (s.title) {
        m.title = `Week · ${s.title}`;
        m.titleColour = s.state === 'pay_risk' ? HEX.red : null;
        m.subtitle = s.subtitle ?? null;
        m.note = s.note ?? null;
    }
    const ln = s.lines;
    if (ln?.expected_min > 0) {
        const pc = v => Math.min(100, 100 * v / ln.expected_min);
        const logged = s.logged_min ?? 0;
        // B3: the LOP tick is emphasised, with the gap spelled out, on the last working day under the line
        const emphasis = logged < ln.lop_min && !!s.note?.startsWith('Last working day');
        m.bar = {
            fill: pc(logged), lop: pc(ln.lop_min), target: pc(ln.target_min),
            colour: l.dim ? HEX.grey : HEX[s.colour] ?? HEX.green,
            emphasis,
            legend: [`LOP ${hours(ln.lop_min)}`, `target ${hours(ln.target_min)}`, `expected ${hours(ln.expected_min)}`],
        };
        if (emphasis)
            m.gap = `${hoursFixed(ln.lop_min - logged)} to the loss-of-pay line · ${hoursFixed(ln.target_min - logged)} to target`;
    }
    if (s.days?.length)
        m.days = s.days.map(d => ({dow: d.dow, text: d.text, kind: d.kind}));
    m.warning = s.warning ?? null;
    m.warningDetail = s.warning_detail ?? null;
    m.action = s.action ?? null;
    m.lastWeek = s.last_week ?? null;
    if (s.month) {
        const n = s.month.working_days_left;
        m.month = {
            name: s.month.name,
            left: `${n} working day${n === 1 ? '' : 's'} left`,
            projects: (s.month.projects ?? []).map(p => ({
                name: p.name, text: p.text, needText: p.need_text,
                colour: p.gap_min === null ? null : p.gap_min < 0 ? HEX.amber : HEX.green,
                fill: p.target_min ? Math.min(100, 100 * p.billed_min / p.target_min) : null,
            })),
        };
    }
    if (s.problem) {
        const retry = s.problem.retry_at ? new Date(s.problem.retry_at).getTime() - now : null;
        const parts = [at ? `as of ${hhmm(at)}` : null,
            retry === null ? null : retry <= 0 ? 'retrying now' : `retrying in ${Math.max(1, Math.round(retry / 60e3))} min`];
        m.problem = {message: s.problem.message, detail: parts.filter(Boolean).join(' · ')};
    }
    return m;
}
