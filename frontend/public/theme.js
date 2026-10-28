/* Blocking startup controller: apply the preference before styles and React paint. */
(() => {
  const key = 'mikrotik-manager-v2.theme';
  const media = window.matchMedia('(prefers-color-scheme: dark)');
  const valid = value => ['light', 'dark', 'system'].includes(value) ? value : 'system';
  const read = () => { try { return valid(localStorage.getItem(key)); } catch { return 'system'; } };
  let preference = read(), fallback = 'system', explicit = false;
  try { explicit = ['light','dark','system'].includes(localStorage.getItem(key)); } catch {}

  const apply = () => {
    const theme = preference === 'system' ? (media.matches ? 'dark' : 'light') : preference;
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme === 'dark' ? '#0a0e14' : '#f4f7fb');
    window.dispatchEvent(new Event('v2-theme-change'));
  };
  window.v2Theme = {
    getPreference: () => preference,
    setDefaultPreference: value => {fallback=valid(value);if(!explicit){preference=fallback;apply();}},
    setPreference: value => {
      explicit = true;
      preference = valid(value);
      try { localStorage.setItem(key, preference); } catch { /* In-memory selection still works. */ }
      apply();
    },
  };
  media.addEventListener('change', () => { if (preference === 'system') apply(); });
  window.addEventListener('storage', event => {
    if (event.key === key || event.key === null) { try{explicit=['light','dark','system'].includes(localStorage.getItem(key));}catch{explicit=false;}preference=explicit?read():fallback;apply(); }
  });
  apply();
})();
