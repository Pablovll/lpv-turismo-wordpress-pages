<?php
/** Offline harness for the rendered LPV Deploy Shield. */

if ( 2 !== $argc ) {
	fwrite( STDERR, "Usage: php test_lpv_deploy_shield.php <rendered-shield>\n" );
	exit( 2 );
}

define( 'ABSPATH', __DIR__ );
if ( '1' === getenv( 'LPV_TEST_WP_CLI' ) ) {
	define( 'WP_CLI', true );
}

$GLOBALS['lpv_filters'] = array();
$GLOBALS['lpv_actions'] = array();

function add_filter( $name, $callback ) {
	$GLOBALS['lpv_filters'][ $name ] = $callback;
}
function add_action( $name, $callback ) {
	$GLOBALS['lpv_actions'][ $name ] = $callback;
}
function wp_unslash( $value ) {
	return $value;
}
function __( $value ) {
	return $value;
}
function esc_html__( $value ) {
	return htmlspecialchars( $value, ENT_QUOTES, 'UTF-8' );
}
function is_admin() {
	return false;
}
function wp_doing_ajax() {
	return false;
}
function wp_doing_cron() {
	return false;
}
function status_header() {}
function nocache_headers() {}

class WP_Error {
	public $code;
	public $data;
	public function __construct( $code, $message, $data ) {
		$this->code = $code;
		$this->data = $data;
	}
}

class LPV_Test_Response {
	public $headers = array();
	public function header( $name, $value ) {
		$this->headers[ $name ] = $value;
	}
}

require $argv[1];

if ( defined( 'WP_CLI' ) && WP_CLI ) {
	if ( ! empty( $GLOBALS['lpv_filters'] ) || ! empty( $GLOBALS['lpv_actions'] ) ) {
		throw new RuntimeException( 'WP-CLI was not bypassed.' );
	}
	echo "LPV deploy shield WP-CLI harness: OK\n";
	exit( 0 );
}

if ( ! isset( $GLOBALS['lpv_filters']['rest_authentication_errors'] ) ) {
	throw new RuntimeException( 'REST filter was not registered.' );
}

unset( $_SERVER['HTTP_X_LPV_DEPLOY_TOKEN'] );
$blocked = call_user_func( $GLOBALS['lpv_filters']['rest_authentication_errors'], null );
if ( '1' === getenv( 'LPV_TEST_EXPECT_EXPIRED' ) ) {
	if ( null !== $blocked ) {
		throw new RuntimeException( 'Expired shield remained active.' );
	}
	echo "LPV deploy shield expiry harness: OK\n";
	exit( 0 );
}
if ( ! $blocked instanceof WP_Error || 503 !== $blocked->data['status'] ) {
	throw new RuntimeException( 'Public REST was not blocked.' );
}

$_SERVER['HTTP_X_LPV_DEPLOY_TOKEN'] = 'definitely-wrong';
$wrong = call_user_func( $GLOBALS['lpv_filters']['rest_authentication_errors'], null );
if ( ! $wrong instanceof WP_Error || 503 !== $wrong->data['status'] ) {
	throw new RuntimeException( 'Wrong deploy token was not blocked.' );
}

$_SERVER['HTTP_X_LPV_DEPLOY_TOKEN'] = getenv( 'LPV_TEST_DEPLOY_TOKEN' );
$allowed = call_user_func( $GLOBALS['lpv_filters']['rest_authentication_errors'], null );
if ( null !== $allowed ) {
	throw new RuntimeException( 'Authorized deploy REST was not allowed through the shield.' );
}

$response = new LPV_Test_Response();
unset( $_SERVER['HTTP_X_LPV_DEPLOY_TOKEN'] );
call_user_func( $GLOBALS['lpv_filters']['rest_post_dispatch'], $response );
if ( '120' !== $response->headers['Retry-After'] ) {
	throw new RuntimeException( 'Retry-After was not applied.' );
}

if ( '1' === getenv( 'LPV_TEST_FRONTEND' ) ) {
	call_user_func( $GLOBALS['lpv_actions']['template_redirect'] );
}

echo "LPV deploy shield harness: OK\n";
