<?php
/** Read-only production inventory for the controlled LPV deployment. */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

$lpv_pages = array(
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

$pages = array();
foreach ( $lpv_pages as $id => $expected_path ) {
	$post = get_post( $id );
	if ( ! ( $post instanceof WP_Post ) ) {
		$pages[ (string) $id ] = array( 'exists' => false, 'expected_path' => $expected_path );
		continue;
	}
	$aioseo = array();
	if ( class_exists( '\\AIOSEO\\Plugin\\Common\\Models\\Post' ) ) {
		$model = \AIOSEO\Plugin\Common\Models\Post::getPost( $id );
		if ( $model && method_exists( $model, 'exists' ) && $model->exists() ) {
			$data = json_decode( wp_json_encode( $model ), true );
			$aioseo = array(
				'title'       => isset( $data['title'] ) ? $data['title'] : '',
				'description' => isset( $data['description'] ) ? $data['description'] : '',
			);
		}
	}
	$permalink = get_permalink( $post );
	$pages[ (string) $id ] = array(
		'exists'          => true,
		'post_type'       => $post->post_type,
		'post_name'       => $post->post_name,
		'post_status'     => $post->post_status,
		'post_password'   => '' === $post->post_password ? '' : '[present]',
		'post_modified_gmt' => $post->post_modified_gmt,
		'permalink'       => $permalink,
		'path'            => wp_parse_url( $permalink, PHP_URL_PATH ),
		'expected_path'   => $expected_path,
		'content'         => $post->post_content,
		'content_sha256'  => hash( 'sha256', $post->post_content ),
		'postmeta'        => get_post_meta( $id ),
		'aioseo'          => $aioseo,
	);
}

$plugins = array();
if ( ! function_exists( 'get_plugins' ) ) {
	require_once ABSPATH . 'wp-admin/includes/plugin.php';
}
foreach ( get_plugins() as $file => $data ) {
	$plugins[ $file ] = array(
		'name'    => $data['Name'],
		'version' => $data['Version'],
		'status'  => is_plugin_active( $file ) ? 'active' : 'inactive',
	);
}

$templates = array();
foreach ( get_posts( array( 'post_type' => 'wp_template', 'post_status' => 'any', 'numberposts' => -1 ) ) as $template ) {
	$templates[] = array(
		'id' => $template->ID, 'slug' => $template->post_name,
		'status' => $template->post_status, 'content' => $template->post_content,
	);
}

$stylesheet = get_stylesheet();
$aioseo_option_hashes = array();
foreach ( wp_load_alloptions() as $name => $value ) {
	if ( 0 === strpos( $name, 'aioseo' ) ) {
		$aioseo_option_hashes[ $name ] = hash( 'sha256', maybe_serialize( $value ) );
	}
}

$theme = wp_get_theme();
$admin = get_user_by( 'id', 1 );
rest_get_server();
$result = array(
	'home' => home_url(), 'siteurl' => site_url(),
	'wordpress_version' => get_bloginfo( 'version' ), 'php_version' => PHP_VERSION,
	'template' => get_template(), 'stylesheet' => $stylesheet,
	'theme_version' => $theme->get( 'Version' ),
	'admin_user_login' => $admin instanceof WP_User ? $admin->user_login : '',
	'options' => array(
		'show_on_front' => get_option( 'show_on_front' ),
		'page_on_front' => (int) get_option( 'page_on_front' ),
		'blog_public' => (string) get_option( 'blog_public' ),
	),
	'custom_css' => wp_get_custom_css( $stylesheet ),
	'custom_css_sha256' => hash( 'sha256', wp_get_custom_css( $stylesheet ) ),
	'pages' => $pages, 'plugins' => $plugins, 'wp_templates' => $templates,
	'aioseo_option_hashes' => $aioseo_option_hashes,
	'rest_aioseo_field' => isset( $GLOBALS['wp_rest_additional_fields']['page']['aioseo_meta_data'] ),
);

echo wp_json_encode( $result, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE );
