<?php
/** Standalone scope harness for the LPV LiteSpeed Page Optimization filter. */
error_reporting( E_ALL );
define( 'ABSPATH', __DIR__ . '/' );

$GLOBALS['filters'] = array();
$GLOBALS['state'] = array();
$GLOBALS['pagenow'] = 'index.php';

function add_action( $hook, $callback, $priority = 10 ) {}
function add_filter( $hook, $callback, $priority = 10 ) { $GLOBALS['filters'][ $hook ] = $callback; }
function wp_parse_url( $url, $component = -1 ) { return parse_url( $url, $component ); }
function wp_unslash( $value ) { return $value; }
function trailingslashit( $value ) { return rtrim( $value, '/\\' ) . '/'; }
function is_admin() { return $GLOBALS['state']['admin']; }
function wp_doing_ajax() { return $GLOBALS['state']['ajax']; }
function wp_doing_cron() { return $GLOBALS['state']['cron']; }
function is_feed() { return $GLOBALS['state']['feed']; }
function is_embed() { return $GLOBALS['state']['embed']; }
function is_preview() { return $GLOBALS['state']['preview']; }
function is_search() { return $GLOBALS['state']['search']; }
function is_404() { return $GLOBALS['state']['404']; }
function is_singular( $type ) { return 'page' === $type && $GLOBALS['state']['singular']; }
function wp_is_block_theme() { return $GLOBALS['state']['block']; }
function get_template() { return $GLOBALS['state']['theme']; }
function get_queried_object_id() { return $GLOBALS['state']['id']; }
function get_permalink( $id ) { return $GLOBALS['state']['permalink']; }
function is_front_page() { return $GLOBALS['state']['front']; }
function get_option( $name ) { return $GLOBALS['state'][ $name ] ?? false; }

function fixture( $id, $path ) {
	$GLOBALS['state'] = array(
		'id' => $id, 'permalink' => 'https://lpvturismo.com' . $path,
		'admin' => false, 'ajax' => false, 'cron' => false, 'feed' => false,
		'embed' => false, 'preview' => false, 'search' => false, '404' => false,
		'singular' => true, 'block' => true, 'theme' => 'twentytwentyfive',
		'front' => 7 === $id, 'show_on_front' => 'page', 'page_on_front' => 7,
	);
	$_SERVER['REQUEST_URI'] = $path;
	$GLOBALS['pagenow'] = 'index.php';
}

$assertions = 0;
function same( $expected, $actual, $label ) {
	++$GLOBALS['assertions'];
	if ( $expected !== $actual ) {
		throw new RuntimeException( $label . ': expected ' . var_export( $expected, true )
			. ', got ' . var_export( $actual, true ) );
	}
}

try {
	$source_b64 = getenv( 'LPV_PLUGIN_SOURCE_B64' );
	if ( $source_b64 ) {
		$source = base64_decode( $source_b64, true );
	} else {
		$source = file_get_contents( dirname( __DIR__, 2 )
			. '/wordpress/plugins/lpv-page-templates/lpv-page-templates.php' );
	}
	if ( false === $source ) {
		throw new RuntimeException( 'Plugin source unavailable.' );
	}
	$source = preg_replace( '/^<\?php\s*/', '', $source, 1 );
	eval( $source );
	$filter = $GLOBALS['filters']['litespeed_can_optm'] ?? null;
	same( 'lpv_page_templates_litespeed_can_optm', $filter, 'Native LiteSpeed filter registered' );

	$paths = array(
		7 => '/', 17 => '/passeios/', 18 => '/outros-servicos/',
		19 => '/quero-montar-meu-roteiro/', 84 => '/passeios/mosaicos-do-rio/',
		85 => '/passeios/imersao-floresta-da-tijuca/', 86 => '/passeios/rio-essencial/',
		255 => '/lp-experiences/', 20 => '/es/', 237 => '/es/paseos/',
		205 => '/es/servicios/', 203 => '/es/quiero-armar-mi-itinerario/',
		160 => '/es/mosaicos-del-rio/', 194 => '/es/inmersion-floresta-da-tijuca/',
		195 => '/es/rio-esencial/', 21 => '/en/', 239 => '/en/tours/',
		217 => '/en/services/', 218 => '/en/plan-my-itinerary/',
		219 => '/en/mosaics-of-rio/', 220 => '/en/tijuca-forest-immersion/',
		221 => '/en/rio-essential/',
	);
	same( $paths, lpv_page_templates_paths(), 'Exact approved map' );
	foreach ( $paths as $id => $path ) {
		fixture( $id, $path );
		same( false, $filter( true ), 'Bypass exact route ' . $path );
		$_SERVER['REQUEST_URI'] = $path . '?utm_source=scope-test';
		same( false, $filter( true ), 'Bypass exact route with query ' . $path );
	}

	fixture( 17, '/passeios/' );
	foreach ( array( 'admin', 'ajax', 'cron', 'feed', 'embed', 'preview', 'search', '404' ) as $context ) {
		fixture( 17, '/passeios/' );
		$GLOBALS['state'][ $context ] = true;
		same( true, $filter( true ), 'Excluded context ' . $context );
	}
	fixture( 17, '/passeios/' );
	$GLOBALS['pagenow'] = 'wp-login.php';
	same( true, $filter( true ), 'Login excluded' );
	fixture( 999, '/politica-de-privacidade/' );
	same( true, $filter( true ), 'Privacy excluded' );
	fixture( 999, '/not-mapped/' );
	same( true, $filter( true ), 'Nonmapped page excluded' );
	fixture( 17, '/passeios/' );
	$GLOBALS['state']['singular'] = false;
	same( true, $filter( true ), 'Posts and archives excluded' );
	foreach ( array( '/passeios-extra/', '/passeios/subpath/', '/passeios%2F', '/wp-json/' ) as $path ) {
		fixture( 17, '/passeios/' );
		$_SERVER['REQUEST_URI'] = $path;
		same( true, $filter( true ), 'Similar or REST path excluded ' . $path );
	}
	fixture( 17, '/passeios/' );
	same( false, $filter( false ), 'Existing false decision remains false' );
	define( 'REST_REQUEST', true );
	same( true, $filter( true ), 'REST request constant excluded' );

	echo 'PASS: ' . $assertions . " assertions; LiteSpeed scope is exact and cache-independent.\n";
} catch ( Throwable $error ) {
	fwrite( STDERR, $error->getMessage() . "\n" );
	exit( 1 );
}
