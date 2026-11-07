import {next} from '@vercel/functions';
import {equal,passwordHash,makeSession,validSession,sessionCookie,readSession} from './server/auth.js';
export const config={matcher:'/:path*',runtime:'nodejs'};
const attempts=new Map();
const headers={'Cache-Control':'private, no-store','Content-Type':'text/html; charset=utf-8','X-Content-Type-Options':'nosniff','Content-Security-Policy':"default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"};
function page(error='',status=200){return new Response(`<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="color-scheme" content="dark"><title>Sign in · PacketIntelligence</title><style>*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;background:#111923;color:#e6edf4;font:16px system-ui,sans-serif;padding:24px}main{width:100%;max-width:430px;border:1px solid #354355;background:#1b2734;padding:36px;border-radius:8px}.brand{font-weight:700;letter-spacing:-.7px;font-size:25px}.mark{display:inline-grid;place-items:center;width:32px;height:32px;margin-right:9px;background:#e6edf4;color:#172330;border-radius:4px}small{display:block;color:#91a3b7;font-size:11px;letter-spacing:1.4px;margin-top:15px}h1{font-size:25px;margin:28px 0 8px}p{font-size:14px;line-height:1.6;color:#aab9c9}label{display:block;font-size:13px;margin:22px 0 8px}input{width:100%;padding:12px;border:1px solid #48596c;border-radius:4px;background:#111b27;color:#fff;font:inherit}input:focus{outline:2px solid #85b9e9;outline-offset:2px}button{width:100%;margin-top:28px;padding:13px;background:#87b9e7;color:#0c2034;border:0;border-radius:4px;font-weight:700;font-size:15px;cursor:pointer}.error{color:#ffc1b6;background:#4a2c2e;padding:12px;border-radius:4px}.foot{border-top:1px solid #354355;padding-top:18px;margin-top:25px;font-size:12px}</style></head><body><main><div class="brand"><span class="mark">P</span>PacketIntelligence</div><small>RESEARCH & OPERATIONS WORKSPACE</small><h1>Sign in to your workspace</h1><p>Enter the shared test credentials to access the dashboard and research documents.</p>${error?`<p role="alert" class="error">${error}</p>`:''}<form method="post" action="/login"><label for="username">Username</label><input id="username" name="username" autocomplete="username" required maxlength="100"><label for="password">Password</label><input id="password" name="password" type="password" autocomplete="current-password" required maxlength="200"><button type="submit">Sign in →</button></form><p class="foot">Test workspace · Sessions expire after 8 hours.</p></main></body></html>`,{status,headers})}
function redirect(path,cookie){const h={'Location':path,'Cache-Control':'private, no-store'};if(cookie)h['Set-Cookie']=cookie;return new Response(null,{status:303,headers:h})}
export default async function middleware(request){
 const url=new URL(request.url),user=process.env.PACKET_TEST_USER,hash=process.env.PACKET_TEST_PASSWORD_HASH,secret=process.env.PACKET_SESSION_SECRET;
 if(!user||!hash||!secret||secret.length<32)return page('Sign-in is not configured. Contact the workspace administrator.',503);
 if(request.method==='POST'&&['/login','/logout'].includes(url.pathname)&&request.headers.get('origin')!==url.origin)return new Response('Invalid request origin',{status:403,headers:{'Cache-Control':'no-store'}});
 if(url.pathname==='/logout'){if(request.method!=='POST')return new Response('Use the Sign out button.',{status:405,headers:{Allow:'POST'}});return redirect('/login',sessionCookie('',0))}
 const authenticated=await validSession(readSession(request),user,secret);
 if(url.pathname==='/login'){
  if(request.method==='GET')return authenticated?redirect('/'):page();
  if(request.method!=='POST')return new Response('Method not allowed',{status:405});
  if(+(request.headers.get('content-length')||0)>4096)return page('Unable to sign in. Please try again.',400);
  const ip=request.headers.get('x-real-ip')||'unknown',now=Date.now();let attempt=attempts.get(ip);if(attempt&&now-attempt.start>900000){attempts.delete(ip);attempt=null}if(attempt?.count>=10)return page('Too many attempts. Try again in 15 minutes.',429);
  let form;try{const body=await request.text();if(body.length>4096)throw Error();form=new URLSearchParams(body)}catch{return page('Unable to sign in. Please try again.',400)}
  const suppliedUser=form.get('username')||'',password=form.get('password')||'';const [salt,expected]=hash.split(':');const actual=password.length<=200?await passwordHash(password,salt):'';
  if(!equal(suppliedUser,user)||!equal(actual,expected)){if(attempts.size>10000)attempts.clear();attempts.set(ip,{start:attempt?.start||now,count:(attempt?.count||0)+1});return page('Username or password is incorrect.',401)}
  attempts.delete(ip);return redirect('/',sessionCookie(await makeSession(user,secret)));
 }
 if(!authenticated)return redirect('/login');
 const response=next();response.headers.set('Cache-Control','private, no-store');return response;
}
