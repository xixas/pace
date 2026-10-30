// Pace week verdict, rules v2 (after Fable round 1). Faithful to hrms-api LOP:
// lopCount = max(0, d - (floor(total/9) + (total%9 >= 5))), weekly, total = billable + non-billable.
const DAYS = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
const POLLS = [9, 12.5, 18.5, 20.5];
const T = 8.5, E = 9, FULL = 9, PART = 5, MAXDAY = 10.5, GRACE_UNTIL = 12, EOD = 20;

const lopCount = (total, d) => d <= 0 ? 0 : Math.max(0, d - (Math.floor(total / FULL) + ((total % FULL) >= PART ? 1 : 0)));
const lopLine = d => FULL * (Math.ceil(d) - 1) + PART; // smallest total with lopCount 0

function verdict(work, entries, day, hour) {
  // work: number[7] = fraction of day working (1, 0.5, 0)
  const seen = entries.filter(e => e.day < day || (e.day === day && e.hour <= hour));
  const forDay = i => seen.filter(e => e.at === i).reduce((s, e) => s + e.h, 0);
  const logged = seen.reduce((s, e) => s + e.h, 0);
  const d = work.reduce((a, b) => a + b, 0);
  if (d === 0) return { v: 'ON LEAVE', logged };
  const lop = lopLine(d), target = Math.max(T * d, lop); // half-day weeks: 38.25 < 41, pay wins
  const lastWork = work.map((w, i) => w ? i : -1).filter(i => i >= 0).pop();
  // pending: a working day with ZERO hours billed is "not billed yet" (not a shortfall) after its EOD
  // until 12:00 of the next working day (Fri -> Mon 12:00). Partial days count as billed.
  const nextWork = i => { for (let j = i + 1; j < 7; j++) if (work[j]) return j; return 7; }; // 7 = next Monday
  let credit = 0; const pendingDays = [];
  for (let i = 0; i <= Math.min(day, 6); i++) {
    if (!work[i] || forDay(i) > 0) continue;
    const closed = i < day ? true : hour >= EOD;            // day's own work window over
    const nw = nextWork(i);
    const graceOpen = day < nw || (day === nw && hour < GRACE_UNTIL);
    if (closed && graceOpen) { credit += T * work[i]; pendingDays.push(DAYS[i]); }
  }
  const eff = logged + credit;
  const tag = pendingDays.length ? ` · ${pendingDays.join(',')} not billed yet` : '';
  if (day > lastWork) {
    const n = lopCount(eff, d);
    return { v: (logged >= target ? 'DONE' : eff >= target ? 'BILL' : n > 0 ? `LOP ${n}d` : 'SHORT (pay safe)') + tag, logged, short: +(target - logged).toFixed(1) };
  }
  // remaining working capacity incl. today (today counts fully until EOD, then 0)
  let rem = work.slice(day + 1).reduce((a, b) => a + b, 0) + (hour < EOD ? work[day] : 0);
  const afterEod = hour >= EOD;
  const pastDays = work.slice(0, day + (afterEod ? 1 : 0)).reduce((a, b) => a + b, 0);
  const before = afterEod ? logged : logged - forDay(day);
  const todayH = forDay(day), inToday = hour < EOD && work[day] > 0;
  const base = inToday ? eff - todayH : eff;                 // today's hours don't move need/day until EOD
  const need = rem > 0 ? (target - base) / rem : Infinity;
  const lopNeed = rem > 0 ? (lop - base) / rem : Infinity;
  const todayLeft = inToday ? Math.max(0, need * work[day] - todayH) : undefined;
  let v;
  if (logged >= target) v = 'DONE';
  else if (eff >= target) v = 'BILL';
  else if (eff < lop && (rem === 0 || lopNeed > MAXDAY)) v = 'PAY RISK';
  else if (rem === 0) v = 'SHORT (pay safe)';
  else if (need > MAXDAY) v = 'BEHIND';
  else if (need > E) v = 'TIGHT';
  else if (pastDays > 0 && day !== lastWork && before >= E * pastDays) v = 'AHEAD';
  else v = 'ON TRACK';
  // last working day: show the hard pay gap next to the band
  if (day === lastWork && eff < lop) v += ` · pay needs ${(lop - eff).toFixed(1)} h`;
  // red points at the fixable day: closed working days under 8.5 h this week
  const shortDays = []; for (let i = 0; i <= day; i++) if (work[i] && (i < day || afterEod) && !pendingDays.includes(DAYS[i]) && forDay(i) < T * work[i] - 0.25) shortDays.push(`${DAYS[i]} ${forDay(i)} h`);
  if (v.startsWith('PAY RISK') && shortDays.length) v += ` · ${shortDays.join(', ')}`;
  v += tag;
  return { v, logged: +logged.toFixed(1), todayLeft: todayLeft === undefined ? '-' : +todayLeft.toFixed(1), need: isFinite(need) ? +need.toFixed(2) : '-', lopNeed: isFinite(lopNeed) ? +lopNeed.toFixed(2) : '-' };
}

const daily = (hrs, enteredHour = 18, lag = 0) => hrs.flatMap((h, i) => h ? [{ at: i, day: i + lag, hour: enteredHour, h }] : []);
const W5 = [1,1,1,1,1,0,0];
const S = {
  '1 steady 8.5 billed 18:00': [W5, daily([8.5,8.5,8.5,8.5,8.5])],
  '2 steady 8.5 billed next morning 10:00': [W5, daily([8.5,8.5,8.5,8.5,8.5], 10, 1)],
  '3 front-loaded 10,10,10,8,4.5': [W5, daily([10,10,10,8,4.5])],
  '4 back-loaded 0,0,10.5,10.5,10.5': [W5, daily([0,0,10.5,10.5,10.5])],
  '5 Monday zero (sick, no leave) then 9.5': [W5, daily([0,9.5,9.5,9.5,9.5])],
  '6 leave Wed, 8.5x4': [[1,1,0,1,1,0,0], daily([8.5,8.5,0,8.5,8.5])],
  '7 holiday Mon, 8x4': [[0,1,1,1,1,0,0], daily([0,8,8,8,8])],
  '8 batch biller, each day entered Fri 17:00': [W5, [0,1,2,3,4].map(i => ({at:i,day:4,hour:17,h:8.5}))],
  '9 9,9,9,9,4 (1 h under LOP)': [W5, daily([9,9,9,9,4])],
  '10 8x5 then Sat 3h': [W5, [...daily([8,8,8,8,8]), {at:5,day:5,hour:12,h:3}]],
  '11 on leave all week': [[0,0,0,0,0,0,0], []],
  '12 trickle hourly to 8.5/day': [W5, [0,1,2,3,4].flatMap(d => [11,13,15,17,18].map((hr,k)=>({at:d,day:d,hour:hr,h:k<4?2:0.5})))],
  '13 exactly 41: 9,9,9,9,5': [W5, daily([9,9,9,9,5])],
  '14 half-day leave Thu (d=4.5), 8.5,8.5,8.5,4.5,8.5': [[1,1,1,0.5,1,0,0], daily([8.5,8.5,8.5,4.5,8.5])],
  '15 Friday billed Saturday 10:00': [W5, [...daily([8.5,8.5,8.5,8.5]), {at:4,day:5,hour:10,h:8.5}]],
  '16 3-day week (Mon,Tue holidays) 8.5x3': [[0,0,1,1,1,0,0], daily([0,0,8.5,8.5,8.5])],
  '17 50 h week: 10x5': [W5, daily([10,10,10,10,10])],
  '18 Thu partial 3.5 entered, rest never': [W5, daily([9.2,8.4,9.0,3.5,8.5])],
};
for (const [name, [work, entries]] of Object.entries(S)) {
  console.log(`\n## ${name}`);
  for (let day = 0; day < 7; day++) for (const hour of POLLS) {
    if (day > 4 && hour !== 12.5) continue;
    const r = verdict(work, entries, day, hour);
    console.log(`${DAYS[day]} ${String(hour).padStart(4)}  ${r.v.padEnd(30)} logged ${String(r.logged).padStart(5)}${r.need !== undefined ? `  today-left ${r.todayLeft}  need/day ${r.need}  lopNeed ${r.lopNeed}` : ''}`);
  }
}
