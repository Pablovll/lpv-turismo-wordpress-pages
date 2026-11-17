<?php
/**
 * Plugin Name: LPV ChatGPT Conversions
 * Description: Confirmed FormSubmit leads to OpenAI CAPI, with optional visitor consent.
 * Version: 0.1.0
 * Requires PHP: 7.4
 * Requires at least: 6.2
 * Author: LPV Turismo
 */
namespace LPV\ChatGPTAds;

if (!defined('ABSPATH')) { exit; }
require_once __DIR__ . '/includes/core.php';

final class Plugin {
    const VERSION = '0.1.0';
    const CLEANUP = 'lpv_ads_cleanup';
    const SEND = 'lpv_ads_send_event';
    const RECEIPTS = 'lpv_ads_receipt_';
    const QUEUE = 'lpv_ads_queue_';

    public function __construct() {
        add_action('rest_api_init', [$this, 'routes']);
        add_action('wp_enqueue_scripts', [$this, 'assets']);
        add_action(self::SEND, [$this, 'send'], 10, 1);
        add_action(self::CLEANUP, [$this, 'cleanup']);
        add_action('admin_menu', [$this, 'admin_menu']);
    }

    public function config() {
        return [
            'enabled' => defined('LPV_ADS_ENABLED') && LPV_ADS_ENABLED === true,
            'privacy_ready' => defined('LPV_ADS_PRIVACY_READY') && LPV_ADS_PRIVACY_READY === true,
            'pixel' => defined('LPV_ADS_PIXEL_ID') ? (string) LPV_ADS_PIXEL_ID : '',
            'key' => defined('LPV_ADS_CAPI_KEY') ? (string) LPV_ADS_CAPI_KEY : '',
            'validate' => !defined('LPV_ADS_VALIDATE_ONLY') || LPV_ADS_VALIDATE_ONLY !== false,
        ];
    }

    public function ready() {
        $c = $this->config();
        return $c['enabled'] && $c['privacy_ready'] && $c['pixel'] !== '' && $c['key'] !== '';
    }

    public function routes() {
        register_rest_route('lpv-ads/v1', '/session', [
            'methods' => 'GET', 'callback' => [$this, 'session'],
            'permission_callback' => [$this, 'same_site'],
        ]);
        register_rest_route('lpv-ads/v1', '/lead', [
            'methods' => 'POST', 'callback' => [$this, 'lead'],
            'permission_callback' => [$this, 'permission'],
        ]);
    }

    public function same_site($request) {
        if (!$this->ready()) {
            return new \WP_Error('lpv_ads_disabled', 'Integration unavailable.', ['status' => 503]);
        }
        $origin = $request->get_header('origin');
        $referer = $request->get_header('referer');
        try {
            if ($origin !== '') { Core::source_url($origin, home_url('/')); }
            elseif ($referer !== '') { Core::source_url($referer, home_url('/')); }
            else { throw new \InvalidArgumentException('origin_required'); }
        } catch (\InvalidArgumentException $e) {
            return new \WP_Error('lpv_ads_origin', 'Invalid origin.', ['status' => 403]);
        }
        return true;
    }

    public function permission($request) {
        $allowed = $this->same_site($request);
        if (is_wp_error($allowed)) { return $allowed; }
        if (!wp_verify_nonce($request->get_header('x-lpv-nonce'), 'lpv_ads_lead')) {
            return new \WP_Error('lpv_ads_nonce', 'Session expired.', ['status' => 403]);
        }
        return true;
    }

    private function response($data, $status = 200) {
        $response = new \WP_REST_Response($data, $status);
        $response->header('Cache-Control', 'no-store, private');
        return $response;
    }

    public function session() {
        return $this->response(['nonce' => wp_create_nonce('lpv_ads_lead')]);
    }

    private function budget() {
        // Use the direct peer only, never trust a client-supplied forwarded IP.
        $peer = isset($_SERVER['REMOTE_ADDR']) ? (string) $_SERVER['REMOTE_ADDR'] : 'unknown';
        $key = 'lpv_ads_rate_' . hash_hmac('sha256', $peer, wp_salt('nonce'));
        $count = (int) get_transient($key);
        if ($count >= 5) { return false; }
        set_transient($key, $count + 1, 10 * MINUTE_IN_SECONDS);
        return true;
    }

    public function lead($request) {
        if (strlen($request->get_body()) > 65536) {
            return $this->response(['code' => 'request_too_large'], 413);
        }
        $input = $request->get_json_params();
        try {
            if (!is_array($input)) { throw new \InvalidArgumentException('invalid_payload'); }
            $id = $input['id'] ?? '';
            if (!is_string($id) || !preg_match('/^lpv_lead_[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/D', $id)) {
                throw new \InvalidArgumentException('invalid_event_id');
            }
            $source = Core::form_page($input['source'] ?? '', home_url('/'));
            $fields = Core::fields($input['fields'] ?? null);
            $event = Core::event(
                $id, $source, home_url('/'), $input['oppref'] ?? '',
                ($input['consent'] ?? false) === true, (int) floor(microtime(true) * 1000)
            );
        } catch (\InvalidArgumentException $e) {
            return $this->response(['code' => $e->getMessage()], 400);
        }
        // A request ID is bound to the original sanitized fields, never to raw PII in storage.
        $digest = hash_hmac('sha256', wp_json_encode([$source, $fields]), wp_salt('auth'));
        $receipt_key = self::RECEIPTS . hash('sha256', $id);
        $prior = get_option($receipt_key);
        if ($prior) {
            if (!hash_equals($prior['digest'] ?? '', $digest)) {
                return $this->response(['code' => 'request_conflict'], 409);
            }
            return $this->receipt_response($prior);
        }
        if (!$this->budget()) { return $this->response(['code' => 'rate_limited'], 429); }
        $receipt = [
            'digest' => $digest, 'state' => 'processing',
            'expires' => time() + 3 * DAY_IN_SECONDS,
        ];
        if (!add_option($receipt_key, $receipt, '', false)) {
            return $this->response(['code' => 'processing'], 409);
        }
        // Fixed destination: clients cannot choose an email recipient or remote host.
        $fields['_url'] = $source;
        $provider = wp_remote_post('https://formsubmit.co/ajax/info@lpvturismo.com', [
            'timeout' => 20, 'redirection' => 0, 'limit_response_size' => 65536,
            'headers' => [
                'Content-Type' => 'application/json', 'Accept' => 'application/json',
                'Origin' => untrailingslashit(home_url('/')), 'Referer' => $source,
            ],
            'body' => wp_json_encode($fields), 'data_format' => 'body',
        ]);
        $code = is_wp_error($provider) ? 0 : (int) wp_remote_retrieve_response_code($provider);
        $body = is_wp_error($provider) ? '' : wp_remote_retrieve_body($provider);
        if (!Core::accepted($code, $body)) {
            // A timeout is ambiguous: never resend email automatically or count a lead.
            $receipt['state'] = 'unconfirmed';
            update_option($receipt_key, $receipt, false);
            return $this->receipt_response($receipt);
        }
        $receipt['state'] = 'accepted';
        update_option($receipt_key, $receipt, false);
        if ($event !== null) { $this->queue($id, $event); }
        return $this->response(['accepted' => true]);
    }

    private function receipt_response($receipt) {
        if (($receipt['state'] ?? '') === 'accepted') {
            return $this->response(['accepted' => true]);
        }
        return $this->response(['accepted' => false, 'code' => 'unconfirmed'], 409);
    }

    public function queue($id, $event) {
        $c = $this->config();
        if (!$this->ready()) { return; }
        $key = self::QUEUE . hash('sha256', $id);
        $record = [
            'event' => $event, 'attempts' => 0, 'validate' => $c['validate'],
            'status' => 'pending', 'expires' => time() + 3 * DAY_IN_SECONDS,
        ];
        if (add_option($key, $record, '', false)) {
            wp_schedule_single_event(time() + 1, self::SEND, [$key]);
        }
    }

    public function send($key) {
        if (strpos($key, self::QUEUE) !== 0 || !$this->ready()) { return; }
        $record = get_option($key);
        if (!$record || ($record['status'] ?? '') !== 'pending') { return; }
        // Mode changes require a fresh event: never turn validation data into live conversions.
        $config = $this->config();
        if ($record['validate'] !== $config['validate'] || $record['expires'] <= time()) {
            delete_option($key);
            return;
        }
        $lock = $key . '_lock';
        if (!add_option($lock, ['expires' => time() + 60], '', false)) { return; }
        try {
            $response = wp_remote_post('https://bzr.openai.com/v1/events?pid=' . rawurlencode($config['pixel']), [
                'timeout' => 15, 'redirection' => 0, 'limit_response_size' => 32768,
                'headers' => [
                    'Content-Type' => 'application/json',
                    'Authorization' => 'Bearer ' . $config['key'],
                ],
                'body' => wp_json_encode([
                    'validate_only' => $record['validate'], 'events' => [$record['event']],
                ]),
                'data_format' => 'body',
            ]);
            $code = is_wp_error($response) ? 0 : (int) wp_remote_retrieve_response_code($response);
            $attempts = $record['attempts'] + 1;
            if ($code >= 200 && $code < 300) {
                // Do not retain the click reference after successful delivery.
                update_option($key, [
                    'status' => 'sent', 'validate' => $record['validate'],
                    'attempts' => $attempts, 'expires' => time() + 3 * DAY_IN_SECONDS,
                ], false);
            } elseif (Core::retryable($code) && $attempts < 6) {
                $record['attempts'] = $attempts;
                update_option($key, $record, false);
                wp_schedule_single_event(time() + min(3600, 60 * (2 ** $attempts)), self::SEND, [$key]);
            } else {
                update_option($key, [
                    'status' => 'failed', 'http_code' => $code, 'attempts' => $attempts,
                    'expires' => time() + 3 * DAY_IN_SECONDS,
                ], false);
            }
        } finally {
            delete_option($lock);
        }
    }

    public function assets() {
        if (!$this->ready() || is_admin()) { return; }
        wp_enqueue_script('lpv-chatgpt-conversions', plugins_url('assets/conversions.js', __FILE__), [], self::VERSION, true);
        wp_localize_script('lpv-chatgpt-conversions', 'LPVAdsConfig', [
            'sessionUrl' => rest_url('lpv-ads/v1/session'),
            'leadUrl' => rest_url('lpv-ads/v1/lead'),
            'privacyUrl' => get_privacy_policy_url(),
        ]);
    }

    public function admin_menu() {
        add_management_page('LPV — ChatGPT Ads', 'LPV — ChatGPT Ads', 'manage_options', 'lpv-chatgpt-ads', [$this, 'admin_page']);
    }

    public function admin_page() {
        if (!current_user_can('manage_options')) { return; }
        $config = $this->config();
        echo '<div class="wrap"><h1>LPV — ChatGPT Ads</h1>';
        echo '<p>Versão 0.1.0. Integração de solicitações recebidas pelo FormSubmit.</p><ul>';
        foreach ([
            'Integração habilitada' => $config['enabled'],
            'Privacidade revisada' => $config['privacy_ready'],
            'Pixel ID configurado' => $config['pixel'] !== '',
            'Chave CAPI configurada' => $config['key'] !== '',
            'Somente validação (não registra conversões)' => $config['validate'],
        ] as $label => $value) {
            echo '<li>' . esc_html($label) . ': ' . ($value ? 'Sim' : 'Não') . '</li>';
        }
        echo '</ul><p>A chave nunca é exibida. Consulte o README do plugin para configuração e testes.</p></div>';
    }

    public function cleanup() {
        global $wpdb;
        // Expire only this plugin's records, including stale worker locks.
        $patterns = [$wpdb->esc_like(self::RECEIPTS) . '%', $wpdb->esc_like(self::QUEUE) . '%'];
        foreach ($patterns as $pattern) {
            $names = $wpdb->get_col($wpdb->prepare(
                "SELECT option_name FROM {$wpdb->options} WHERE option_name LIKE %s LIMIT 2000", $pattern
            ));
            foreach ($names as $name) {
                $record = get_option($name);
                if (is_array($record) && ($record['expires'] ?? PHP_INT_MAX) <= time()) {
                    delete_option($name);
                }
            }
        }
    }
}

$lpv_ads_plugin = new Plugin();
register_activation_hook(__FILE__, function () {
    if (!wp_next_scheduled(Plugin::CLEANUP)) {
        wp_schedule_event(time() + HOUR_IN_SECONDS, 'daily', Plugin::CLEANUP);
    }
});
register_deactivation_hook(__FILE__, function () {
    wp_clear_scheduled_hook(Plugin::CLEANUP);
    wp_clear_scheduled_hook(Plugin::SEND);
});
