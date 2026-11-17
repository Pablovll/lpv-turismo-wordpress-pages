<?php
/**
 * Plugin Name: LPV ChatGPT Conversions
 * Description: Confirmed FormSubmit leads to OpenAI CAPI, with optional visitor consent.
 * Version: 0.2.0
 * Requires PHP: 7.4
 * Requires at least: 6.2
 * Author: LPV Turismo
 */
namespace LPV\ChatGPTAds;

if (!defined('ABSPATH')) { exit; }
require_once __DIR__ . '/includes/core.php';
require_once __DIR__ . '/includes/secrets.php';

final class Plugin {
    const VERSION = '0.2.0';
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
        add_action('admin_post_lpv_ads_save', [$this, 'save_settings']);
        add_action('admin_post_lpv_ads_validate', [$this, 'validate_credentials']);
    }

    private function settings() {
        $settings = get_option('lpv_ads_settings');
        return is_array($settings) ? $settings : [];
    }

    private function secret_salt() {
        return wp_salt('auth') . wp_salt('secure_auth');
    }

    public function config() {
        $saved = $this->settings();
        return [
            'enabled' => defined('LPV_ADS_ENABLED') ? LPV_ADS_ENABLED === true : !empty($saved['enabled']),
            'privacy_ready' => defined('LPV_ADS_PRIVACY_READY') ? LPV_ADS_PRIVACY_READY === true : !empty($saved['privacy_ready']),
            'pixel' => defined('LPV_ADS_PIXEL_ID') ? (string) LPV_ADS_PIXEL_ID : ($saved['pixel'] ?? 'RhD2bsVtU7zYjLxg3Z2KGq'),
            'key' => defined('LPV_ADS_CAPI_KEY') ? (string) LPV_ADS_CAPI_KEY : Secrets::decrypt($saved['encrypted_key'] ?? '', $this->secret_salt()),
            'validate' => defined('LPV_ADS_VALIDATE_ONLY') ? LPV_ADS_VALIDATE_ONLY !== false : ($saved['validate'] ?? true) !== false,
        ];
    }

    public function settings_from_input($input) {
        if (!is_array($input)) { throw new \InvalidArgumentException('invalid_settings'); }
        $saved = $this->settings();
        $pixel = $input['pixel'] ?? '';
        $key = $input['key'] ?? '';
        if (!is_string($pixel) || !preg_match('/^[A-Za-z0-9_-]{1,200}$/D', $pixel)
            || !is_string($key) || strlen($key) > 4096 || preg_match('/[\x00-\x20\x7f]/', $key)) {
            throw new \InvalidArgumentException('invalid_settings');
        }
        $saved['pixel'] = $pixel;
        // Saving a blank password input preserves the existing protected key.
        if (!empty($input['delete_key'])) { unset($saved['encrypted_key']); }
        elseif ($key !== '') { $saved['encrypted_key'] = Secrets::encrypt($key, $this->secret_salt()); }
        $saved['enabled'] = !empty($input['enabled']);
        $saved['privacy_ready'] = !empty($input['privacy_ready']);
        $saved['validate'] = empty($input['live']);
        return $saved;
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
        add_options_page('LPV — ChatGPT Ads', 'LPV — ChatGPT Ads', 'manage_options', 'lpv-chatgpt-ads', [$this, 'admin_page']);
    }

    public function save_settings() {
        if (!current_user_can('manage_options')) { wp_die('Acesso negado.', '', ['response' => 403]); }
        check_admin_referer('lpv_ads_save');
        try {
            $input = isset($_POST['lpv_ads']) ? wp_unslash($_POST['lpv_ads']) : [];
            update_option('lpv_ads_settings', $this->settings_from_input($input), false);
            set_transient('lpv_ads_admin_notice_' . get_current_user_id(), 'Configuração salva. A chave não será exibida novamente.', MINUTE_IN_SECONDS);
        } catch (\Exception $e) {
            set_transient('lpv_ads_admin_notice_' . get_current_user_id(), 'Não foi possível salvar. Confira o Pixel ID e o formato da chave; verifique se a hospedagem oferece OpenSSL AES-GCM.', MINUTE_IN_SECONDS);
        }
        wp_safe_redirect(admin_url('options-general.php?page=lpv-chatgpt-ads'));
        exit;
    }

    public function validate_credentials() {
        if (!current_user_can('manage_options')) { wp_die('Acesso negado.', '', ['response' => 403]); }
        check_admin_referer('lpv_ads_validate');
        $config = $this->config();
        if ($config['pixel'] === '' || $config['key'] === '') {
            $message = 'Salve o Pixel ID e a chave CAPI antes de testar.';
        } else {
            // This test never reads a customer form or records a live conversion.
            $response = wp_remote_post('https://bzr.openai.com/v1/events?pid=' . rawurlencode($config['pixel']), [
                'timeout' => 15, 'redirection' => 0, 'limit_response_size' => 32768,
                'headers' => [
                    'Content-Type' => 'application/json',
                    'Authorization' => 'Bearer ' . $config['key'],
                ],
                'body' => wp_json_encode([
                    'validate_only' => true,
                    'events' => [[
                        'id' => 'lpv_validation_' . wp_generate_uuid4(),
                        'type' => 'lead_created',
                        'timestamp_ms' => (int) floor(microtime(true) * 1000),
                        'action_source' => 'web',
                        'source_url' => home_url('/quero-montar-meu-roteiro/'),
                        'data' => ['type' => 'customer_action'],
                    ]],
                ]),
                'data_format' => 'body',
            ]);
            $code = is_wp_error($response) ? 0 : (int) wp_remote_retrieve_response_code($response);
            $message = ($code >= 200 && $code < 300)
                ? 'Validação aceita pela API. Nenhuma conversão real foi registrada. Isto ainda não testa o formulário nem a atribuição ao anúncio.'
                : 'A validação não foi aceita. Confira se a chave é da CAPI do Gerenciador de Anúncios e pertence à mesma conta do Pixel ID. Código HTTP: ' . $code . '.';
        }
        // Never store or render the upstream response, which may include sensitive diagnostics.
        set_transient('lpv_ads_admin_notice_' . get_current_user_id(), $message, MINUTE_IN_SECONDS);
        wp_safe_redirect(admin_url('options-general.php?page=lpv-chatgpt-ads'));
        exit;
    }

    public function admin_page() {
        if (!current_user_can('manage_options')) { return; }
        $config = $this->config();
        echo '<div class="wrap"><h1>LPV — ChatGPT Ads</h1>';
        echo '<p>Versão ' . esc_html(self::VERSION) . '. Primeiro salve a chave e teste a conexão. Deixe a integração desativada até concluir a revisão.</p>';
        $notice_key = 'lpv_ads_admin_notice_' . get_current_user_id();
        $notice = get_transient($notice_key);
        if (is_string($notice) && $notice !== '') {
            echo '<div class="notice notice-info"><p>' . esc_html($notice) . '</p></div>';
            delete_transient($notice_key);
        }
        if (!Secrets::available()) {
            echo '<div class="notice notice-error"><p>A hospedagem precisa oferecer OpenSSL AES-GCM para guardar a chave pelo painel. Nenhuma chave será gravada sem essa proteção.</p></div>';
        }
        echo '<p>Chave CAPI: <strong>' . ($config['key'] !== '' ? 'configurada' : 'não configurada') . '</strong>. Salvar a chave não envia dados de visitantes.</p>';
        foreach (['LPV_ADS_ENABLED', 'LPV_ADS_PRIVACY_READY', 'LPV_ADS_PIXEL_ID', 'LPV_ADS_CAPI_KEY', 'LPV_ADS_VALIDATE_ONLY'] as $constant) {
            if (defined($constant)) {
                echo '<p><strong>Configuração técnica existente:</strong> ' . esc_html($constant) . ' tem prioridade sobre o painel. Peça ao responsável técnico para revisar essa definição.</p>';
            }
        }
        echo '<form method="post" action="' . esc_url(admin_url('admin-post.php')) . '">';
        echo '<input type="hidden" name="action" value="lpv_ads_save">';
        wp_nonce_field('lpv_ads_save');
        echo '<table class="form-table"><tr><th><label for="lpv-ads-pixel">Pixel ID</label></th><td>';
        echo '<input class="regular-text" id="lpv-ads-pixel" name="lpv_ads[pixel]" type="text" value="' . esc_attr($config['pixel']) . '" required></td></tr>';
        echo '<tr><th><label for="lpv-ads-key">Chave CAPI</label></th><td>';
        echo '<input class="regular-text" id="lpv-ads-key" name="lpv_ads[key]" type="password" value="" autocomplete="new-password" spellcheck="false">';
        echo '<p class="description">Cole aqui a chave gerada no Gerenciador de Anúncios. Se já estiver configurada, deixe em branco para manter. A chave é criptografada no banco de dados deste WordPress.</p>';
        echo '<label><input type="checkbox" name="lpv_ads[delete_key]" value="1"> Remover a chave salva no painel</label></td></tr></table>';
        foreach ([
            'enabled' => ['Ativar integração no site', $config['enabled']],
            'privacy_ready' => ['A atualização de privacidade foi revisada e publicada', $config['privacy_ready']],
            'live' => ['Registrar conversões reais (deixe desmarcado durante a configuração)', !$config['validate']],
        ] as $name => $field) {
            echo '<p><label><input type="checkbox" name="lpv_ads[' . esc_attr($name) . ']" value="1"' . ($field[1] ? ' checked' : '') . '> ' . esc_html($field[0]) . '</label></p>';
        }
        echo '<p><button class="button button-primary" type="submit">Salvar configuração</button></p></form>';
        echo '<hr><h2>Testar a conexão</h2><p>Envia apenas um exemplo técnico sem dados de clientes, em modo de validação. Não envia formulário nem registra conversão real.</p>';
        echo '<form method="post" action="' . esc_url(admin_url('admin-post.php')) . '"><input type="hidden" name="action" value="lpv_ads_validate">';
        wp_nonce_field('lpv_ads_validate');
        echo '<button class="button" type="submit">Testar conexão sem registrar conversão</button></form></div>';
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
