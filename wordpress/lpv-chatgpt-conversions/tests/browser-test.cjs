'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { accepted, reference, safeEndpoint, FORM_IDS } = require('../assets/conversions.js');
test('a successful request is not necessarily an accepted lead', () => {
  assert.equal(accepted({ok: true}, {accepted: true}), true);
  for (const body of [{accepted: false}, {accepted: 'true'}, {}, null]) {
    assert.ok(!accepted({ok: true}, body));
  }
  assert.equal(accepted({ok: false}, {accepted: true}), false);
});
test('opaque click references are preserved and malformed references are discarded', () => {
  assert.equal(reference('Opaque+REF/='), 'Opaque+REF/=');
  assert.equal(reference(null), '');
  assert.equal(reference('bad\nref'), '');
  assert.equal(reference('x'.repeat(4097)), '');
});
test('use the current canonical origin without allowing a foreign endpoint', () => {
  assert.equal(safeEndpoint('https://www.lpvturismo.com/wp-json/lpv-ads/v1/lead', 'https://lpvturismo.com/passeios/'),
    'https://lpvturismo.com/wp-json/lpv-ads/v1/lead');
  for (const url of ['https://evil.test/', 'https://lpvturismo.com.evil.test/', 'http://lpvturismo.com/', 'https://lpvturismo.com:9999/']) {
    assert.throws(() => safeEndpoint(url, 'https://lpvturismo.com/'));
  }
});
test('target only the three observed forms', () => {
  assert.deepEqual(FORM_IDS, ['lpv-roteiro-form', 'lpv-roteiro-form-es', 'lpv-itinerary-form']);
});
