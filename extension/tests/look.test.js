// The panel look for every B1 state, from the fixtures paced's own status() wrote.
// Run: gjs -m extension/tests/look.test.js

import Gio from 'gi://Gio';
import System from 'system';
import {look} from '../pace@osmosys/look.js';

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

if (failed)
    System.exit(1);
