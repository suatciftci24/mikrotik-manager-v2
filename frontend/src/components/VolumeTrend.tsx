import { useId } from 'react';
import { volumeGB } from '../lib/internetReport';
type Bucket={label:string;download:number|null;upload:number|null;samples:number};
/** Discrete byte-volume columns; no interpolated lines through absent samples. */
export function VolumeTrend({buckets}:{buckets:Bucket[]}){
  const id=useId();
  const known=buckets.flatMap(bucket=>[bucket.download,bucket.upload].filter((value):value is number=>value!==null));
  if(!known.length)return <p className="missing-data">Veri yok. Bu dönemde çizilecek indirme/yükleme ölçümü yok.</p>;
  const max=Math.max(...known,1),left=115,top=20,height=150,width=580,step=width/Math.max(buckets.length,1);
  return <figure className="volume-trend">
    <figcaption id={id}>Kayıtlı örnek hacmi · indirme / yükleme · GB</figcaption>
    <svg viewBox="0 0 720 215" role="img" aria-labelledby={id}>
      {[0,0.5,1].map(ratio=><g key={ratio}><line className="chart-grid" x1={left} x2={left+width} y1={top+height*(1-ratio)} y2={top+height*(1-ratio)}/><text x={left-8} y={top+height*(1-ratio)+4} textAnchor="end">{volumeGB(Math.floor(max*ratio))}</text></g>)}
      {buckets.map((bucket,index)=><g key={index}><title>{bucket.label+' · İndirme '+volumeGB(bucket.download)+' · Yükleme '+volumeGB(bucket.upload)+' · '+bucket.samples+' kayıt'}</title>
        {bucket.download!==null&&<rect className="volume-download" x={left+step*index+step*0.1} y={top+height*(1-bucket.download/max)} width={step*0.35} height={height*bucket.download/max}/>}
        {bucket.upload!==null&&<rect className="volume-upload" x={left+step*index+step*0.55} y={top+height*(1-bucket.upload/max)} width={step*0.35} height={height*bucket.upload/max}/>}
        {(index===0||index===buckets.length-1||index%Math.ceil(buckets.length/6)===0)&&<text x={left+step*(index+0.5)} y={top+height+23} textAnchor="middle">{bucket.label}</text>}
      </g>)}
    </svg>
    <p className="daily-description"><span className="volume-legend-download">İndirme</span> · <span className="volume-legend-upload">Yükleme</span>. Boş aralıklar çizilmez; kayıtlı sıfır, gerçek sıfır örneğidir. GB hacimdir, Mbps hız değildir.</p>
  </figure>;
}
