<?php
/** Apply or restore Additional CSS through the native WordPress API. */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}
if ( empty( $args[0] ) || ! is_readable( $args[0] ) ) {
	WP_CLI::error( 'Missing CSS payload.' );
}
$payload = json_decode( file_get_contents( $args[0] ), true );
$current = wp_get_custom_css( get_stylesheet() );
if ( ! is_array( $payload ) || empty( $payload['expected_sha256'] )
	|| ! hash_equals( $payload['expected_sha256'], hash( 'sha256', $current ) ) ) {
	WP_CLI::error( 'Concurrent CSS change detected.' );
}
$target = base64_decode( $payload['target_b64'], true );
if ( false === $target || ! hash_equals( $payload['target_sha256'], hash( 'sha256', $target ) ) ) {
	WP_CLI::error( 'Invalid target CSS.' );
}
$before = array( 'bytes' => strlen( $current ), 'sha256' => hash( 'sha256', $current ) );
$wanted = array( 'bytes' => strlen( $target ), 'sha256' => hash( 'sha256', $target ) );
if ( hash_equals( $before['sha256'], $wanted['sha256'] ) ) {
	echo 'LPV_RESULT:' . wp_json_encode( array(
		'status' => 'APROVADO', 'changed' => false, 'before' => $before,
		'target' => $wanted, 'saved' => $before,
	) );
	return;
}
$result = wp_update_custom_css_post( $target, array( 'stylesheet' => get_stylesheet() ) );
if ( is_wp_error( $result ) ) {
	WP_CLI::error( 'WordPress rejected CSS: ' . $result->get_error_code() );
}
$saved = wp_get_custom_css( get_stylesheet() );
if ( ! hash_equals( $payload['target_sha256'], hash( 'sha256', $saved ) ) ) {
	wp_update_custom_css_post( $current, array( 'stylesheet' => get_stylesheet() ) );
	WP_CLI::error( 'Saved CSS differs; original CSS restored.' );
}
echo 'LPV_RESULT:' . wp_json_encode( array(
	'status' => 'APROVADO', 'changed' => true, 'before' => $before,
	'target' => $wanted,
	'saved' => array( 'bytes' => strlen( $saved ), 'sha256' => hash( 'sha256', $saved ) ),
) );
