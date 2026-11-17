import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {buildSync} from 'esbuild';
import {renderToStaticMarkup} from 'react-dom/server';
import {subscriberExpiryCounts,filterSubscribers,EMPTY_SUBSCRIBER_FILTERS} from '../src/lib/subscriberFilters.ts';
import {turkeyToday,expiryInfo,matchesExpiry} from '../src/lib/expiry.ts';
const today=turkeyToday(new Date('2026-11-16T21:01:00Z'));
const dates=['2026-11-16','2026-11-17','2026-11-18','2026-11-20','2026-11-21','2026-11-24','2026-11-25','2026-12-17','2026-12-18',null,'bad','2026-02-30','0000-01-01'];
const rows=dates.map((expires_on,i)=>({id:String(i),username:`test.${i}`,customer_name:'Ayşe Işık',plan:'Fiber',router_name:'Test Ev',expires_on,source:i%2?'RADIUS':'LOCAL',status:'ACTIVE'}));
test('exclusive groups partition all rows at Turkey midnight; invalid dates stay unknown',()=>{
 assert.equal(today,'2026-11-17');
 const counts=subscriberExpiryCounts(rows,today);
 assert.deepEqual(counts,{EXPIRED:1,TODAY:1,WITHIN_3:2,WITHIN_7:2,WITHIN_30:2,ACTIVE:1,UNKNOWN:4});
 assert.equal(Object.values(counts).reduce((a,b)=>a+b),rows.length);
 assert.equal(expiryInfo('2026-11-21',today).status,'WITHIN_7');
 assert.equal(matchesExpiry('2026-11-18','WITHIN_7',today),true);
});
test('username and multi-field terms intersect with LOCAL/RADIUS/unknown filters',()=>{
 const find=changes=>filterSubscribers(rows,{...EMPTY_SUBSCRIBER_FILTERS,...changes},today);
 assert.deepEqual(find({query:' TEST.3 ISIK EV ',source:'RADIUS'}).map(r=>r.id),['3']);
 assert.deepEqual(find({query:'test.3',source:'LOCAL'}),[]);
 assert.deepEqual(filterSubscribers([{...rows[0],source:null}],{...EMPTY_SUBSCRIBER_FILTERS,source:'UNKNOWN',query:'test.0'},today).map(r=>r.id),['0']);
});
const require=createRequire(import.meta.url),module={exports:{}};
const code=buildSync({entryPoints:['src/components/SubscriberExpiryGroups.tsx'],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime']}).outputFiles[0].text;
new Function('require','module','exports',code)(require,module,module.exports);
test('group controls expose one selected group and dispatch exact exclusive keys',()=>{
 let selected;const element=module.exports.SubscriberExpiryGroups({counts:subscriberExpiryCounts(rows,today),value:'WITHIN_7',onChange:value=>selected=value});
 const html=renderToStaticMarkup(element);
 assert.equal((html.match(/aria-pressed="true"/g)||[]).length,1);
 assert.match(html,/4–7 gün/);assert.match(html,/Bitiş tarihi bilinmiyor/);
 const children=element.props.children[1].props.children;
 children[1].find(button=>button.key==='WITHIN_30').props.onClick();assert.equal(selected,'WITHIN_30');
});
