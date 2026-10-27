const encoder=new TextEncoder();
export const COOKIE='__Host-packet_session';
export const SESSION_SECONDS=8*60*60;
const hex=bytes=>Array.from(new Uint8Array(bytes),v=>v.toString(16).padStart(2,'0')).join('');
const unhex=s=>Uint8Array.from(s.match(/.{2}/g)||[],h=>parseInt(h,16));
export function equal(a,b){if(typeof a!=='string'||typeof b!=='string')return false;let diff=a.length^b.length;for(let i=0;i<Math.max(a.length,b.length);i++)diff|=(a.charCodeAt(i)||0)^(b.charCodeAt(i)||0);return diff===0}
export async function passwordHash(password,salt){const key=await crypto.subtle.importKey('raw',encoder.encode(password),'PBKDF2',false,['deriveBits']);return hex(await crypto.subtle.deriveBits({name:'PBKDF2',salt:encoder.encode(salt),iterations:150000,hash:'SHA-256'},key,256))}
async function signature(body,secret){const key=await crypto.subtle.importKey('raw',encoder.encode(secret),{name:'HMAC',hash:'SHA-256'},false,['sign']);return hex(await crypto.subtle.sign('HMAC',key,encoder.encode(body)))}
export async function makeSession(user,secret,now=Date.now()){const body=btoa(JSON.stringify({user,exp:Math.floor(now/1000)+SESSION_SECONDS,nonce:crypto.randomUUID()}));return body+'.'+await signature(body,secret)}
export async function validSession(token,user,secret,now=Date.now()){try{if(!secret||!token||token.length>2048)return false;const [body,sig,...rest]=token.split('.');if(rest.length||!sig||!/^[a-f0-9]{64}$/.test(sig))return false;if(!equal(sig,await signature(body,secret)))return false;const data=JSON.parse(atob(body));return data.user===user&&Number.isInteger(data.exp)&&data.exp>Math.floor(now/1000)&&data.exp<=Math.floor(now/1000)+SESSION_SECONDS}catch{return false}}
export function sessionCookie(value,maxAge=SESSION_SECONDS){return `${COOKIE}=${value}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${maxAge}`}
export function readSession(request){return (request.headers.get('cookie')||'').split(';').map(s=>s.trim()).find(s=>s.startsWith(COOKIE+'='))?.slice(COOKIE.length+1)||''}
