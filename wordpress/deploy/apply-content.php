<?php
/** Apply or restore approved page content through wp_update_post(). */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}
if ( empty( $args[0] ) || ! is_readable( $args[0] ) ) {
	WP_CLI::error( 'Missing deployment payload.' );
}
$payload = json_decode( file_get_contents( $args[0] ), true );
if ( ! is_array( $payload ) || empty( $payload['pages'] ) ) {
	WP_CLI::error( 'Invalid deployment payload.' );
}
$changed = array();
try {
	foreach ( $payload['pages'] as $item ) {
		$id = (int) $item['id'];
		$post = get_post( $id );
		if ( ! ( $post instanceof WP_Post ) || 'page' !== $post->post_type ) {
			throw new RuntimeException( 'Invalid page ID ' . $id );
		}
		$path = wp_parse_url( get_permalink( $post ), PHP_URL_PATH );
		if ( $path !== $item['path'] || ! hash_equals( $item['expected_sha256'], hash( 'sha256', $post->post_content ) ) ) {
			throw new RuntimeException( 'Concurrent change or path mismatch for page ' . $id );
		}
		if ( ! empty( $item['target_file'] ) ) {
			$base = realpath( dirname( $args[0] ) );
			$file = realpath( $base . '/' . ltrim( $item['target_file'], '/' ) );
			if ( false === $file || 0 !== strpos( $file, $base . DIRECTORY_SEPARATOR ) || ! is_readable( $file ) ) {
				throw new RuntimeException( 'Invalid target file for page ' . $id );
			}
			$target = file_get_contents( $file );
		} else {
			$target = base64_decode( $item['target_b64'], true );
		}
		if ( false === $target || ! hash_equals( $item['target_sha256'], hash( 'sha256', $target ) ) ) {
			throw new RuntimeException( 'Invalid target content for page ' . $id );
		}
		$result = wp_update_post( wp_slash( array( 'ID' => $id, 'post_content' => $target ) ), true );
		if ( is_wp_error( $result ) ) {
			throw new RuntimeException( 'WordPress rejected page ' . $id . ': ' . $result->get_error_code() );
		}
		clean_post_cache( $id );
		if ( ! hash_equals( $item['target_sha256'], hash( 'sha256', get_post( $id )->post_content ) ) ) {
			throw new RuntimeException( 'Saved content differs for page ' . $id );
		}
		$changed[] = $item;
	}
} catch ( Throwable $error ) {
	$rollback_failures = array();
	foreach ( array_reverse( $changed ) as $item ) {
		$original = base64_decode( $item['rollback_b64'], true );
		$result = wp_update_post( wp_slash( array( 'ID' => (int) $item['id'], 'post_content' => $original ) ), true );
		clean_post_cache( (int) $item['id'] );
		if ( is_wp_error( $result ) || ! hash_equals( $item['expected_sha256'], hash( 'sha256', get_post( (int) $item['id'] )->post_content ) ) ) {
			$rollback_failures[] = (int) $item['id'];
		}
	}
	WP_CLI::error( wp_json_encode( array( 'error' => $error->getMessage(), 'rollback_failures' => $rollback_failures ) ) );
}
echo 'LPV_RESULT:' . wp_json_encode( array( 'status' => 'APROVADO', 'updated_ids' => array_map( function ( $item ) { return (int) $item['id']; }, $changed ) ) );
