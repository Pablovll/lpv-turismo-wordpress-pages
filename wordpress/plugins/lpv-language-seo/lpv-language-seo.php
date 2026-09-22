<?php
/**
 * Plugin Name: LPV Language SEO
 * Description: Page-specific language and published hreflang equivalents for LPV Turismo.
 * Version: 1.0.0
 * Requires at least: 6.2
 * Requires PHP: 7.4
 * Author: LPV Turismo
 * License: GPL-2.0-or-later
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/** Approved stage 4 groups. Navigation fallbacks are deliberately absent. */
function lpv_language_seo_groups() {
	return array(
		'home' => array(
			'pt-BR' => array( 'id' => 7, 'url' => 'https://lpvturismo.com/' ),
			'es' => array( 'id' => 20, 'url' => 'https://lpvturismo.com/es/' ),
			'en' => array( 'id' => 21, 'url' => 'https://lpvturismo.com/en/' ),
		),
		'tours' => array(
			'pt-BR' => array( 'id' => 17, 'url' => 'https://lpvturismo.com/passeios/' ),
			'es' => array( 'id' => 237, 'url' => 'https://lpvturismo.com/es/paseos/' ),
			'en' => array( 'id' => 239, 'url' => 'https://lpvturismo.com/en/tours/' ),
		),
		'services' => array(
			'pt-BR' => array( 'id' => 18, 'url' => 'https://lpvturismo.com/outros-servicos/' ),
			'es' => array( 'id' => 205, 'url' => 'https://lpvturismo.com/es/servicios/' ),
			'en' => array( 'id' => 217, 'url' => 'https://lpvturismo.com/en/services/' ),
		),
		'itinerary_form' => array(
			'pt-BR' => array( 'id' => 19, 'url' => 'https://lpvturismo.com/quero-montar-meu-roteiro/' ),
			'es' => array( 'id' => 203, 'url' => 'https://lpvturismo.com/es/quiero-armar-mi-itinerario/' ),
			'en' => array( 'id' => 218, 'url' => 'https://lpvturismo.com/en/plan-my-itinerary/' ),
		),
		'mosaics' => array(
			'pt-BR' => array( 'id' => 84, 'url' => 'https://lpvturismo.com/passeios/mosaicos-do-rio/' ),
			'es' => array( 'id' => 160, 'url' => 'https://lpvturismo.com/es/mosaicos-del-rio/' ),
			'en' => array( 'id' => 219, 'url' => 'https://lpvturismo.com/en/mosaics-of-rio/' ),
		),
		'tijuca_forest' => array(
			'pt-BR' => array( 'id' => 85, 'url' => 'https://lpvturismo.com/passeios/imersao-floresta-da-tijuca/' ),
			'es' => array( 'id' => 194, 'url' => 'https://lpvturismo.com/es/inmersion-floresta-da-tijuca/' ),
			'en' => array( 'id' => 220, 'url' => 'https://lpvturismo.com/en/tijuca-forest-immersion/' ),
		),
		'rio_essential' => array(
			'pt-BR' => array( 'id' => 86, 'url' => 'https://lpvturismo.com/passeios/rio-essencial/' ),
			'es' => array( 'id' => 195, 'url' => 'https://lpvturismo.com/es/rio-esencial/' ),
			'en' => array( 'id' => 221, 'url' => 'https://lpvturismo.com/en/rio-essential/' ),
		),
		'lp_experiences' => array(
			'pt-BR' => array( 'id' => 255, 'url' => 'https://lpvturismo.com/lp-experiences/' ),
		),
	);
}

function lpv_language_seo_current_page() {
	if ( is_admin() || is_feed() || is_embed() || ! is_singular( 'page' ) ) {
		return null;
	}
	$id = (int) get_queried_object_id();
	foreach ( lpv_language_seo_groups() as $group ) {
		foreach ( $group as $language => $page ) {
			if ( $id === $page['id'] ) {
				return array( 'language' => $language, 'page' => $page, 'group' => $group );
			}
		}
	}
	return null;
}

function lpv_language_seo_language_attributes( $output, $doctype = 'html' ) {
	$current = lpv_language_seo_current_page();
	if ( null === $current ) {
		return $output;
	}
	// The native HTML API escapes changed values and preserves dir, prefix and other attributes.
	$processor = new WP_HTML_Tag_Processor( '<html ' . $output . '>' );
	if ( ! $processor->next_tag( 'HTML' ) ) {
		return $output;
	}
	$processor->set_attribute( 'lang', $current['language'] );
	if ( 'xhtml' === $doctype || null !== $processor->get_attribute( 'xml:lang' ) ) {
		$processor->set_attribute( 'xml:lang', $current['language'] );
	}
	return substr( $processor->get_updated_html(), strlen( '<html ' ), -1 );
}

function lpv_language_seo_is_public_equivalent( $page ) {
	$post = get_post( $page['id'] );
	if ( ! ( $post instanceof WP_Post ) || 'page' !== $post->post_type
		|| 'publish' !== get_post_status( $post ) || '' !== (string) $post->post_password
		|| ! is_post_publicly_viewable( $post ) ) {
		return false;
	}
	// Do not advertise stale routes or a clone whose IDs refer to different URLs.
	return untrailingslashit( (string) get_permalink( $post ) ) === untrailingslashit( $page['url'] );
}

function lpv_language_seo_hreflang() {
	if ( is_preview() || is_paged() || (int) get_query_var( 'page', 1 ) > 1
		|| '0' === (string) get_option( 'blog_public' ) ) {
		return;
	}
	$current = lpv_language_seo_current_page();
	if ( null === $current || ! lpv_language_seo_is_public_equivalent( $current['page'] ) ) {
		return;
	}
	$alternates = array();
	foreach ( $current['group'] as $language => $page ) {
		if ( lpv_language_seo_is_public_equivalent( $page ) ) {
			$alternates[ $language ] = $page['url'];
		}
	}
	if ( isset( $alternates['pt-BR'] ) ) {
		$alternates['x-default'] = $alternates['pt-BR'];
	}
	foreach ( $alternates as $language => $url ) {
		printf( '<link rel="alternate" hreflang="%s" href="%s" />' . "\n", esc_attr( $language ), esc_url( $url ) );
	}
}

add_filter( 'language_attributes', 'lpv_language_seo_language_attributes', 20, 2 );
add_action( 'wp_head', 'lpv_language_seo_hreflang', 20 );
