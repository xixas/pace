// The panel look for every B1 state, from the fixtures paced's own status() wrote.
// Run: gjs -m extension/tests/look.test.js

import Gio from 'gi://Gio';
import System from 'system';
import {look, menuModel} from '../pace@osmosys/look.js';

const here = Gio.File.new_for_uri(import.meta.url).get_parent();
const load = (dir, name) => new TextDecoder().decode(here.get_child(dir).get_child(`${name}.json`).load_contents(null)[1]);
const fixture = name => load('fixtures', name);
const menu = name => load('menus', name);

let failed = 0;
function test(name, fn) {
    try {
        fn();
        print(`ok   ${name}`);
    } catch (e) {
        failed++;
        print(`FAIL ${name}\n     ${e.message}`);
    }
}
function eq(actual, expected, what) {
    if (JSON.stringify(actual) !== JSON.stringify(expected))
        throw new Error(`${what}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
}

// name → [marker, colour, dim, text] as drawn in B1
const B1 = {
    '01-on-track': ['dot', 'green', false, '30.1 / 42.5 h'],
    '02-ahead': ['▲', 'green', false, '28.4 / 42.5 h'],
    '03-tight': ['dot', 'amber', false, '23.0 / 42.5 h'],
    '04-behind': ['dot', 'amber', false, '21.0 / 42.5 h · pay 10.0/day'],
    '05-pay-risk': ['dot', 'red', false, '27.1 / 42.5 h · pay risk'],
    '06-bill': ['◌', 'blue', false, '34.0 / 42.5 h'],
    '07-last-day-gap': ['dot', 'green', false, '40.0 / 42.5 h · pay needs 1.0 h'],
    '08-done': ['✓', 'green', false, '42.5 h'],
    '09-short': ['dot', 'amber', false, '41.8 / 42.5 h · pay safe'],
    '10-lop': ['dot', 'red', false, '39.5 h · LOP 1 day'],
    '11-on-leave': ['○', 'grey', true, 'On leave'],
    '12-offline': ['○', 'grey', true, '26.6 / 42.5 h · 09:40'],
    '13-signed-out': ['dot', 'amber', false, 'Sign in again'],
};

for (const [name, [marker, colour, dim, text]] of Object.entries(B1)) {
    test(name, () => {
        const l = look(fixture(name));
        eq([l.marker, l.colour, l.dim, l.text], [marker, colour, dim, text], 'look');
    });
}

test('no file yet: waiting for paced, greyed', () => {
    const l = look(null);
    eq([l.state, l.marker, l.colour, l.dim, l.text, l.verdict], ['none', '○', 'grey', true, 'Pace', null], 'look');
});

test('unreadable or half-written file: same as no file', () => {
    eq(look('{"version": 1, "sta').state, 'none', 'state');
});

test('a newer status.json than this extension knows: says so instead of guessing', () => {
    const l = look(JSON.stringify({version: 2, state: 'on_track', colour: 'green', icon: 'dot', text: '1 / 2 h'}));
    eq([l.state, l.marker, l.colour, l.dim, l.text], ['skew', '○', 'grey', true, 'Update Pace'], 'look');
});

// Fixtures are stamped 2026-10-29 14:10 local; paced rewrites status.json every 5 min poll
const AT = new Date(2026, 9, 29, 14, 10).getTime();
const MIN = 60e3;

test('fresh numbers keep their colour', () => {
    const l = look(fixture('01-on-track'), AT + 14 * MIN);
    eq([l.state, l.colour, l.dim, l.text], ['on_track', 'green', false, '30.1 / 42.5 h'], 'look');
});

test('numbers 3 polls old: paced has stopped, grey them with the time like OFFLINE', () => {
    const l = look(fixture('05-pay-risk'), AT + 16 * MIN);
    eq([l.state, l.marker, l.colour, l.dim, l.text], ['stale', '○', 'grey', true, '27.1 / 42.5 h · pay risk · 14:10'], 'look');
});

test('OFFLINE already carries its time and SIGNED OUT has none: neither turns stale', () => {
    eq(look(fixture('12-offline'), AT + 600 * MIN).text, '26.6 / 42.5 h · 09:40', 'offline');
    eq(look(fixture('13-signed-out'), AT + 600 * MIN).state, 'signed_out', 'signed out');
});

test('stale_after in status.json beats the 15 min default; icon-only stays icon-only', () => {
    const s = JSON.parse(fixture('01-on-track'));
    s.stale_after = '2026-10-29T14:20:00';
    eq(look(JSON.stringify(s), AT + 8 * MIN).state, 'on_track', 'before stale_after');
    s.text = '';
    const l = look(JSON.stringify(s), AT + 21 * MIN);
    eq([l.state, l.text], ['stale', ''], 'after stale_after');
});

// Menus: fixtures stamped 2026-10-29 14:06, so "now" 14:10 reads "Updated 4 min ago"
const M = new Date(2026, 9, 29, 14, 10).getTime();

test('B2 on track: header, bar ticks, days, month, footer', () => {
    const m = menuModel(menu('b2-on-track'), M);
    eq([m.title, m.subtitle, m.note, m.titleColour], ['Week · On track', 'needs 8.0 h/day', '4.5 h left today', null], 'header');
    eq(m.bar.legend, ['LOP 41', 'target 42.5', 'expected 45'], 'legend');
    eq([m.bar.fill, m.bar.lop, m.bar.target].map(v => Math.round(v * 10) / 10), [66.9, 91.1, 94.4], 'bar percentages');
    eq(m.bar.emphasis, false, 'lop not emphasised');
    eq(m.days.map(d => `${d.dow} ${d.text} ${d.kind}`), ['Mon 9.2 billed', 'Tue 8.4 billed', 'Wed 9.0 billed', 'Thu 3.5 today', 'Fri – future'], 'days');
    eq([m.month.name, m.month.left, m.month.projects.length], ['October', '2 working days left', 2], 'month');
    eq([m.month.projects[0].needText, m.month.projects[0].colour, m.month.projects[1].colour], ['needs 10.3 h/day on Tweelin', '#ffbe6f', null], 'projects');
    eq([m.updated, m.problem, m.snoozed, m.lastWeek, m.action], ['Updated 4 min ago', undefined, false, null, null], 'footer');
});

test('B3 friday gap: LOP tick emphasised with the gap spelled out and a fix button', () => {
    const m = menuModel(menu('b3-friday-gap'), new Date(2026, 9, 30, 18, 30).getTime());
    eq([m.bar.emphasis, m.gap], [true, '1.0 h to the loss-of-pay line · 2.5 h to target'], 'gap');
    eq([m.subtitle, m.action.label], ['pay needs 1.0 h', 'Bill 1 h to stay clear of loss of pay'], 'header');
});

test('B4 pay risk: red title, short days named, warning detail', () => {
    const m = menuModel(menu('b4-pay-risk'), new Date(2026, 9, 30, 11, 0).getTime());
    eq([m.titleColour, m.warning, m.days[2].kind], ['#ff7b63', 'Short days: Wed 6.0 h · Thu 3.5 h', 'short'], 'risk');
    eq(m.warningDetail.startsWith('Even 10.5 h'), true, 'detail');
});

test('B5 bill: blue, pending day says not yet, button bills', () => {
    const m = menuModel(menu('b5-bill'), new Date(2026, 9, 30, 20, 30).getTime());
    eq([m.bar.colour, m.days[4].kind, m.days[4].text, m.action.label], ['#78aeed', 'pending', 'not yet', 'Open PineStem to bill Fri'], 'bill');
});

test('B6 offline: banner with as-of and retry countdown, grey, last-updated time', () => {
    const m = menuModel(menu('b6-offline'), M);
    eq([m.problem.message, m.problem.detail], ["Can't reach DhiHRMS", 'as of 09:40 · retrying in 2 min'], 'banner');
    eq([m.updated, m.dim, m.bar.colour], ['Last updated 09:40', true, '#9a9996'], 'dim');
});

test('B12 monday: last-week banner data present', () => {
    const m = menuModel(menu('b12-monday-banner'), new Date(2026, 10, 2, 9, 20).getTime());
    eq([m.lastWeek.text, m.lastWeek.detail], ['Last week: Fri 30 Oct not billed yet', 'Bill by 12:00 today or it counts as 34.0 h → LOP 1 day.'], 'banner');
});

test('C12 snoozed', () => {
    eq(menuModel(menu('c12-snoozed'), M).snoozed, true, 'snoozed');
});

test('C10 skew: update prompt only, never numbers', () => {
    const m = menuModel(menu('c10-skew'), M);
    eq([m.state, m.notice, m.noticeDetail, m.title, m.bar, m.days], ['skew', 'Pace schema mismatch', 'Log out and back in to show numbers', undefined, undefined, undefined], 'skew');
});

test('signed out: notice plus sign-in, no data blocks', () => {
    const m = menuModel(menu('signed-out'), M);
    eq([m.signIn, m.problem.message, m.notice, m.title, m.bar, m.days], [true, 'Your DhiHRMS session expired', null, undefined, undefined, undefined], 'signed out');
});

test('stale numbers: notice and "Last updated" instead of "N min ago"', () => {
    const m = menuModel(menu('b2-on-track'), M + 60 * MIN);
    eq([m.state, m.notice, m.updated], ['stale', 'paced has stopped updating: these numbers are old', 'Last updated 14:06'], 'stale');
});

test('no file: waiting for paced', () => {
    eq(menuModel(null, M).notice, 'Waiting for paced', 'none');
});

if (failed)
    System.exit(1);
