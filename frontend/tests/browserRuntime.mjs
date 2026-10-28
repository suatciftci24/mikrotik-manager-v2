// Reuse local binaries only. Never download or attach to a personal browser profile.
import {accessSync,constants} from 'node:fs';
import {homedir} from 'node:os';
import {basename,dirname,join} from 'node:path';

export function selectBrowser(chromium,{env=process.env,home=homedir(),usable=path=>{
 try{accessSync(path,constants.X_OK);return true;}catch{return false;}
}}={}){
 const expected=chromium.executablePath();
 const cacheBinary=join(home,'.cache/ms-playwright',basename(dirname(dirname(expected))),basename(dirname(expected)),basename(expected));
 const explicit=env.V2_BROWSER_EXECUTABLE;
 const candidates=explicit?[explicit]:[expected,cacheBinary,'/usr/bin/chromium','/usr/bin/chromium-browser','/usr/bin/google-chrome','/opt/google/chrome/chrome'];
 const executablePath=candidates.find(path=>!path.toLowerCase().endsWith('.exe')&&usable(path));
 if(!executablePath)throw new Error('BROWSER BLOCKED: kullanılabilir yerel Linux Chrome/Chromium yok; indirme denenmedi. Windows Chrome bu Linux Playwright sürecinden doğrudan başlatılamaz.');
 return {headless:true,executablePath};
}
