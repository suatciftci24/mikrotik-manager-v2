// Read-only preflight: select an already-installed Linux browser; never launch or download it.
import {chromium} from '../../.local/browser-tools/node_modules/playwright/index.mjs';
import {selectBrowser} from './browserRuntime.mjs';

selectBrowser(chromium);
console.log('PASS: local Playwright and existing Linux browser executable available');
