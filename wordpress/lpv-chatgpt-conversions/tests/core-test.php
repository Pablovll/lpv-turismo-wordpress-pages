<?php
require_once dirname(__DIR__) . '/includes/core.php';
use LPV\ChatGPTAds\Core;
$count = 0;
function check($condition, $name) {
    global $count;
    if (!$condition) { throw new RuntimeException($name); }
    ++$count;
}
function rejects($callback, $name) {
    try { $callback(); } catch (InvalidArgumentException $e) { check(true, $name); return; }
    throw new RuntimeException($name);
}
$home = 'https://www.lpvturismo.com/';
$source = 'https://lpvturismo.com/quero-montar-meu-roteiro/?email=private@example.test#secret';
$id = 'lpv_lead_12345678-1234-1234-1234-123456789abc';
check(Core::source_url($source, $home) === 'https://www.lpvturismo.com/quero-montar-meu-roteiro/', 'Strip private query and fragment');
foreach (['http://lpvturismo.com/', 'https://evil.test/', 'https://lpvturismo.com.evil.test/', 'https://user:pass@lpvturismo.com/', 'https://lpvturismo.com:9999/'] as $bad) {
    rejects(function () use ($bad, $home) { Core::source_url($bad, $home); }, 'Reject foreign or unsafe origin');
}
rejects(function () use ($home) { Core::form_page('https://lpvturismo.com/other/', $home); }, 'Only observed forms');
$fields = ['Nome' => ' Test ', 'Email' => 'person@example.test', '_captcha' => 'false', 'Observações' => 'Private health note', '_cc' => 'attacker@example.test', '_webhook' => 'https://evil.test/'];
$clean = Core::fields($fields);
check(!isset($clean['_cc']) && !isset($clean['_webhook']), 'Cannot change recipients or add a webhook');
check($clean['Observações'] === 'Private health note', 'Preserve customer fields for FormSubmit');
check(Core::accepted(200, '{"success":true}'), 'Boolean provider success');
check(Core::accepted(200, '{"success":"true"}'), 'String provider success');
check(!Core::accepted(200, '{"success":"false"}'), 'HTTP 200 is not provider success');
check(!Core::accepted(200, '<html>Activation required</html>'), 'Reject HTML activation page');
check(!Core::accepted(200, '{"success":true,"message":"This form needs Activation"}'), 'Activation is not a confirmed submission');
check(!Core::accepted(500, '{"success":true}'), 'Reject HTTP failure');
check(Core::event($id, $source, $home, 'opaque-ref', false, 1) === null, 'No consent means no event');
$event = Core::event($id, $source, $home, 'Opaque+REF/=', true, 123);
check($event['oppref'] === 'Opaque+REF/=', 'Keep opaque reference unchanged');
check($event['data'] === ['type' => 'customer_action'] && $event['type'] === 'lead_created', 'Lead taxonomy');
check(!isset($event['user']) && !isset($event['amount']), 'No customer identifiers or invented revenue');
check(strpos(json_encode($event), 'person@example.test') === false, 'Do not transmit form PII');
rejects(function () use ($id, $source, $home) { Core::event($id, $source, $home, "bad\nref", true, 1); }, 'Reject control characters');
check(Core::retryable(429) && Core::retryable(503) && !Core::retryable(401), 'Retry transient failures only');
echo "Core: {$count} assertions passed.\n";
