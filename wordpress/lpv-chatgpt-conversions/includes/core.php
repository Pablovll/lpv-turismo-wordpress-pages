<?php
/**
 * Pure validation rules shared by the WordPress adapter and offline tests.
 */
namespace LPV\ChatGPTAds;

final class Core {
    public static function source_url($value, $home) {
        $url = parse_url((string) $value);
        $base = parse_url((string) $home);
        if (!$url || !$base || ($url['scheme'] ?? '') !== 'https'
            || isset($url['user']) || isset($url['pass'])
            || strtolower(preg_replace('/^www\./i', '', $url['host'] ?? ''))
               !== strtolower(preg_replace('/^www\./i', '', $base['host'] ?? ''))
            || ($url['port'] ?? 443) !== ($base['port'] ?? 443)) {
            throw new \InvalidArgumentException('invalid_origin');
        }
        $path = $url['path'] ?? '/';
        if (strlen($path) > 300 || preg_match('/[\x00-\x20\x7f]/', $path)) {
            throw new \InvalidArgumentException('invalid_path');
        }
        // Never forward URL queries/fragments, which can contain personal information.
        return 'https://' . $base['host'] . (isset($base['port']) ? ':' . $base['port'] : '') . $path;
    }

    public static function form_page($source, $home) {
        $safe = self::source_url($source, $home);
        $allowed = [
            '/quero-montar-meu-roteiro/',
            '/es/quiero-armar-mi-itinerario/',
            '/en/plan-my-itinerary/',
        ];
        if (!in_array(parse_url($safe, PHP_URL_PATH), $allowed, true)) {
            throw new \InvalidArgumentException('invalid_form_page');
        }
        return $safe;
    }

    public static function fields($values) {
        if (!is_array($values) || count($values) > 100) {
            throw new \InvalidArgumentException('invalid_fields');
        }
        $result = [];
        foreach ($values as $key => $value) {
            if (!is_string($key) || strlen($key) > 160 || !is_scalar($value)
                || strlen((string) $value) > 6000) {
                throw new \InvalidArgumentException('invalid_field');
            }
            if (isset($key[0]) && $key[0] === '_'
                && !in_array($key, ['_subject', '_template', '_captcha', '_honey'], true)) {
                continue;
            }
            $result[$key] = trim(strip_tags((string) $value));
        }
        if (!empty($result['_honey'])) {
            throw new \InvalidArgumentException('spam');
        }
        if (($result['_captcha'] ?? '') !== 'false') {
            // Never bypass a captcha enabled in an existing form.
            throw new \InvalidArgumentException('captcha_required');
        }
        $email = $result['Email'] ?? '';
        $name = $result['Nome'] ?? $result['Nombre'] ?? $result['Name'] ?? '';
        if (!filter_var($email, FILTER_VALIDATE_EMAIL) || $name === '') {
            throw new \InvalidArgumentException('missing_contact');
        }
        $result['_subject'] = str_replace(["\r", "\n"], ' ', $result['_subject'] ?? 'LPV Turismo — Solicitação');
        $result['_template'] = 'table';
        return $result;
    }

    public static function accepted($code, $body) {
        $data = json_decode((string) $body, true);
        return $code >= 200 && $code < 300 && is_array($data)
            && isset($data['success'])
            && ($data['success'] === true || $data['success'] === 'true')
            && !preg_match('/activat|confirm.{0,30}email/i', (string) ($data['message'] ?? ''));
    }

    public static function event($id, $source, $home, $oppref, $consent, $time_ms) {
        if ($consent !== true) {
            return null;
        }
        if (!preg_match('/^lpv_lead_[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/D', (string) $id)) {
            throw new \InvalidArgumentException('invalid_event_id');
        }
        if (!is_string($oppref) || strlen($oppref) > 4096 || preg_match('/[\x00-\x1f\x7f]/', $oppref)) {
            throw new \InvalidArgumentException('invalid_click_reference');
        }
        $event = [
            'id' => $id,
            'type' => 'lead_created',
            'timestamp_ms' => (int) $time_ms,
            'source_url' => self::form_page($source, $home),
            'action_source' => 'web',
            'data' => ['type' => 'customer_action'],
        ];
        if ($oppref !== '') {
            $event['oppref'] = $oppref; // Opaque value: never alter or hash it.
        }
        return $event;
    }

    public static function retryable($code) {
        return $code === 0 || $code === 408 || $code === 429 || $code >= 500;
    }
}
