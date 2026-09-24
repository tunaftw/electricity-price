import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  asOf,
  impliedHistory,
  withGaps,
  priceGroups,
  csvText,
} from '../app/analysis.mjs';
test('historical queries never use later quotes and expire stale quotes', () => {
  const r = [
    ['2024-06-03', 12],
    ['2024-06-05', 99],
  ];
  assert.deepEqual(asOf(r, '2024-06-04'), r[0]);
  assert.equal(asOf(r, '2024-06-02'), null);
  assert.equal(asOf(r, '2024-06-20'), null);
});
test('implied curves require both legs on the same value date', () =>
  assert.deepEqual(
    impliedHistory(
      [
        ['2024-06-01', 50],
        ['2024-06-02', 60],
      ],
      [['2024-06-02', -5]],
    ),
    [['2024-06-02', 55, null]],
  ));
test('long gaps are explicit, regular weekends remain connected', () => {
  const r = withGaps([
    ['2024-06-07', 1],
    ['2024-06-10', 2],
    ['2024-06-28', 3],
  ]);
  assert.equal(r.length, 4);
  assert.equal(r[2][1], null);
});
test('local time distinguishes repeated autumn intervals', () => {
  const r = priceGroups(
    [
      ['2024-10-27T02:00:00+02:00', 10],
      ['2024-10-27T02:00:00+01:00', 30],
    ],
    'interval',
  );
  assert.equal(r.length, 2);
  assert.equal(
    priceGroups(
      [
        ['2024-10-27T02:00:00+02:00', 10],
        ['2024-10-27T02:00:00+01:00', 30],
      ],
      'day',
    )[0].price,
    20,
  );
});
test('export preserves numeric negatives and neutralizes formula strings', () => {
  const x = csvText(['a', 'b'], [[-5, '=1+1']]);
  assert.ok(x.includes('"-5"'));
  assert.ok(x.includes('"\'=1+1"'));
});
test('repeated autumn intervals retain chronological order', () => {
  const r = priceGroups(
    [
      ['2024-10-27T02:00:00+01:00', 30],
      ['2024-10-27T02:00:00+02:00', 10],
    ],
    'interval',
  );
  assert.equal(r[0].price, 10);
  assert.equal(r[1].price, 30);
});
