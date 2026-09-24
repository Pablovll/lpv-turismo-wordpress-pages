<?php
/** Offline core tests. Request, theme and database access use explicit fixtures. */
error_reporting( E_ALL );
$options = getopt( '', array( 'wordpress-core:' ) );
$core = isset( $options['wordpress-core'] ) ? rtrim( $options['wordpress-core'], '/\\' ) : getenv( 'WP_TEMPLATE_CORE_DIR' );
if ( ! $core || ! is_file( $core . '/wp-includes/class-wp-block-templates-registry.php' ) ) {
	fwrite( STDERR, "Provide local WordPress 6.7+ core via --wordpress-core.\n" );
	exit( 1 );
}
define( 'ABSPATH', $core . '/' );
define( 'WPINC', 'wp-includes' );
foreach ( array( 'plugin.php', 'class-wp-error.php', 'class-wp-block-template.php',
	'class-wp-block-templates-registry.php', 'block-template-utils.php', 'block-template.php',
	'class-wp-block-parser-block.php', 'class-wp-block-parser-frame.php', 'class-wp-block-parser.php',
	'blocks.php', 'http.php' ) as $file ) {
	require_once $core . '/wp-includes/' . $file;
}

function __( $text ) { return $text; }
function _x( $text, $context ) { return $text; }
function _doing_it_wrong( $function, $message, $version ) { throw new RuntimeException( $message ); }
function is_wp_error( $value ) { return $value instanceof WP_Error; }
function wp_parse_args( $args, $defaults = array() ) { return array_merge( $defaults, $args ); }
function wp_list_pluck( $items, $field ) { return array_map( function ( $item ) use ( $field ) { return $item->$field; }, $items ); }
function get_stylesheet() { return 'twentytwentyfive'; }
function get_template() { return $GLOBALS['state']['theme']; }
function get_stylesheet_directory() { return __DIR__ . '/nonexistent-theme'; }
function get_template_directory() { return get_stylesheet_directory(); }
function wp_get_theme( $name = null ) { return new class { public function exists() { return false; } }; }
class WP_Query { public $posts = array(); public function __construct( $args ) {} }
function wp_is_block_theme() { return $GLOBALS['state']['block']; }
function is_admin() { return $GLOBALS['state']['admin']; }
function is_feed() { return $GLOBALS['state']['feed']; }
function is_embed() { return $GLOBALS['state']['embed']; }
function is_singular( $type ) { return 'page' === $type && $GLOBALS['state']['singular']; }
function is_front_page() { return $GLOBALS['state']['front']; }
function get_queried_object_id() { return $GLOBALS['state']['id']; }
function get_permalink( $id ) { return $GLOBALS['state']['url']; }
function get_option( $key ) { return $GLOBALS['state'][ $key ] ?? false; }
function wpautop( $content ) { return '<p>' . $content . '</p>'; }

$root = dirname( __DIR__, 2 );
$rows = json_decode( file_get_contents( $root . '/docs/stage-4-language-map.json' ), true, 512, JSON_THROW_ON_ERROR )['pages'];
$assertions = 0;
function reset_fixture( $id = 7, $path = '/' ) {
	$GLOBALS['state'] = array( 'id' => $id, 'url' => 'https://staging.example.test' . $path,
		'theme' => 'twentytwentyfive', 'block' => true, 'admin' => false,
		'feed' => false, 'embed' => false, 'singular' => true, 'front' => 7 === $id,
		'show_on_front' => 'page', 'page_on_front' => '7' );
}
function same( $expected, $actual, $label ) {
	++$GLOBALS['assertions'];
	if ( $expected !== $actual ) {
		throw new RuntimeException( $label . "\nExpected: " . var_export( $expected, true ) . "\nActual: " . var_export( $actual, true ) );
	}
}
function blocks_named( $blocks ) {
	$names = array();
	foreach ( $blocks as $block ) {
		if ( null !== $block['blockName'] ) { $names[] = $block['blockName']; }
		$names = array_merge( $names, blocks_named( $block['innerBlocks'] ) );
	}
	return $names;
}

try {
	reset_fixture();
	require $root . '/wordpress/plugins/lpv-page-templates/lpv-page-templates.php';
	$hooks_before = array_keys( $GLOBALS['wp_filter'] );
	do_action( 'init' );
	$new_hooks = array_values( array_diff( array_keys( $GLOBALS['wp_filter'] ), $hooks_before ) );
	sort( $new_hooks );
	same( array( 'frontpage_template_hierarchy', 'page_template_hierarchy' ), $new_hooks, 'Only template hierarchy filters' );
	$registry = WP_Block_Templates_Registry::get_instance();
	$template = $registry->get_registered( 'lpv-page-templates//lpv-content-only' );
	same( true, $template instanceof WP_Block_Template, 'Native template registered' );
	same( 'plugin', $template->source, 'Template comes from plugin' );
	same( array( 'page' ), $template->post_types, 'Page template only' );
	same( file_get_contents( $root . '/wordpress/templates/lpv-content-only.html' ), $template->content, 'Canonical template unchanged' );
	$parsed = parse_blocks( $template->content );
	same( array( 'core/group', 'core/post-content' ), blocks_named( $parsed ), 'Only group and Post Content' );
	same( 'main', $parsed[0]['attrs']['tagName'], 'Main belongs to template' );
	same( 'default', $parsed[0]['attrs']['layout']['type'], 'No constrained layout' );
	same( '0', $parsed[0]['attrs']['style']['spacing']['margin']['top'], 'No theme top margin' );
	$map = array();
	foreach ( $rows as $row ) { $map[ $row['id'] ] = $row['url']; }
	$actual = lpv_page_templates_paths();
	ksort( $map );
	ksort( $actual );
	same( $map, $actual, 'Exact approved paths and IDs' );

	foreach ( $rows as $row ) {
		reset_fixture( $row['id'], $row['url'] );
		$type = 7 === $row['id'] ? 'frontpage' : 'page';
		$original = array( 7 === $row['id'] ? 'front-page.php' : 'page.php', 'index.php' );
		$hierarchy = apply_filters( $type . '_template_hierarchy', $original );
		same( array_merge( array( 'lpv-content-only.php' ), $original ), $hierarchy, 'Selected ' . $row['id'] );
		same( $hierarchy, apply_filters( $type . '_template_hierarchy', $hierarchy ), 'No duplicate candidate' );
		// Core registry, template query and resolver; no DB records or theme files in fixture.
		$resolved = resolve_block_template( $type, $hierarchy, '' );
		same( $template->id, $resolved->id, 'Core resolves LPV ' . $row['id'] );
		same( $template->content, $resolved->content, 'Resolved content preserved' );
		$GLOBALS['state']['url'] = $row['canonical'];
		same( $hierarchy, apply_filters( $type . '_template_hierarchy', $original ), 'Official domain accepted' );
		foreach ( array( '/wrong/', '/clone' . $row['url'] ) as $path ) {
			$GLOBALS['state']['url'] = 'https://staging.example.test' . $path;
			same( $original, apply_filters( $type . '_template_hierarchy', $original ), 'Reject mismatched path' );
		}
	}

	$original = array( 'page.php', 'index.php' );
	foreach ( array( 'admin', 'feed', 'embed' ) as $key ) {
		reset_fixture( 17, '/passeios/' );
		$GLOBALS['state'][ $key ] = true;
		same( $original, apply_filters( 'page_template_hierarchy', $original ), 'Excluded context ' . $key );
	}
	foreach ( array( 'singular', 'block' ) as $key ) {
		reset_fixture( 17, '/passeios/' );
		$GLOBALS['state'][ $key ] = false;
		same( $original, apply_filters( 'page_template_hierarchy', $original ), 'Excluded context ' . $key );
	}
	foreach ( array( 0, 999, 256 ) as $id ) {
		reset_fixture( $id, '/politica-de-privacidade/' );
		same( $original, apply_filters( 'page_template_hierarchy', $original ), 'Unmapped ID' );
	}
	reset_fixture( 17, '/passeios/' );
	$GLOBALS['state']['theme'] = 'another-theme';
	same( $original, apply_filters( 'page_template_hierarchy', $original ), 'Other theme unchanged' );
	$GLOBALS['state']['theme'] = 'twentytwentyfive';
	$GLOBALS['state']['url'] = false;
	same( $original, apply_filters( 'page_template_hierarchy', $original ), 'Missing permalink unchanged' );
	foreach ( array( array( 'show_on_front', 'posts' ), array( 'page_on_front', 20 ), array( 'front', false ) ) as $change ) {
		reset_fixture();
		$GLOBALS['state'][ $change[0] ] = $change[1];
		same( $original, apply_filters( 'frontpage_template_hierarchy', $original ), 'Wrong front-page setup' );
	}
	reset_fixture( 20, '/es/' );
	$GLOBALS['state']['front'] = true;
	same( $original, apply_filters( 'frontpage_template_hierarchy', $original ), 'Do not replace alternate front page' );

	reset_fixture( 17, '/passeios/' );
	add_filter( 'the_content', 'wpautop' );
	do_action( 'wp' );
	same( false, has_filter( 'the_content', 'wpautop' ), 'Managed page disables wpautop' );
	reset_fixture( 999, '/politica-de-privacidade/' );
	add_filter( 'the_content', 'wpautop' );
	do_action( 'wp' );
	same( 10, has_filter( 'the_content', 'wpautop' ), 'Unmapped page retains wpautop' );
	remove_filter( 'the_content', 'wpautop' );

	// A saved template may override the plugin. This is an explicit manual preflight gate.
	reset_fixture();
	$override = clone $template;
	$override->content = '<!-- wp:post-title /-->';
	$fixture = function () use ( $override ) { return array( $override ); };
	add_filter( 'pre_get_block_templates', $fixture );
	same( $override->content, resolve_block_template( 'frontpage', array( 'lpv-content-only.php' ), '' )->content,
		'Core customization precedence is not bypassed' );
	remove_filter( 'pre_get_block_templates', $fixture );
	$registry->unregister( 'lpv-page-templates//lpv-content-only' );
	remove_filter( 'page_template_hierarchy', 'lpv_page_templates_hierarchy', 20 );
	remove_filter( 'frontpage_template_hierarchy', 'lpv_page_templates_hierarchy', 20 );
	same( $original, apply_filters( 'frontpage_template_hierarchy', $original ), 'No persistent assignment after unload' );
	$GLOBALS['state']['theme'] = 'another-theme';
	lpv_page_templates_register();
	same( null, $registry->get_registered( 'lpv-page-templates//lpv-content-only' ), 'Do not register for another theme' );

	$canvas = file_get_contents( $core . '/wp-includes/template-canvas.php' );
	foreach ( array( 'language_attributes();', 'wp_head();', 'wp_body_open();', 'wp_footer();' ) as $hook ) {
		same( true, false !== strpos( $canvas, $hook ), 'Native canvas retains ' . $hook );
	}
	echo 'PASS: ' . $assertions . " assertions; template scope and native resolution (offline fixtures).\n";
} catch ( Throwable $error ) {
	fwrite( STDERR, $error->getMessage() . "\n" . $error->getTraceAsString() . "\n" );
	exit( 1 );
}
