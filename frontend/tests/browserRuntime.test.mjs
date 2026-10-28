import {test} from 'node:test';
import assert from 'node:assert/strict';
import {selectBrowser} from './browserRuntime.mjs';
const chromium={executablePath:()=>'/repo/browsers/chromium-1248/chrome-linux64/chrome'};
const options=paths=>({env:{},home:'/home/test',usable:p=>paths.includes(p)});
test('uses the configured Playwright binary first',()=>{
 const result=selectBrowser(chromium,options([chromium.executablePath(),'/usr/bin/chromium']));
 assert.equal(result.executablePath,chromium.executablePath());assert.equal(result.headless,true);
});
test('reuses the same revision in the standard user cache',()=>{
 const path='/home/test/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome';
 assert.equal(selectBrowser(chromium,options([path])).executablePath,path);
});
test('uses installed Linux Chromium without downloading',()=>{
 assert.equal(selectBrowser(chromium,options(['/usr/bin/chromium'])).executablePath,'/usr/bin/chromium');
});
test('explicit binary is honored without silently falling back',()=>{
 assert.equal(selectBrowser(chromium,{...options(['/custom/chrome']),env:{V2_BROWSER_EXECUTABLE:'/custom/chrome'}}).executablePath,'/custom/chrome');
 assert.throws(()=>selectBrowser(chromium,{...options(['/usr/bin/chromium']),env:{V2_BROWSER_EXECUTABLE:'/missing'}}),/BLOCKED/);
});
test('missing browsers and Windows executables block without launch',()=>{
 assert.throws(()=>selectBrowser(chromium,options([])),/indirme denenmedi/);
 assert.throws(()=>selectBrowser(chromium,{...options(['/mnt/c/chrome.exe']),env:{V2_BROWSER_EXECUTABLE:'/mnt/c/chrome.exe'}}),/BLOCKED/);
});
