import fs from 'fs';
const data = JSON.parse(fs.readFileSync('research/fixtures/local-sealed-json-v0.1.json','utf8'));
function isValid(card){
  const required=['id','sport','description','provenance','rights','abstention'];
  for(const f of required) if(!(f in card)) return false;
  if(typeof card.abstention!=="boolean") return false;
  if(card.videoBinding && typeof card.videoBinding.url!=='string') return false;
  // fail-closed: if videoBinding missing url, invalid
  if(card.videoBinding && !card.videoBinding.url) return false;
  return true;
}
console.log(isValid(data)?'valid':'invalid');
