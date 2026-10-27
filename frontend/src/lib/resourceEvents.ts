export function invalidateResources(prefixes: string[]) {
  window.dispatchEvent(new CustomEvent('v2-resource-change', {detail: prefixes}));
}
