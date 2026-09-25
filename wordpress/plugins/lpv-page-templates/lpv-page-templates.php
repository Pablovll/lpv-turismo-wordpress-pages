<?php
/**
 * Plugin Name: LPV Page Templates
 * Description: Scoped content-only block template for the approved LPV pages.
 * Version: 1.0.1
 * Requires at least: 6.7
 * Requires PHP: 7.4
 * License: GPL-2.0-or-later
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/** Approved IDs and paths, checked against the stage 4 map by local tests. */
function lpv_page_templates_paths() {
	return array(
		7   => '/',
		17  => '/passeios/',
		18  => '/outros-servicos/',
		19  => '/quero-montar-meu-roteiro/',
		84  => '/passeios/mosaicos-do-rio/',
		85  => '/passeios/imersao-floresta-da-tijuca/',
		86  => '/passeios/rio-essencial/',
		255 => '/lp-experiences/',
		20  => '/es/',
		237 => '/es/paseos/',
		205 => '/es/servicios/',
		203 => '/es/quiero-armar-mi-itinerario/',
		160 => '/es/mosaicos-del-rio/',
		194 => '/es/inmersion-floresta-da-tijuca/',
		195 => '/es/rio-esencial/',
		21  => '/en/',
		239 => '/en/tours/',
		217 => '/en/services/',
		218 => '/en/plan-my-itinerary/',
		219 => '/en/mosaics-of-rio/',
		220 => '/en/tijuca-forest-immersion/',
		221 => '/en/rio-essential/',
	);
}

/** Normalize only the request-path details WordPress treats as equivalent. */
function lpv_page_templates_request_path() {
	if ( empty( $_SERVER['REQUEST_URI'] ) ) {
		return '';
	}

	$path = wp_parse_url( wp_unslash( $_SERVER['REQUEST_URI'] ), PHP_URL_PATH );
	if ( ! is_string( $path ) || '' === $path || preg_match( '/%(?![0-9A-Fa-f]{2})/', $path ) ) {
		return '';
	}

	// Decode only unreserved characters except dot; encoded separators remain distinct.
	$path = preg_replace_callback(
		'/%([0-9A-Fa-f]{2})/',
		static function ( $match ) {
			$character = chr( hexdec( $match[1] ) );
			return preg_match( '/[A-Za-z0-9_~-]/', $character )
				? $character
				: strtoupper( $match[0] );
		},
		$path
	);
	if ( ! is_string( $path ) || '' === $path ) {
		return '';
	}

	return '/' === $path ? '/' : trailingslashit( $path );
}

/** Contexts that must retain their original LiteSpeed and template behavior. */
function lpv_page_templates_is_excluded_context() {
	return is_admin()
		|| wp_doing_ajax()
		|| wp_doing_cron()
		|| ( defined( 'REST_REQUEST' ) && REST_REQUEST )
		|| ( defined( 'WP_CLI' ) && WP_CLI )
		|| is_feed()
		|| is_embed()
		|| is_preview()
		|| is_search()
		|| is_404()
		|| ( isset( $GLOBALS['pagenow'] ) && 'wp-login.php' === $GLOBALS['pagenow'] );
}

/** True only for the approved page identity in the expected theme and request context. */
function lpv_page_templates_is_managed_request() {
	if ( lpv_page_templates_is_excluded_context() || ! is_singular( 'page' )
		|| ! wp_is_block_theme() || 'twentytwentyfive' !== get_template() ) {
		return false;
	}

	$id    = get_queried_object_id();
	$paths = lpv_page_templates_paths();
	if ( ! isset( $paths[ $id ] ) ) {
		return false;
	}

	// A root-domain staging clone may differ in host, but not in page IDs or paths.
	$permalink = get_permalink( $id );
	if ( ! $permalink || wp_parse_url( $permalink, PHP_URL_PATH ) !== $paths[ $id ]
		|| lpv_page_templates_request_path() !== $paths[ $id ] ) {
		return false;
	}
	if ( 7 === $id || is_front_page() ) {
		if ( 7 !== $id || 'page' !== get_option( 'show_on_front' )
			|| 7 !== (int) get_option( 'page_on_front' ) || ! is_front_page() ) {
			return false;
		}
	}
	return true;
}

/** Bypass only LiteSpeed Page Optimization; page cache and the plugin remain active. */
function lpv_page_templates_litespeed_can_optm( $can_optimize ) {
	return lpv_page_templates_is_managed_request() ? false : $can_optimize;
}

function lpv_page_templates_hierarchy( $templates ) {
	if ( ! lpv_page_templates_is_managed_request() ) {
		return $templates;
	}

	array_unshift( $templates, 'lpv-content-only.php' );
	return array_values( array_unique( $templates ) );
}

/** Approved fragments are complete HTML; wpautop corrupts their inline JavaScript and CSS. */
function lpv_page_templates_disable_wpautop() {
	if ( lpv_page_templates_is_managed_request() ) {
		remove_filter( 'the_content', 'wpautop' );
	}
}

function lpv_page_templates_register() {
	if ( ! function_exists( 'register_block_template' ) || ! wp_is_block_theme()
		|| 'twentytwentyfive' !== get_template() ) {
		return;
	}

	$file = __DIR__ . '/templates/lpv-content-only.html';
	if ( ! is_readable( $file ) ) {
		return;
	}
	$content = file_get_contents( $file );
	if ( false === $content || '' === trim( $content ) ) {
		return;
	}
	$template = register_block_template(
		'lpv-page-templates//lpv-content-only',
		array(
			'title'       => 'LPV - Content only',
			'description' => 'Versioned LPV layout. Maintain in the repository, not the Site Editor.',
			'content'     => $content,
			'post_types'  => array( 'page' ),
		)
	);
	if ( is_wp_error( $template ) ) {
		return;
	}

	// Let WordPress resolve and render its native block canvas, including document hooks.
	add_filter( 'page_template_hierarchy', 'lpv_page_templates_hierarchy', 20 );
	add_filter( 'frontpage_template_hierarchy', 'lpv_page_templates_hierarchy', 20 );
}

add_action( 'init', 'lpv_page_templates_register' );
add_action( 'wp', 'lpv_page_templates_disable_wpautop', 20 );
add_filter( 'litespeed_can_optm', 'lpv_page_templates_litespeed_can_optm' );
