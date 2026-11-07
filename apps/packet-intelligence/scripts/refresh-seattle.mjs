// Explicit refresh of the bounded public-government snapshot. Never runs in the browser.
import {writeFile} from 'node:fs/promises';
const url=new URL('https://data.seattle.gov/resource/76t5-zqzr.json');
url.search=new URLSearchParams({'$where':"contains(upper(description),'RESTAURANT')",'$order':'applieddate DESC,permitnum ASC','$limit':'500'});
const response=await fetch(url);
if(!response.ok)throw Error(`Seattle source returned ${response.status}`);
const rows=await response.json();
if(!Array.isArray(rows)||rows.some(r=>!r.permitnum))throw Error('Unexpected government dataset schema');
await writeFile(new URL('../public/seattle-data.js',import.meta.url),'const seattlePermits='+JSON.stringify(rows)+';\n');
console.log(`Refreshed ${rows.length} official permit records. Review the snapshot date and rebuild before publishing.`);
