// Read-only preflight: select an already-installed Linux browser; never launch or download it.
import {chromium} from 'playwright-core';
import {selectBrowser} from './browserRuntime.mjs';

selectBrowser(chromium);
console.log('PASS: local Playwright and existing Linux browser executable available');
