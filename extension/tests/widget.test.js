// The shell widget's pure logic: what it shows, where it may sit, what is remembered.
// Run: gjs -m extension/tests/widget.test.js

import Gio from 'gi://Gio';
import System from 'system';
import {clampToArea, isLight, monitorAt, parseSaved, serializeSaved, startPosition, widgetModel} from '../pace@osmosys/widgetModel.js';

const here = Gio.File.new_for_uri(import.meta.url).get_parent();
const fixture = name => new TextDecoder().decode(here.get_child('fixtures').get_child(`${name}.json`).load_contents(null)[1]);

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

const AREA = {x: 0, y: 32, width: 1600, height: 868};

test('week on track and project behind: label, word, numbers, bar and captions come from the widget key', () => {
    const m = widgetModel(fixture('01-on-track'));
    eq([m.week.label, m.week.word, m.week.colour, m.week.big, m.week.unit, m.week.fill, m.week.lines],
        ['THIS WEEK', 'on track', 'green', '30.1 / 42.5', 'h', 71, ['8.0 h/day to reach 42.5 h']], 'week');
    eq([m.project.label, m.project.word, m.project.colour, m.project.fill], ['TWEELIN · OCT', 'behind 14.8 h', 'amber', 80], 'project');
});

test('pay risk keeps both caption lines; on leave has no big line and no bar', () => {
    eq(widgetModel(fixture('05-pay-risk')).week.lines, ['13.9 h needed today', 'Wed 6.0 h · Thu 3.5 h'], 'lines');
    const w = widgetModel(fixture('11-on-leave')).week;
    eq([w.big, w.fill], ['', null], 'leave');
});

test('no status, no widget key and a bad colour still draw something sensible', () => {
    eq(widgetModel(null).week.lines, ['Waiting for paced'], 'none');
    eq(widgetModel('{not json').week.lines, ['Waiting for paced'], 'garbled');
    eq(widgetModel('{"text": "Sign in again"}').week.lines, ['Sign in again'], 'no widget key');
    const odd = {widget: {week: {label: 'X', word: 'w', colour: 'purple', big: '1', unit: 'h', fill: 7, lines: []}, project: null}};
    eq([widgetModel(JSON.stringify(odd)).week.colour, widgetModel(JSON.stringify(odd)).week.fill, widgetModel(JSON.stringify(odd)).project], ['grey', 100, null], 'odd');
});

test('clamping keeps the card inside the work area on every side', () => {
    eq(clampToArea(-50, 0, 240, 200, AREA), [0, 32], 'top-left');
    eq(clampToArea(5000, 5000, 240, 200, AREA), [1360, 700], 'bottom-right');
    eq(clampToArea(100, 300, 240, 200, AREA), [100, 300], 'inside is untouched');
});

test('the monitor is the one under the card centre, the first when none is', () => {
    const mons = [{x: 0, y: 0, width: 1600, height: 900}, {x: 1600, y: 0, width: 1920, height: 1080}];
    eq(monitorAt(1700, 100, 240, 200, mons), mons[1], 'second');
    eq(monitorAt(-3000, 100, 240, 200, mons), mons[0], 'off-screen falls back');
});

test('a first run sits top right; a saved spot is kept but pulled back on screen', () => {
    eq(startPosition(null, 240, 200, AREA), [1344, 48], 'default');
    eq(startPosition({x: 100, y: 200}, 240, 200, AREA), [100, 200], 'saved');
    eq(startPosition({x: 9000, y: 200}, 240, 200, AREA), [1360, 200], 'monitor went away');
});

test('the remembered state survives a round trip and junk reads as hidden', () => {
    eq(parseSaved(serializeSaved({visible: true, x: 10, y: 20})), {visible: true, x: 10, y: 20}, 'round trip');
    eq(parseSaved('nope'), {visible: false, x: null, y: null}, 'junk');
    eq(parseSaved('{"visible": true}'), {visible: true, x: null, y: null}, 'no position yet');
});

test('light only when the desktop is not asking for dark', () => {
    eq([isLight('default'), isLight('prefer-light'), isLight('prefer-dark')], [true, true, false], 'scheme');
});

if (failed > 0)
    System.exit(1);
