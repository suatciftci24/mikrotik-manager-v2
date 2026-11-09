/** Fixed top-layer coordinates, clamped to the visible viewport (also mobile keyboards). */
export function subscriberMenuPosition(anchor:{left:number;right:number;top:number;bottom:number},size:{width:number;height:number},viewport:{width:number;height:number;left?:number;top?:number}){
 const margin=8,gap=4,startX=(viewport.left??0)+margin,startY=(viewport.top??0)+margin;
 const maxWidth=Math.max(0,viewport.width-margin*2),maxHeight=Math.max(0,viewport.height-margin*2);
 const width=Math.min(size.width,maxWidth),height=Math.min(size.height,maxHeight);
 const endX=startX+maxWidth,endY=startY+maxHeight;
 const left=Math.max(startX,Math.min(anchor.right-width,endX-width));
 const preferred=anchor.bottom+gap+height<=endY?anchor.bottom+gap:anchor.top-gap-height;
 return {left,top:Math.max(startY,Math.min(preferred,endY-height)),maxWidth,maxHeight};
}
