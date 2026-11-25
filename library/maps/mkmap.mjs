import fs from 'fs';import {feature} from 'topojson-client';import {geoMercator} from 'd3-geo';import pc from 'polygon-clipping';
const topo=JSON.parse(fs.readFileSync('node_modules/world-atlas/countries-50m.json'));
const fc=feature(topo,topo.objects.countries);
const want={'364':'إيران','512':'عُمان','784':'الإمارات','682':'السعودية','634':'قطر','048':'البحرين'};
const B=[[53.2,23.2],[60.2,28.6]];
const pr=geoMercator().fitExtent([[-100,-130],[100,130]],{type:'Polygon',coordinates:[[[B[0][0],B[0][1]],[B[0][0],B[1][1]],[B[1][0],B[1][1]],[B[1][0],B[0][1]],[B[0][0],B[0][1]]]]});
const rect=[[[-320,-320],[320,-320],[320,320],[-320,320],[-320,-320]]];
const out=[];
for(const f of fc.features){const id=String(f.id).padStart(3,'0');if(!want[id])continue;
  const polys=f.geometry.type==='Polygon'?[f.geometry.coordinates]:f.geometry.coordinates;
  for(const p of polys){const rings=p.map(r=>r.map(c=>pr(c)));const cl=pc.intersection([rings],[rect]);
    for(const q of cl){const outer=q[0];let a=0;for(let i=1;i<outer.length;i++)a+=outer[i-1][0]*outer[i][1]-outer[i][0]*outer[i-1][1];if(Math.abs(a)<2)continue;
      out.push({id,name:want[id],rings:q.map(r=>r.map(([x,y])=>[+x.toFixed(2),+y.toFixed(2)]))})}}}
const P=(lon,lat)=>pr([lon,lat]).map(v=>+v.toFixed(2));
const pts={hormuz:P(56.5,26.55),bandar:P(56.27,27.18),qeshm:P(55.9,26.8),fujairah:P(56.35,25.12),khasab:P(56.24,26.18),gulfOman:P(58.2,25.0),muscat:P(58.4,23.6),dubai:P(55.3,25.25)};
fs.writeFileSync('assets/map.json',JSON.stringify({polys:out,pts}));
console.log(out.length,'polys', out.map(o=>o.name).join(','));console.log(pts);
