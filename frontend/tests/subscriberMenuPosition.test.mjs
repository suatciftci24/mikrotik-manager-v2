import {test} from 'node:test';
import assert from 'node:assert/strict';
import {subscriberMenuPosition} from '../src/lib/subscriberMenu.ts';

test('menu fits desktop/mobile edges without changing row geometry',()=>{
 for(const viewport of [{width:1000,height:600},{width:390,height:844},{width:320,height:220}]){
  for(const anchor of [{left:0,right:80,top:0,bottom:40},{left:viewport.width-80,right:viewport.width,top:viewport.height-40,bottom:viewport.height}]){
   const size={width:240,height:300},position=subscriberMenuPosition(anchor,size,viewport);
   assert.ok(position.left>=8);assert.ok(position.top>=8);
   assert.ok(position.left+Math.min(size.width,position.maxWidth)<=viewport.width-8);
   assert.ok(position.top+Math.min(size.height,position.maxHeight)<=viewport.height-8);
  }
 }
 const top=subscriberMenuPosition({left:200,right:280,top:500,bottom:540},{width:240,height:180},{width:1000,height:600});assert.equal(top.top,316);
});
test('visual viewport offsets and a mobile keyboard constrain the same fixed panel',()=>{
 const viewport={left:20,top:200,width:320,height:200};
 const p=subscriberMenuPosition({left:300,right:370,top:350,bottom:390},{width:240,height:300},viewport);
 assert.ok(p.left>=28);assert.ok(p.top>=208);assert.ok(p.left+240<=332);assert.ok(p.top+p.maxHeight<=392);
});

test('mobile menu opens below when it fits and scrolls above a low trigger',()=>{
 const viewport={width:390,height:480};
 const size={width:240,height:300};
 const below=subscriberMenuPosition({left:20,right:120,top:54,bottom:98},size,viewport,true);
 assert.equal(below.top,102);
 assert.equal(below.maxHeight,370);
 const above=subscriberMenuPosition({left:20,right:120,top:275,bottom:319},size,viewport,true);
 assert.equal(above.top,8);
 assert.equal(above.maxHeight,263);
 assert.equal(above.top+above.maxHeight,271);
});

test('mobile menu uses the larger lower space when neither side fits',()=>{
 const viewport={left:20,top:200,width:320,height:200};
 const position=subscriberMenuPosition({left:300,right:370,top:235,bottom:279},{width:240,height:300},viewport,true);
 assert.equal(position.left,92);
 assert.equal(position.top,283);
 assert.equal(position.maxHeight,109);
});
