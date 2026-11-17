<?php
namespace LPV\ChatGPTAds;

final class Secrets {
    const AAD = 'lpv-chatgpt-conversions-key-v1';

    public static function available() {
        return function_exists('openssl_encrypt') && function_exists('openssl_decrypt')
            && in_array('aes-256-gcm', openssl_get_cipher_methods(), true);
    }

    public static function encrypt($value, $salt) {
        if (!self::available()) { throw new \RuntimeException('encryption_unavailable'); }
        $iv = random_bytes(12);
        $tag = '';
        $key = hash('sha256', $salt, true);
        $ciphertext = openssl_encrypt($value, 'aes-256-gcm', $key, OPENSSL_RAW_DATA, $iv, $tag, self::AAD, 16);
        if ($ciphertext === false || strlen($tag) !== 16) {
            throw new \RuntimeException('encryption_failed');
        }
        return 'v1:' . base64_encode($iv . $tag . $ciphertext);
    }

    public static function decrypt($encoded, $salt) {
        if (!self::available() || !is_string($encoded) || strpos($encoded, 'v1:') !== 0) { return ''; }
        $raw = base64_decode(substr($encoded, 3), true);
        if ($raw === false || strlen($raw) <= 28) { return ''; }
        $value = openssl_decrypt(
            substr($raw, 28), 'aes-256-gcm', hash('sha256', $salt, true),
            OPENSSL_RAW_DATA, substr($raw, 0, 12), substr($raw, 12, 16), self::AAD
        );
        return $value === false ? '' : $value;
    }
}
