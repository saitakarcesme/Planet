const fs=require('node:fs'), vm=require('node:vm'), assert=require('node:assert/strict'), path=require('node:path');
const field=vm.createContext({Math});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../app/DotField.js'),'utf8'),field);
for (const size of [48,60,76]) {
const scale=size/48;
const dots=field.points(size);
let minimumGap=Infinity;
for(let i=0;i<dots.length;i++) {
  for(let j=i+1;j<dots.length;j++) {
    // Continuous bound: both dots at maximum radius, drifting toward one another.
    const gap=Math.hypot(dots[i].x-dots[j].x,dots[i].y-dots[j].y)
      -2*field.maximumRadius*scale-2*field.maximumDrift*scale;
    minimumGap=Math.min(minimumGap,gap);
  }
  let low=Infinity,high=0;
  for(const phase of ['idle','thinking','acting','success','error']) {
    for(let t=0;t<30;t+=0.07) {
      const r=field.radiusAt(dots[i],t,phase,false);
      assert(r>=field.minimumRadius*scale && r<=field.maximumRadius*scale);
      const p=field.positionAt(dots[i],t);
      assert(Math.hypot(p.x-size/2,p.y-size/2)+r<size/2);
      if(phase==='idle') { low=Math.min(low,r); high=Math.max(high,r); }
    }
  }
  assert(high-low>1,'Visible size variation in every dot');
}
assert(minimumGap>1.2);
assert(dots.length>=30);
console.log(JSON.stringify({size,dots:dots.length,minimumGapPx:minimumGap,result:'PASS'}));

}
