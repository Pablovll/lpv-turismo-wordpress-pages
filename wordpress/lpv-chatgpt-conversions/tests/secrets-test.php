<?php
require_once dirname(__DIR__) . '/includes/secrets.php';
use LPV\ChatGPTAds\Secrets;
$count = 0;
function check($ok, $name) {
    global $count;
    if (!$ok) { throw new RuntimeException($name); }
    ++$count;
}
check(Secrets::available(), 'Test runner supports authenticated encryption');
$dummy = 'test-only-key-not-a-customer-credential';
$a = Secrets::encrypt($dummy, 'site-specific-test-salt');
$b = Secrets::encrypt($dummy, 'site-specific-test-salt');
check($a !== $b, 'Fresh nonce on every encryption');
check(strpos($a, $dummy) === false, 'No cleartext in stored record');
check(Secrets::decrypt($a, 'site-specific-test-salt') === $dummy, 'Stored key round trip');
check(Secrets::decrypt($a, 'different-site-salt') === '', 'Salt rotation fails closed');
$raw = base64_decode(substr($a, 3));
$raw[15] = chr(ord($raw[15]) ^ 1);
check(Secrets::decrypt('v1:' . base64_encode($raw), 'site-specific-test-salt') === '', 'Tampered authentication tag rejected');
foreach (['', 'v1:invalid!', 'v1:' . base64_encode('short'), 'unknown:anything'] as $invalid) {
    check(Secrets::decrypt($invalid, 'salt') === '', 'Invalid stored value fails closed');
}
echo "Secrets: {$count} assertions passed.\n";
