# LPV ChatGPT Conversions

- Version: 0.1.0
- Date: 2026-11-17
- Owner: Pablo Vallasciani / LPV Turismo
- Status: implementation candidate; NOT installed, activated, or verified against a live ad account.

This independent plugin preserves the published page contents, product choices, language, images, menus and native FormSubmit actions. It progressively enhances the three observed enquiry forms after its own same-origin initialization succeeds.

## Scope and event definition

A lead is counted only when the server-side FormSubmit AJAX request returns HTTP 2xx with a strict boolean/string success value and no activation prompt. HTTP 200 alone, an attempted submit, a button click and a URL containing enviado=1/sent=1 are not conversion evidence.

Acceptance by FormSubmit establishes submission-service acceptance; it does not prove inbox delivery, booking, availability, payment or a completed tour. No order_created, customer audiences or revenue values are generated in this release.

Forms observed in the connected WordPress site on 2026-11-17:

| Page | ID | Form |
| --- | --- | --- |
| /quero-montar-meu-roteiro/ | 19 | lpv-roteiro-form |
| /es/quiero-armar-mi-itinerario/ | 203 | lpv-roteiro-form-es |
| /en/plan-my-itinerary/ | 218 | lpv-itinerary-form |

Published WordPress content is newer than main in the repository. Do not replace current pages with repository HTML to deploy this integration.

## Configuration

The plugin is inert by default. Configure secrets privately on the host; never put a real API key in this repository, page HTML, browser script, screenshots, issues or chat.

Example placeholders for wp-config.php, before its stop-editing line:

~~~php
define('LPV_ADS_ENABLED', false);
define('LPV_ADS_PRIVACY_READY', false);
define('LPV_ADS_PIXEL_ID', getenv('LPV_ADS_PIXEL_ID') ?: '');
define('LPV_ADS_CAPI_KEY', getenv('LPV_ADS_CAPI_KEY') ?: '');
define('LPV_ADS_VALIDATE_ONLY', true);
~~~

Host environment variables are an option only if supported by the actual hosting setup. Otherwise enter real values privately in protected server-side configuration. The Conversions API key is separate from a model/API-platform key. No LLM credits are needed by this plugin.

The Pixel ID identifies the source even though this implementation does not install the browser Pixel. Reuse an existing suitable source in the same advertiser account instead of creating duplicates. The source's internal id used in event settings is different from pixel_id.

## What happens when enabled

1. Load the LPV script and optional measurement choice in PT/ES/EN.
2. Store only the measurement choice and, after acceptance, an available oppref in sessionStorage. No reference is persisted before acceptance. Declining does not stop enquiry submission.
3. Fetch a fresh no-store nonce rather than embedding an expiring token in cached WordPress HTML.
4. On a supported form, send a same-origin JSON request to /wp-json/lpv-ads/v1/lead.
5. Server validates origin, nonce, fields, source path, body size and a basic rate limit.
6. Forward the enquiry to the fixed existing FormSubmit recipient. No new recipient, CC or webhook can be injected.
7. After a confirmed FormSubmit response, return success to the visitor independently of CAPI delivery.
8. Only with measurement acceptance, enqueue a minimal lead_created event for CAPI. Do not forward the form fields, names, email, phone, hashes, health/mobility notes, visitor IP/user-agent, or query strings.
9. Retry transient CAPI transport/408/429/5xx failures with the same event ID. Do not retry invalid credentials or other permanent 4xx errors.

The action attribute remains native FormSubmit. If the plugin is disabled or fails initialization, that original path continues to operate without CAPI measurement. Once a relay submission starts, an ambiguous network failure is NOT retried via the native form: that could email the same enquiry twice.

The baseline plugin list includes Site Kit; this plugin does not alter Google tags or their existing settings. Its capture-phase handler prevents the older submit-attempt listener from treating the enhanced path as a confirmed submission; existing Google event behavior outside that path is unchanged.

## Validation and activation

1. Back up the site and plugins. Install this folder as wp-content/plugins/lpv-chatgpt-conversions using the existing controlled deployment procedure; keep ENABLED=false.
2. Create/reuse a web source in Ads Manager -> Conversions and privately provision its CAPI key.
3. Review the draft privacy addendum in docs/chatgpt-ads-privacy-addendum-v0.1.md and update the approved public policy with version/date before enabling measurement. PRIVACY_READY is an explicit deployment gate, not a claim of legal review.
4. Verify the FormSubmit address/activation in the real account. A live provider relay has NOT been tested in this change.
5. Set ENABLED=true and PRIVACY_READY=true only in an isolated QA environment with provider HTTP mocked, while keeping VALIDATE_ONLY=true. If production is the only environment, do not perform real test-email submissions without a separately agreed test recipient/workflow.
6. Run offline tests below. With the real source/key available, send a synthetic, non-customer event directly with validate_only=true. A validation-only event does not appear in recent-event monitoring.
7. Check decline/accept/withdrawal behavior, all three languages, disabled product fields, errors, session expiration and original native fallback. Confirm there is no API key or personal form data in browser telemetry.
8. After review and an agreed live-test procedure, change VALIDATE_ONLY=false for future real submissions. Previously queued validation events are discarded on a mode change.
9. Define lead_created as a conversion setting on that source and attach the setting to the intended campaign. Do not change objective, budget or activate an ad as part of instrumentation.
10. Verify one agreed conversion in source event diagnostics, separately from ad attribution. Reception does not guarantee it is attributable to an ad. Verify campaign/date window independently.

Do not call the integration live or end-to-end verified until steps 2-10 have actually completed.

## Offline tests

All HTTP calls are mocked. Tests require PHP >=7.4 and Node >=18.

~~~sh
php -l lpv-chatgpt-conversions.php
php -l includes/core.php
php tests/core-test.php
php tests/adapter-test.php
node --test tests/browser-test.cjs
~~~

A GitHub Actions workflow runs these checks on the review branch/PR. No credentials, customer data, live CAPI calls or FormSubmit emails are used.

## Operations and limits

- WordPress Cron must be operational. Scheduled processing is traffic-dependent; use the host's existing cron mechanism if WP-Cron is disabled.
- Only the fixed existing FormSubmit recipient and three observed enquiry pages are supported.
- Forms with file inputs or enabled captcha are left on the native path. Native-path submissions are not measured by this release.
- A provider timeout is ambiguous and can mean the email was accepted despite no response. The request stays unconfirmed, is not resent, and creates no conversion.
- CAPI matching without email/phone and without an available oppref may be incomplete. This is a deliberate initial data-minimization choice.
- Withdrawing measurement permission stops future enqueueing; it does not recall an event already sent.
- Receipt records contain only a keyed digest, state and expiry. Queue records contain minimal event data including the click reference while pending. They expire after 72 hours and are removed at a later daily cleanup; verify cron.
- Successful/failed CAPI delivery drops the queued reference and retains only a short-lived result marker. No response bodies or secrets are logged.
- Basic IP rate limiting uses a keyed transient and is not a full anti-bot service. Keep existing host protections. Do not enable on production until abuse handling and host request limits are reviewed.
- Worker process crashes and failed WP-Cron scheduling require operational review of pending queue items. This first version has bounded retries, not a durable external job service.
- No automated sale confirmation from WhatsApp, Pix or a bank is implemented.

## Rollback

Set LPV_ADS_ENABLED=false and purge LiteSpeed/page caches, then deactivate the plugin through the established deployment procedure. Existing form action attributes and published content do not need to be restored. Inspect any queued items before re-enabling; do not replay test events as live conversions.

## Primary references

- https://developers.openai.com/ads/conversions-api
- https://developers.openai.com/ads/conversion-tracking
- https://developers.openai.com/ads/supported-events
- https://formsubmit.co/documentation
- https://developer.wordpress.org/reference/functions/wp_remote_post/
