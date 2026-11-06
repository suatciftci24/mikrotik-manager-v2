/** Build a LOCAL review tree from the supplied VDS snapshot. No deployment/network. */
import * as fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import {parseArgs} from 'node:util';

const repo=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const frontend=path.join(repo,'frontend');
export const referenceCommit='189a717357a7136c83ccf5958a7d136c3f90303f';
export const overlayFiles=Object.freeze([
 'components/SubscriberDeviceCenter.tsx','components/LegacySubscriberActions.tsx',
 'components/QuickActions.tsx','screens/Details.tsx','lib/subscriberActions.ts',
 'lib/subscriberDependencies.ts','lib/quick.ts','lib/resourceEvents.ts',
 'lib/useResource.ts','styles/subscriber-edit-highlight.css',
]);
const sha=data=>createHash('sha256').update(data).digest('hex');
function exists(p){try{fs.lstatSync(p);return true;}catch(error){if(error.code==='ENOENT')return false;throw error;}}
function files(root){
 const result={};
 function visit(dir){
  for(const entry of fs.readdirSync(dir,{withFileTypes:true})){
   const name=path.join(dir,entry.name);
   if(entry.isSymbolicLink())throw Error('SYMLINK_REJECTED');
   if(entry.isDirectory())visit(name);
   else if(entry.isFile())result[path.relative(root,name).split(path.sep).join('/')]=fs.readFileSync(name);
   else throw Error('NON_SOURCE_FILE_REJECTED');
  }
 }
 if(fs.realpathSync(root)!==root)throw Error('REFERENCE_PATH_REJECTED');
 visit(root);return result;
}
export function expectedReference(){
 const pinned=JSON.parse(fs.readFileSync(new URL('./v26-vds-reference.json',import.meta.url),'utf8'));
 if(pinned.referenceCommit!==referenceCommit)throw Error('REFERENCE_MANIFEST_REJECTED');
 return pinned.sourceSha256;
}
export function prepareLegacyCandidate({reference,output}){
 reference=path.resolve(reference);output=path.resolve(output);
 const parent=path.join(repo,'.local');
 if(path.dirname(output)!==parent||!/^v26-legacy-[A-Za-z0-9-]+$/.test(path.basename(output))||
    fs.realpathSync(parent)!==parent||exists(output))throw Error('NEW_LOCAL_OUTPUT_REQUIRED');
 const before=files(reference),expected=expectedReference();
 if(Object.keys(before).length!==Object.keys(expected).length||
    Object.entries(expected).some(([name,digest])=>!before[name]||sha(before[name])!==digest)){
  throw Error('REFERENCE_DRIFT_STOP; no files copied');
 }
 const overlay=Object.fromEntries(overlayFiles.map(name=>{
  const source=path.join(frontend,'src',name);
  if(fs.realpathSync(source)!==source)throw Error('OVERLAY_PATH_REJECTED');
  return [name,fs.readFileSync(source)];
 }));
 fs.mkdirSync(output,{mode:0o700});
 try{
  for(const [name,data] of Object.entries({...before,...overlay})){
   const target=path.join(output,'src',name);
   fs.mkdirSync(path.dirname(target),{recursive:true});fs.writeFileSync(target,data,{flag:'wx'});
  }
  // Dependency versions are pinned by the LOCAL lockfile; no npm install/network.
  for(const name of ['package.json','package-lock.json','tsconfig.json','vite.config.ts','index.html']){
   fs.copyFileSync(path.join(frontend,name),path.join(output,name),fs.constants.COPYFILE_EXCL);
  }
  fs.cpSync(path.join(frontend,'public'),path.join(output,'public'),{recursive:true,errorOnExist:true,force:false});
  fs.symlinkSync(path.join(frontend,'node_modules'),path.join(output,'node_modules'),'dir');
  const after=files(path.join(output,'src'));
  for(const [name,data] of Object.entries(before)){
   if(!overlayFiles.includes(name)&&!data.equals(after[name]))throw Error('PRESERVATION_FAILED');
  }
  const manifest={referenceCommit,integrationBase:'ac90735ecdfe8c1e4b063935a436ac8681622ca2',
   overlaySha256:Object.fromEntries(Object.entries(overlay).map(([name,data])=>[name,sha(data)])),overlayFiles,
   referenceSourceFiles:Object.keys(before).length,
   unchangedSourceFiles:Object.keys(before).filter(name=>!overlayFiles.includes(name)).length,
   packageLockSha256:sha(fs.readFileSync(path.join(output,'package-lock.json'))),
   before:Object.fromEntries(Object.entries(before).map(([name,data])=>[name,sha(data)])),
   after:Object.fromEntries(Object.entries(after).map(([name,data])=>[name,sha(data)]))};
  fs.writeFileSync(path.join(output,'preservation.json'),JSON.stringify(manifest,null,2)+'\n',{flag:'wx'});
  return manifest;
 }catch(error){fs.rmSync(output,{recursive:true,force:true});throw error;}
}

if(process.argv[1]&&import.meta.url===pathToFileURL(path.resolve(process.argv[1])).href){
 try{
  const {values}=parseArgs({options:{reference:{type:'string'},output:{type:'string'}}});
  if(!values.reference||!values.output)throw Error('REQUIRED: --reference <snapshot/src> --output <repo/.local/v26-legacy-name>');
  const manifest=prepareLegacyCandidate(values);
  console.log(`LOCAL CANDIDATE READY: ${manifest.referenceSourceFiles} reference files; ${manifest.unchangedSourceFiles} unchanged; ${overlayFiles.length} overlay files. Build/tests still required.`);
 }catch(error){console.error('BLOCKED:',error.message);process.exitCode=1;}
}
