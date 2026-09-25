<?php
/**
 * Temporary LPV production deployment shield.
 *
 * This template is rendered by scripts/deploy_production.py. It is never a
 * permanent production component.
 */

defined( 'ABSPATH' ) || exit;

if ( defined( 'WP_CLI' ) && WP_CLI ) {
	return;
}

define( 'LPV_DEPLOY_SHIELD_TOKEN_HASH', '__LPV_DEPLOY_TOKEN_HASH__' );
define( 'LPV_DEPLOY_SHIELD_EXPIRES_AT', __LPV_DEPLOY_EXPIRES_AT__ );

function lpv_deploy_shield_is_active() {
	return time() <= LPV_DEPLOY_SHIELD_EXPIRES_AT;
}

function lpv_deploy_shield_token_is_valid() {
	$token = isset( $_SERVER['HTTP_X_LPV_DEPLOY_TOKEN'] )
		? trim( (string) wp_unslash( $_SERVER['HTTP_X_LPV_DEPLOY_TOKEN'] ) )
		: '';

	return '' !== $token && hash_equals( LPV_DEPLOY_SHIELD_TOKEN_HASH, hash( 'sha256', $token ) );
}

function lpv_deploy_shield_rest_authentication( $result ) {
	if ( ! lpv_deploy_shield_is_active() || lpv_deploy_shield_token_is_valid() ) {
		return $result;
	}

	return new WP_Error(
		'service_unavailable',
		__( 'Temporarily unavailable. Please try again shortly.', 'lpv-deploy-shield' ),
		array( 'status' => 503 )
	);
}
add_filter( 'rest_authentication_errors', 'lpv_deploy_shield_rest_authentication', PHP_INT_MIN );

function lpv_deploy_shield_rest_retry_after( $response ) {
	if ( lpv_deploy_shield_is_active() && ! lpv_deploy_shield_token_is_valid() ) {
		$response->header( 'Retry-After', '120' );
	}

	return $response;
}
add_filter( 'rest_post_dispatch', 'lpv_deploy_shield_rest_retry_after', PHP_INT_MAX );

function lpv_deploy_shield_frontend() {
	if ( ! lpv_deploy_shield_is_active() || lpv_deploy_shield_token_is_valid()
		|| is_admin() || wp_doing_ajax() || wp_doing_cron() ) {
		return;
	}

	status_header( 503 );
	nocache_headers();
	header( 'Retry-After: 120' );
	header( 'Content-Type: text/plain; charset=utf-8' );
	echo esc_html__( 'Temporarily unavailable. Please try again shortly.', 'lpv-deploy-shield' );
	exit;
}
add_action( 'template_redirect', 'lpv_deploy_shield_frontend', PHP_INT_MIN );
