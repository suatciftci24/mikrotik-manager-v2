// Match the explicit loopback endpoints used by dev.sh and the API manager.
function port(name,fallback){
 const raw=process.env[name]??String(fallback);
 if(!/^[0-9]+$/.test(raw)||Number(raw)<1024||Number(raw)>65535)throw new Error(`Invalid ${name}`);
 return String(Number(raw));
}
export const localPorts=[port('V2_UI_PORT',5173),port('V2_API_PORT',8000)];
if(localPorts[0]===localPorts[1])throw new Error('V2 UI/API ports must differ');
export const uiBase=`http://127.0.0.1:${localPorts[0]}`;
