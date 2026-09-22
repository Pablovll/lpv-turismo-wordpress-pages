<?php
/** Offline harness: real WP hooks/HTML API/escaping, in-memory request and post fixtures. */
error_reporting( E_ALL );
$options = getopt( '', array( 'wordpress-core:' ) );
$core = isset( $options['wordpress-core'] ) ? rtrim( $options['wordpress-core'], '/\\' ) : getenv( 'WP_CORE_DIR' );
if ( ! $core || ! is_file( $core . '/wp-includes/html-api/class-wp-html-tag-processor.php' ) ) {
	fwrite( STDERR, "Provide --wordpress-core=/path/to/wordpress (6.2+), or WP_CORE_DIR.\n" );
	exit( 1 );
}
define( 'ABSPATH', $core . '/' );
define( 'WPINC', 'wp-includes' );
require_once $core . '/wp-includes/plugin.php';
require_once $core . '/wp-includes/formatting.php';
require_once $core . '/wp-includes/kses.php';
require_once $core . '/wp-includes/class-wp-post.php';
spl_autoload_register( function ( $class ) use ( $core ) {
	$file = $core . '/wp-includes/html-api/class-' . strtolower( str_replace( '_', '-', $class ) ) . '.php';
	if ( 0 === strpos( $class, 'WP_HTML_' ) && is_file( $file ) ) {
		require_once $file;
	}
} );

function get_option( $key, $default = false ) {
	return array( 'blog_public' => $GLOBALS['state']['blog_public'], 'blog_charset' => 'UTF-8' )[ $key ] ?? $default;
}
function wp_load_alloptions() { return array( 'blog_charset' => 'UTF-8' ); }
function wp_allowed_protocols() { return array( 'http', 'https' ); }
function _doing_it_wrong( $function, $message, $version ) { throw new RuntimeException( $function . ': ' . $message ); }
function __( $text ) { return $text; }
function is_admin() { return $GLOBALS['state']['admin']; }
function is_feed() { return $GLOBALS['state']['feed']; }
function is_embed() { return $GLOBALS['state']['embed']; }
function is_preview() { return $GLOBALS['state']['preview']; }
function is_paged() { return $GLOBALS['state']['paged']; }
function is_singular( $type ) { return $GLOBALS['state']['singular'] && 'page' === $type; }
function get_query_var( $key, $default = '' ) { return $GLOBALS['state']['vars'][ $key ] ?? $default; }
function get_queried_object_id() { return $GLOBALS['state']['id']; }
function get_post( $id ) { return $id instanceof WP_Post ? $id : ( $GLOBALS['posts'][ $id ] ?? null ); }
function get_post_status( $post ) { return get_post( $post )->post_status; }
function get_permalink( $post ) { return $GLOBALS['urls'][ get_post( $post )->ID ] ?? false; }
function is_post_publicly_viewable( $post ) {
	return 'publish' === $post->post_status && ! in_array( $post->ID, $GLOBALS['not_public'], true );
}

$root = dirname( __DIR__, 2 );
$language_map = json_decode( file_get_contents( $root . '/docs/stage-4-language-map.json' ), true, 512, JSON_THROW_ON_ERROR );
$rows = $language_map['pages'];
$assertions = 0;

function reset_fixture() {
	$GLOBALS['state'] = array( 'id' => 7, 'admin' => false, 'feed' => false, 'embed' => false,
		'preview' => false, 'paged' => false, 'singular' => true, 'blog_public' => '1', 'vars' => array() );
	$GLOBALS['posts'] = array();
	$GLOBALS['urls'] = array();
	$GLOBALS['not_public'] = array();
	foreach ( $GLOBALS['rows'] as $row ) {
		$GLOBALS['posts'][ $row['id'] ] = new WP_Post( (object) array(
			'ID' => $row['id'], 'post_type' => 'page', 'post_status' => 'publish', 'post_password' => '',
		) );
		$GLOBALS['urls'][ $row['id'] ] = $row['canonical'];
	}
}

function same( $expected, $actual, $label ) {
	++$GLOBALS['assertions'];
	if ( $expected !== $actual ) {
		throw new RuntimeException( $label . "\nExpected: " . var_export( $expected, true ) . "\nActual: " . var_export( $actual, true ) );
	}
}

function attribute( $attributes, $name ) {
	$processor = new WP_HTML_Tag_Processor( '<html ' . $attributes . '>' );
	$processor->next_tag();
	return $processor->get_attribute( $name );
}

function output_tags() {
	ob_start();
	do_action( 'wp_head' );
	return ob_get_clean();
}

function alternates() {
	$html = output_tags();
	$processor = new WP_HTML_Tag_Processor( $html );
	$links = array();
	while ( $processor->next_tag() ) {
		same( 'LINK', $processor->get_tag(), 'Only link elements may be emitted' );
		same( 'alternate', $processor->get_attribute( 'rel' ), 'Only alternate links may be emitted' );
		$language = $processor->get_attribute( 'hreflang' );
		same( false, isset( $links[ $language ] ), 'No duplicate alternates' );
		$links[ $language ] = $processor->get_attribute( 'href' );
	}
	return $links;
}

try {
	reset_fixture();
	$hooks_before = array_keys( $GLOBALS['wp_filter'] );
	require $root . '/wordpress/plugins/lpv-language-seo/lpv-language-seo.php';
	$new_hooks = array_values( array_diff( array_keys( $GLOBALS['wp_filter'] ), $hooks_before ) );
	sort( $new_hooks );
	same( array( 'language_attributes', 'wp_head' ), $new_hooks, 'Only two WP hooks registered' );

	$expected_groups = array();
	foreach ( $rows as $row ) {
		$expected_groups[ $row['family'] ][ $row['lang'] ] = array( 'id' => $row['id'], 'url' => $row['canonical'] );
	}
	$actual_groups = lpv_language_seo_groups();
	ksort( $actual_groups );
	ksort( $expected_groups );
	same( $expected_groups, $actual_groups, 'Exact groups, IDs and URLs from stage 4' );

	foreach ( $rows as $row ) {
		$GLOBALS['state']['id'] = $row['id'];
		$attrs = apply_filters( 'language_attributes', 'dir="ltr" lang="pt-BR" prefix="og: https://ogp.me/ns#"', 'html' );
		same( $row['lang'], attribute( $attrs, 'lang' ), 'Language ' . $row['id'] );
		same( 'ltr', attribute( $attrs, 'dir' ), 'Direction preserved' );
		same( 'og: https://ogp.me/ns#', attribute( $attrs, 'prefix' ), 'OG prefix preserved' );
		same( $row['alternates'], alternates(), 'Published alternates ' . $row['id'] );
	}

	// Every publication subset, on every member, including self and missing PT.
	foreach ( $actual_groups as $group ) {
		$members = array_values( $group );
		$languages = array_keys( $group );
		for ( $mask = 0; $mask < ( 1 << count( $members ) ); ++$mask ) {
			reset_fixture();
			$expected = array();
			foreach ( $members as $index => $member ) {
				$published = (bool) ( $mask & ( 1 << $index ) );
				$GLOBALS['posts'][ $member['id'] ]->post_status = $published ? 'publish' : 'draft';
				if ( $published ) { $expected[ $languages[ $index ] ] = $member['url']; }
			}
			if ( isset( $expected['pt-BR'] ) ) { $expected['x-default'] = $expected['pt-BR']; }
			foreach ( $members as $member ) {
				$GLOBALS['state']['id'] = $member['id'];
				$visible = 'publish' === $GLOBALS['posts'][ $member['id'] ]->post_status;
				same( $visible ? $expected : array(), alternates(), 'Publication subset ' . $mask . ', page ' . $member['id'] );
			}
		}
	}

	foreach ( array( 'draft', 'pending', 'future', 'private', 'trash', 'auto-draft' ) as $status ) {
		reset_fixture();
		$GLOBALS['posts'][21]->post_status = $status;
		same( false, isset( alternates()['en'] ), 'Exclude status ' . $status );
	}
	foreach ( array( 'missing', 'password', 'post_type', 'not_public', 'changed_url', 'staging', 'no_permalink' ) as $case ) {
		reset_fixture();
		if ( 'missing' === $case ) { unset( $GLOBALS['posts'][21] ); }
		if ( 'password' === $case ) { $GLOBALS['posts'][21]->post_password = '0'; }
		if ( 'post_type' === $case ) { $GLOBALS['posts'][21]->post_type = 'post'; }
		if ( 'not_public' === $case ) { $GLOBALS['not_public'][] = 21; }
		if ( 'changed_url' === $case ) { $GLOBALS['urls'][21] = 'https://lpvturismo.com/en/new/'; }
		if ( 'staging' === $case ) { $GLOBALS['urls'][21] = 'https://staging.example/en/'; }
		if ( 'no_permalink' === $case ) { $GLOBALS['urls'][21] = false; }
		same( false, isset( alternates()['en'] ), 'Exclude unavailable equivalent: ' . $case );
		$GLOBALS['state']['id'] = 21;
		same( '', output_tags(), 'Unavailable current page: ' . $case );
	}

	foreach ( array( 'admin', 'feed', 'embed', 'preview', 'paged' ) as $flag ) {
		reset_fixture();
		$GLOBALS['state'][ $flag ] = true;
		same( '', output_tags(), 'No head output in ' . $flag );
		if ( in_array( $flag, array( 'admin', 'feed', 'embed' ), true ) ) {
			same( 'lang="de"', apply_filters( 'language_attributes', 'lang="de"', 'html' ), 'Unchanged attributes in ' . $flag );
		}
	}
	reset_fixture();
	$GLOBALS['state']['singular'] = false;
	same( '', output_tags(), 'Archives/search/404 do not emit' );
	same( 'lang="de"', apply_filters( 'language_attributes', 'lang="de"' ), 'Non-page lang untouched' );
	reset_fixture();
	$GLOBALS['state']['vars']['page'] = 2;
	same( '', output_tags(), 'Multipage content excluded' );
	reset_fixture();
	$GLOBALS['state']['blog_public'] = '0';
	same( '', output_tags(), 'Globally noindex excluded' );
	reset_fixture();
	$GLOBALS['state']['id'] = 999;
	same( '', output_tags(), 'Unmapped page excluded' );
	same( 'lang="de"', apply_filters( 'language_attributes', 'lang="de"' ), 'Unmapped lang untouched' );
	reset_fixture();
	$GLOBALS['state']['id'] = 20;
	$GLOBALS['state']['vars'] = array( 'solicitacao' => 'mipim', 'lang' => 'xx', 'id' => 7 );
	same( 'es', attribute( apply_filters( 'language_attributes', 'lang="pt-BR"' ), 'lang' ), 'Query data cannot override approved language' );

	foreach ( array( '', "lang='pt-BR'", 'LANG="pt-BR"', 'xml:lang="pt-BR"', 'dir="rtl" data-note="a &amp; b lang=&quot;xx&quot;"' ) as $input ) {
		$output = apply_filters( 'language_attributes', $input, 'xhtml' );
		same( 'es', attribute( $output, 'lang' ), 'Attribute parsing' );
		same( 'es', attribute( $output, 'xml:lang' ), 'XHTML consistency' );
		same( attribute( $input, 'data-note' ), attribute( $output, 'data-note' ), 'Escaped custom attribute preserved' );
	}
	$attrs = apply_filters( 'language_attributes', 'lang="pt-BR" xml:lang="pt-BR" dir="rtl"', 'html' );
	same( 'es', attribute( $attrs, 'xml:lang' ), 'Existing xml:lang corrected in HTML' );
	same( 'rtl', attribute( $attrs, 'dir' ), 'Existing direction preserved' );
	$attrs = apply_filters( 'language_attributes', 'lang="pt-BR"', 'html' );
	same( null, attribute( $attrs, 'xml:lang' ), 'No unnecessary XML attribute in HTML' );
	$escapes = array( 'attr' => 0, 'url' => 0 );
	add_filter( 'attribute_escape', function ( $value ) use ( &$escapes ) { ++$escapes['attr']; return $value; } );
	add_filter( 'clean_url', function ( $value ) use ( &$escapes ) { ++$escapes['url']; return $value; } );
	output_tags();
	same( 4, $escapes['attr'], 'Native attribute escaping used for all hreflangs' );
	same( 4, $escapes['url'], 'Native URL escaping used for all URLs' );
	fwrite( STDOUT, "PASS: {$assertions} assertions; all 22 pages; all publication subsets; no network/database.\n" );
} catch ( Throwable $error ) {
	fwrite( STDERR, $error . "\n" );
	exit( 1 );
}
