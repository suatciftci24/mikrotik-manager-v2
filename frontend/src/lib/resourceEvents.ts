export function resourceInvalidated(path: string, prefixes: readonly string[], dependencies: readonly string[] = []) {
  return prefixes.some(prefix => [path, ...dependencies].some(dependency => {
    const resource = dependency.split('?', 1)[0];
    return resource === prefix || resource.startsWith(`${prefix}/`);
  }));
}

export function invalidateResources(prefixes: string[]) {
  window.dispatchEvent(new CustomEvent('v2-resource-change', {detail: prefixes}));
}
