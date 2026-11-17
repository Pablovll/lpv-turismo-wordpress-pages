/* LPV ChatGPT Conversions 0.1.0. No third-party browser SDK or personal form data in CAPI. */
(function (root) {
  'use strict';
  const FORM_IDS = ['lpv-roteiro-form', 'lpv-roteiro-form-es', 'lpv-itinerary-form'];
  const CONSENT_KEY = 'lpv_ads_consent_v1';
  const REF_KEY = 'lpv_ads_oppref_v1';

  function accepted(response, body) {
    return response.ok && body && body.accepted === true;
  }
  function reference(value) {
    return typeof value === 'string' && value.length <= 4096 && !/[\u0000-\u001f\u007f]/.test(value) ? value : '';
  }
  function safeEndpoint(value, current) {
    const url = new URL(value, current);
    const here = new URL(current);
    const host = h => h.toLowerCase().replace(/^www\./, '');
    if (url.protocol !== 'https:' || here.protocol !== 'https:' ||
        host(url.hostname) !== host(here.hostname) || url.port !== here.port) {
      throw new Error('foreign_endpoint');
    }
    return here.origin + url.pathname + url.search;
  }
  const helpers = { accepted, reference, safeEndpoint, FORM_IDS };
  if (typeof module !== 'undefined' && module.exports) { module.exports = helpers; }
  if (!root || !root.document || !root.LPVAdsConfig) { return; }

  const doc = root.document;
  const config = root.LPVAdsConfig;
  const langPath = root.location.pathname;
  const lang = langPath.startsWith('/es/') ? 'es' : langPath.startsWith('/en/') ? 'en' : 'pt';
  const translations = {
    pt: {
      title: 'Privacidade dos anúncios',
      text: 'Podemos medir os resultados da publicidade? Ao aceitar, uma referência do anúncio e o registro do envio da solicitação podem ser compartilhados com a OpenAI. O conteúdo do formulário não é compartilhado.',
      accept: 'Aceitar medição', reject: 'Recusar', policy: 'Política de Privacidade',
      preferences: 'Preferências de publicidade', sending: 'Enviando sua solicitação...',
      sent: 'Solicitação recebida pelo serviço de envio. A LPV avaliará as informações; o envio não confirma reserva ou disponibilidade.',
      failed: 'Não foi possível confirmar o envio. Para evitar duplicidade, o sistema não reenviará automaticamente. Se precisar, fale com a LPV pelo WhatsApp.',
    },
    es: {
      title: 'Privacidad de los anuncios',
      text: '¿Podemos medir los resultados de la publicidad? Al aceptar, una referencia del anuncio y el registro del envío de la solicitud pueden compartirse con OpenAI. No se comparte el contenido del formulario.',
      accept: 'Aceptar medición', reject: 'Rechazar', policy: 'Política de Privacidad',
      preferences: 'Preferencias de publicidad', sending: 'Enviando tu solicitud...',
      sent: 'El servicio de envío recibió tu solicitud. LPV revisará la información; el envío no confirma reserva ni disponibilidad.',
      failed: 'No pudimos confirmar el envío. Para evitar duplicados, el sistema no lo reenviará automáticamente. Si necesitás ayuda, contactá a LPV por WhatsApp.',
    },
    en: {
      title: 'Ad privacy',
      text: 'May we measure advertising results? If you accept, an ad reference and a record that your enquiry was submitted may be shared with OpenAI. Your form contents are not shared.',
      accept: 'Accept measurement', reject: 'Decline', policy: 'Privacy Policy',
      preferences: 'Advertising preferences', sending: 'Sending your enquiry...',
      sent: 'The submission service received your enquiry. LPV will review it; submitting does not confirm a booking or availability.',
      failed: 'We could not confirm submission. To avoid duplicates, the system will not resend automatically. Please contact LPV on WhatsApp if you need help.',
    },
  };
  const copy = translations[lang];
  const memory = {};
  const read = key => {
    try { return root.sessionStorage.getItem(key); } catch (_) { return memory[key] || null; }
  };
  const write = (key, value) => {
    memory[key] = value;
    try {
      if (value === null) { root.sessionStorage.removeItem(key); }
      else { root.sessionStorage.setItem(key, value); }
    } catch (_) { /* Form delivery must work even when storage is blocked. */ }
  };
  const consented = () => read(CONSENT_KEY) === 'yes';
  const saveReference = () => {
    if (!consented()) { return; }
    const value = reference(new URL(root.location.href).searchParams.get('oppref'));
    if (value) { write(REF_KEY, value); }
  };
  const choose = allow => {
    write(CONSENT_KEY, allow ? 'yes' : 'no');
    if (allow) { saveReference(); } else { write(REF_KEY, null); }
  };

  function buildPrivacyChoice() {
    const style = doc.createElement('style');
    style.textContent = '.lpv-ads-choice{position:fixed;bottom:1rem;left:1rem;right:1rem;z-index:99990;max-width:40rem;background:#fff;color:#173f35;border:1px solid #173f35;border-radius:12px;padding:1rem;box-shadow:0 4px 24px #0003;font:inherit}.lpv-ads-choice[hidden]{display:none}.lpv-ads-choice p{margin:.5rem 0 1rem}.lpv-ads-choice button,.lpv-ads-preferences{font:inherit;cursor:pointer;padding:.5rem .8rem;margin:.2rem;border:1px solid #173f35;border-radius:6px;background:#fff;color:#173f35}.lpv-ads-preferences{display:block;margin:1rem auto;position:static}';
    doc.head.appendChild(style);
    const panel = doc.createElement('section');
    panel.className = 'lpv-ads-choice';
    panel.setAttribute('aria-label', copy.title);
    const title = doc.createElement('strong');
    title.textContent = copy.title;
    const text = doc.createElement('p');
    text.textContent = copy.text;
    panel.append(title, text);
    for (const allow of [true, false]) {
      const button = doc.createElement('button');
      button.type = 'button';
      button.textContent = allow ? copy.accept : copy.reject;
      button.addEventListener('click', () => { choose(allow); panel.hidden = true; preferences.focus(); });
      panel.appendChild(button);
    }
    if (config.privacyUrl) {
      const link = doc.createElement('a');
      link.href = safeEndpoint(config.privacyUrl, root.location.href);
      link.textContent = copy.policy;
      panel.appendChild(link);
    }
    const preferences = doc.createElement('button');
    preferences.type = 'button';
    preferences.className = 'lpv-ads-preferences';
    preferences.textContent = copy.preferences;
    preferences.addEventListener('click', () => { panel.hidden = false; panel.querySelector('button').focus(); });
    panel.hidden = read(CONSENT_KEY) !== null;
    doc.body.append(preferences, panel);
  }

  function fieldsOf(form) {
    const fields = {};
    for (const [key, value] of new FormData(form).entries()) {
      if (typeof value !== 'string') { throw new Error('files_not_supported'); }
      fields[key] = Object.hasOwn(fields, key) ? fields[key] + '\n' + value : value;
    }
    return fields;
  }
  function status(form, text, type) {
    const output = form.querySelector('#lpv-form-status');
    if (output) {
      output.textContent = text;
      output.className = 'lpv-form-status is-' + type;
      output.hidden = false;
    }
  }
  async function init() {
    saveReference();
    buildPrivacyChoice();
    const forms = FORM_IDS.map(id => doc.getElementById(id)).filter(Boolean);
    if (!forms.length || !root.crypto || typeof root.crypto.randomUUID !== 'function') { return; }
    let nonce;
    let leadUrl;
    try {
      leadUrl = safeEndpoint(config.leadUrl, root.location.href);
      const response = await fetch(safeEndpoint(config.sessionUrl, root.location.href), {
        credentials: 'same-origin', cache: 'no-store',
      });
      const data = await response.json();
      if (!response.ok || typeof data.nonce !== 'string' || !data.nonce) { return; }
      nonce = data.nonce;
    } catch (_) { return; } // Native FormSubmit remains in place when initialization fails.
    const attempts = new WeakMap();
    const busy = new WeakSet();
    root.addEventListener('submit', async event => {
      const form = event.target;
      if (!forms.includes(form)) { return; }
      const destination = new URL(form.action);
      if (destination.origin !== 'https://formsubmit.co' ||
          destination.pathname !== '/info@lpvturismo.com' ||
          form.querySelector('input[type="file"]') ||
          form.querySelector('input[name="_captcha"]')?.value !== 'false') { return; }
      event.preventDefault();
      // Run before legacy submit handlers, which only know that a submit was attempted.
      event.stopImmediatePropagation();
      if (busy.has(form) || !form.reportValidity()) { return; }
      let fields;
      try { fields = fieldsOf(form); } catch (_) { status(form, copy.failed, 'error'); return; }
      const serialized = JSON.stringify(fields);
      let attempt = attempts.get(form);
      if (!attempt || attempt.serialized !== serialized) {
        attempt = { serialized, id: 'lpv_lead_' + root.crypto.randomUUID() };
        attempts.set(form, attempt);
      }
      busy.add(form);
      const button = form.querySelector('button[type="submit"]');
      const originalText = button ? button.textContent : '';
      form.setAttribute('aria-busy', 'true');
      if (button) { button.disabled = true; button.textContent = copy.sending; }
      status(form, copy.sending, 'sending');
      try {
        saveReference();
        const allow = consented();
        const response = await fetch(leadUrl, {
          method: 'POST', credentials: 'same-origin', cache: 'no-store',
          headers: { 'Content-Type': 'application/json', 'X-LPV-Nonce': nonce },
          body: JSON.stringify({
            id: attempt.id, source: root.location.origin + root.location.pathname, fields,
            consent: allow, oppref: allow ? reference(read(REF_KEY)) : '',
          }),
        });
        const result = await response.json();
        if (!accepted(response, result)) { throw new Error('unconfirmed'); }
        status(form, copy.sent, 'success');
      } catch (_) { status(form, copy.failed, 'error'); }
      finally {
        busy.delete(form);
        form.removeAttribute('aria-busy');
        if (button) { button.disabled = false; button.textContent = originalText; }
      }
    }, true);
  }
  if (doc.readyState === 'loading') { doc.addEventListener('DOMContentLoaded', init, { once: true }); }
  else { init(); }
})(typeof window !== 'undefined' ? window : null);
