<?php
/** Verify installed LPV runtime components without rendering or sending forms. */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}
if ( ! function_exists( 'is_plugin_active' ) ) {
	require_once ABSPATH . 'wp-admin/includes/plugin.php';
}
$result = array(
	'template_plugin_active' => is_plugin_active( 'lpv-page-templates/lpv-page-templates.php' ),
	'language_plugin_active' => is_plugin_active( 'lpv-language-seo/lpv-language-seo.php' ),
	'template_registered' => false,
	'language_hooks_registered' => false,
);
if ( function_exists( 'get_block_templates' ) ) {
	foreach ( get_block_templates( array(), 'wp_template' ) as $template ) {
		if ( isset( $template->slug ) && 'lpv-content-only' === $template->slug ) {
			$result['template_registered'] = true;
		}
	}
}
$result['language_hooks_registered'] = has_filter( 'language_attributes', 'lpv_language_seo_language_attributes' )
	&& has_action( 'wp_head', 'lpv_language_seo_hreflang' );
$result['status'] = ! in_array( false, $result, true ) ? 'APROVADO' : 'BLOQUEADOR';
echo 'LPV_RESULT:' . wp_json_encode( $result );
