const { execSync } = require('child_process');
const result = execSync('node scripts/verify-local-sealed-json-v0.1.mjs',{encoding:'utf8'}).trim();
if(result!=='valid') throw new Error('Verification failed: '+result);
