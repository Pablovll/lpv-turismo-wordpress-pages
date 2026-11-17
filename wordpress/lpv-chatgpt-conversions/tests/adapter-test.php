<?php
// Isolated WordPress doubles. Every HTTP request is intercepted; no customer email or CAPI event is sent.
define('ABSPATH', __DIR__);
define('MINUTE_IN_SECONDS', 60);
define('HOUR_IN_SECONDS', 3600);
define('DAY_IN_SECONDS', 86400);
define('LPV_ADS_ENABLED', true);
define('LPV_ADS_PRIVACY_READY', true);
define('LPV_ADS_PIXEL_ID', 'unit-test-pixel');
define('LPV_ADS_CAPI_KEY', 'unit-test-not-a-real-key');
$options = $transients = $requests = $scheduled = [];
$provider = ['response' => ['code' => 200], 'body' => '{"success":"true"}'];
$capi = ['response' => ['code' => 200], 'body' => '{}'];
class WP_Error {
    public $code;
    public function __construct($code, $message = '', $data = []) { $this->code = $code; }
}
class WP_REST_Response {
    public $data; public $status;
    public function __construct($data, $status = 200) { $this->data = $data; $this->status = $status; }
    public function header($key, $value) {}
}
class FakeRequest {
    public $input; public $headers;
    public function __construct($input = [], $headers = []) { $this->input = $input; $this->headers = $headers; }
    public function get_json_params() { return $this->input; }
    public function get_body() { return json_encode($this->input); }
    public function get_header($name) { return $this->headers[$name] ?? ''; }
}
function add_action(...$args) {}
function register_activation_hook(...$args) {}
function register_deactivation_hook(...$args) {}
function register_rest_route(...$args) {}
function home_url($path = '/') { return 'https://www.lpvturismo.com' . $path; }
function untrailingslashit($value) { return rtrim($value, '/'); }
function wp_salt($key) { return 'offline-unit-test-' . $key; }
function wp_json_encode($value) { return json_encode($value); }
function is_wp_error($value) { return $value instanceof WP_Error; }
function wp_verify_nonce($value, $action) { return $value === 'valid-test-nonce'; }
function wp_create_nonce($action) { return 'valid-test-nonce'; }
function get_transient($key) { global $transients; return $transients[$key] ?? false; }
function set_transient($key, $value, $ttl) { global $transients; $transients[$key] = $value; }
function get_option($key) { global $options; return $options[$key] ?? false; }
function add_option($key, $value, ...$args) {
    global $options;
    if (array_key_exists($key, $options)) { return false; }
    $options[$key] = $value; return true;
}
function update_option($key, $value, ...$args) { global $options; $options[$key] = $value; }
function delete_option($key) { global $options; unset($options[$key]); }
function wp_schedule_single_event($when, $hook, $args) { global $scheduled; $scheduled[] = [$when, $hook, $args]; }
function wp_remote_post($url, $args) {
    global $requests, $provider, $capi;
    $requests[] = [$url, $args];
    return strpos($url, 'https://formsubmit.co/') === 0 ? $provider : $capi;
}
function wp_remote_retrieve_response_code($value) { return $value['response']['code']; }
function wp_remote_retrieve_body($value) { return $value['body']; }

require_once dirname(__DIR__) . '/lpv-chatgpt-conversions.php';
use LPV\ChatGPTAds\Plugin;
$count = 0;
function check($condition, $name) {
    global $count;
    if (!$condition) { throw new RuntimeException($name); }
    ++$count;
}
function request_for($tail, $consent = true) {
    return new FakeRequest([
        'id' => 'lpv_lead_12345678-1234-1234-1234-' . str_pad($tail, 12, '0', STR_PAD_LEFT),
        'source' => 'https://lpvturismo.com/quero-montar-meu-roteiro/?email=private@example.test',
        'fields' => [
            'Nome' => 'Test', 'Email' => 'private@example.test', '_captcha' => 'false',
            'Observações' => 'Private health note', 'Produto Tijuca' => 'tijuca-historica',
            '_next' => 'https://evil.test/', '_cc' => 'attacker@example.test',
        ],
        'consent' => $consent, 'oppref' => $consent ? 'opaque-click-reference' : '',
    ], ['origin' => 'https://lpvturismo.com', 'x-lpv-nonce' => 'valid-test-nonce']);
}
function queue_keys() {
    global $options;
    return array_values(array_filter(array_keys($options), function ($key) {
        return strpos($key, Plugin::QUEUE) === 0 && substr($key, -5) !== '_lock';
    }));
}
$plugin = $lpv_ads_plugin;
check($plugin->config()['validate'] === true, 'Validation is the default');
check(is_wp_error($plugin->same_site(new FakeRequest([], ['origin' => 'https://evil.test']))), 'Reject cross-origin');
check(is_wp_error($plugin->permission(new FakeRequest([], ['origin' => 'https://lpvturismo.com']))), 'Reject missing nonce');
$request = request_for('1');
check($plugin->permission($request) === true, 'Allow observed site with nonce');
$result = $plugin->lead($request);
check($result->data['accepted'] === true, 'Confirmed FormSubmit result');
check(count($requests) === 1 && count(queue_keys()) === 1, 'One email request and one queued event');
$plugin->lead($request);
check(count($requests) === 1 && count(queue_keys()) === 1, 'Duplicate does not resend');
$changed = request_for('1'); $changed->input['fields']['Nome'] = 'Changed';
check($plugin->lead($changed)->status === 409 && count($requests) === 1, 'Changed payload cannot reuse an ID');
$forwarded = json_decode($requests[0][1]['body'], true);
check($forwarded['Produto Tijuca'] === 'tijuca-historica', 'Product context survives relay');
check(!isset($forwarded['_cc']) && !isset($forwarded['_next']), 'Recipient and redirect cannot be injected');
$key = queue_keys()[0];
$plugin->send($key);
$payload = json_decode($requests[1][1]['body'], true);
check($payload['validate_only'] === true, 'Tests do not record live conversions');
check($payload['events'][0]['type'] === 'lead_created', 'Correct event type');
check(strpos($requests[1][1]['body'], 'private@example.test') === false, 'No customer email to OpenAI');
check(strpos($requests[1][1]['body'], 'Private health note') === false, 'No customer notes to OpenAI');
check(strpos($payload['events'][0]['source_url'], '?') === false, 'No private query in event');
check($options[$key]['status'] === 'sent' && !isset($options[$key]['event']), 'Reference removed after delivery');
$plugin->send($key);
check(count($requests) === 2, 'Completed queue item not resent');
$transients = [];
$before = count(queue_keys());
check($plugin->lead(request_for('2', false))->data['accepted'] === true, 'Declining measurement does not block enquiry');
check(count(queue_keys()) === $before, 'No opt-in means no queued conversion');
$provider = ['response' => ['code' => 200], 'body' => '{"success":"false"}'];
$transients = [];
check($plugin->lead(request_for('3'))->data['accepted'] === false, 'HTTP 200 provider failure is not a lead');
check(count(queue_keys()) === $before, 'Provider failure produces no conversion');
$provider = new WP_Error('timeout');
$transients = [];
check($plugin->lead(request_for('4'))->data['accepted'] === false, 'Timeout remains unconfirmed');
$before_http = count($requests);
$plugin->lead(request_for('4'));
check(count($requests) === $before_http, 'Ambiguous email delivery never retries automatically');
$provider = ['response' => ['code' => 200], 'body' => '{"success":true}'];
$transients = [];
$plugin->lead(request_for('5'));
$keys = queue_keys(); $last = end($keys);
$capi = ['response' => ['code' => 503], 'body' => 'sensitive diagnostic not for storage'];
$plugin->send($last);
check($options[$last]['status'] === 'pending' && $options[$last]['attempts'] === 1, 'Transient CAPI failure is retried');
check(strpos(json_encode($options[$last]), 'sensitive diagnostic') === false, 'Response bodies are not retained');
$event_id = $options[$last]['event']['id'];
$capi = ['response' => ['code' => 401], 'body' => 'bad key'];
$before_schedule = count($scheduled);
$plugin->send($last);
check($options[$last]['status'] === 'failed', 'Invalid credentials stop retries');
check(count($scheduled) === $before_schedule, 'Permanent CAPI failure not rescheduled');
echo "Adapter: {$count} assertions passed.\n";
