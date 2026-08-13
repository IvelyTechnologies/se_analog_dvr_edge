"""Self-contained local setup page for the Analog DVR Edge service."""


def build_setup_page(product_name: str, version: str) -> str:
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{product_name} Setup</title>
<style>
  :root {{ color-scheme: dark; --bg:#101720; --panel:#182331; --line:#2d3d50; --text:#eef4fb; --muted:#9eafc3; --blue:#3985ff; --green:#1ebc78; --red:#ef5b5b; --amber:#f5ac38; }}
  * {{ box-sizing:border-box; }} body {{ margin:0; min-width:320px; background:var(--bg); color:var(--text); font:14px/1.45 Arial,sans-serif; }}
  header {{ height:64px; display:flex; align-items:center; justify-content:space-between; padding:0 24px; background:#142030; border-bottom:1px solid var(--line); }}
  h1 {{ margin:0; font-size:19px; letter-spacing:0; }} .version {{ color:var(--muted); font-size:12px; }}
  main {{ max-width:1120px; margin:28px auto; padding:0 20px; display:grid; grid-template-columns:minmax(0,1fr) 330px; gap:20px; }}
  section {{ background:var(--panel); border:1px solid var(--line); border-radius:8px; }} .section-head {{ padding:16px 18px; border-bottom:1px solid var(--line); display:flex; align-items:center; justify-content:space-between; }}
  h2 {{ margin:0; font-size:15px; }} form {{ padding:18px; }} .grid {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; }} .full {{ grid-column:1/-1; }}
  label {{ display:block; color:var(--muted); font-size:12px; margin-bottom:6px; }} input,textarea,select {{ width:100%; min-height:38px; padding:8px 10px; color:var(--text); background:#101923; border:1px solid #3b4d61; border-radius:5px; font:inherit; }} textarea {{ min-height:96px; resize:vertical; }} input:focus,textarea:focus,select:focus {{ outline:2px solid #3985ff88; border-color:var(--blue); }}
  .actions {{ display:flex; flex-wrap:wrap; gap:10px; margin-top:20px; }} button {{ min-height:38px; border:0; border-radius:5px; padding:0 14px; background:#314256; color:var(--text); font-weight:700; cursor:pointer; }} button.primary {{ background:var(--blue); }} button.success {{ background:var(--green); }} button:disabled {{ opacity:.55; cursor:wait; }}
  .status {{ padding:16px 18px; }} .badge {{ display:inline-flex; align-items:center; min-height:24px; padding:0 9px; border-radius:999px; font-size:12px; font-weight:700; }} .ok {{ background:#164c3a; color:#8cf0bc; }} .bad {{ background:#59282d; color:#ffb5b5; }} .warn {{ background:#5c451f; color:#ffd584; }}
  .row {{ padding:12px 0; border-bottom:1px solid var(--line); }} .row:last-child {{ border-bottom:0; }} .name {{ font-weight:700; }} .sub {{ color:var(--muted); overflow-wrap:anywhere; font-size:12px; margin-top:3px; }}
  pre {{ margin:0; min-height:110px; padding:14px; overflow:auto; background:#0d141d; color:#c6dbef; border-radius:0 0 8px 8px; font:12px/1.45 Consolas,monospace; }} #message {{ min-height:20px; margin:12px 0 0; color:var(--muted); }}
  .hidden {{ display:none; }} @media (max-width:820px) {{ main {{ grid-template-columns:1fr; margin-top:16px; }} .grid {{ grid-template-columns:1fr; }} .full {{ grid-column:auto; }} header {{ padding:0 16px; }} }}
</style>
</head>
<body>
<header><h1>{product_name} <span class="version">{version}</span></h1><span id="serviceState" class="badge warn">Loading</span></header>
<main>
  <section>
    <div class="section-head"><h2>DVR Configuration</h2><span id="streamCount" class="version"></span></div>
    <form id="configForm">
      <div class="grid">
        <div><label for="site_prefix">Site Prefix</label><input id="site_prefix" required></div>
        <div><label for="channels">Channels</label><input id="channels" inputmode="numeric" placeholder="1, 2, 3"></div>
        <div><label for="ip">DVR IP Address</label><input id="ip" required></div>
        <div><label for="username">DVR Username</label><input id="username"></div>
        <div><label for="password">DVR Password</label><input id="password" type="password" placeholder="Leave blank to keep saved password"></div>
        <div><label for="video_mode">Video Mode</label><select id="video_mode"><option value="copy">H.264 passthrough</option><option value="transcode">H.264 transcode</option></select></div>
        <div class="full"><label for="candidates">RTSP URL Candidates</label><textarea id="candidates" spellcheck="false"></textarea></div>
        <div class="media"><label for="width">Output Width</label><input id="width" type="number" min="160"></div>
        <div class="media"><label for="height">Output Height</label><input id="height" type="number" min="120"></div>
        <div class="media"><label for="fps">Output FPS</label><input id="fps" type="number" min="1" max="60"></div>
        <div class="media"><label for="bitrate">Bitrate</label><input id="bitrate"></div>
      </div>
      <div class="actions"><button type="button" id="saveBtn">Save</button><button type="button" id="probeBtn">Test Channels</button><button type="button" class="success" id="applyBtn">Apply and Start</button></div>
      <div id="message" role="status"></div>
    </form>
  </section>
  <section>
    <div class="section-head"><h2>Stream Status</h2><button id="refreshBtn" title="Refresh status">Refresh</button></div>
    <div id="workers" class="status"></div>
    <pre id="results">Waiting for status...</pre>
  </section>
</main>
<script>
const el = id => document.getElementById(id);
let currentConfig = null;
function setMessage(message, tone='') {{ el('message').textContent = message; el('message').style.color = tone === 'error' ? 'var(--red)' : tone === 'success' ? '#8cf0bc' : 'var(--muted)'; }}
async function request(path, options={{}}) {{ const response = await fetch(path, options); const data = await response.json(); if (!response.ok || data.ok === false) throw new Error(data.error || data.last_start_error || 'Request failed'); return data; }}
function setMediaVisibility() {{ const disabled = el('video_mode').value === 'copy'; document.querySelectorAll('.media input').forEach(input => input.disabled = disabled); document.querySelectorAll('.media').forEach(node => node.classList.toggle('hidden', disabled)); }}
function populate(config) {{ currentConfig = config; const dvr=config.dvr||{{}}; const media=config.media||{{}}; el('site_prefix').value=config.site_prefix||''; el('ip').value=dvr.ip||''; el('username').value=dvr.username||''; el('password').value=''; el('channels').value=(dvr.channels||[]).join(', '); el('video_mode').value=media.video_mode||'transcode'; el('width').value=media.width||640; el('height').value=media.height||360; el('fps').value=media.fps||10; el('bitrate').value=media.bitrate||'512k'; el('candidates').value=(config.rtsp_candidates||[]).join('\\n'); setMediaVisibility(); }}
function collect() {{ const channels=el('channels').value.split(',').map(value=>value.trim()).filter(Boolean).map(Number); const password=el('password').value.trim(); const media={{...(currentConfig?.media||{{}}), video_mode:el('video_mode').value, width:Number(el('width').value), height:Number(el('height').value), fps:Number(el('fps').value), bitrate:el('bitrate').value.trim()}}; return {{...currentConfig, site_prefix:el('site_prefix').value.trim(), dvr:{{...(currentConfig?.dvr||{{}}), ip:el('ip').value.trim(), username:el('username').value.trim(), password, channels}}, media, rtsp_candidates:el('candidates').value.split('\\n').map(value=>value.trim()).filter(Boolean)}}; }}
async function save() {{ const data=await request('/config', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(collect())}}); populate(data.config); setMessage('Configuration saved.', 'success'); return data; }}
function renderStatus(status) {{ const healthy=status.ok && status.running; el('serviceState').textContent=healthy ? 'Running' : (status.last_start_error ? 'Needs action' : 'Stopped'); el('serviceState').className='badge '+(healthy ? 'ok' : status.last_start_error ? 'bad' : 'warn'); const workers=status.workers||[]; el('streamCount').textContent=workers.length+' active stream'+(workers.length===1?'':'s'); el('workers').innerHTML=workers.length ? workers.map(worker=>`<div class="row"><div class="name">${{worker.stream_name}}</div><div class="sub">${{worker.process_running ? 'Publishing' : 'Stopped'}} | restarts: ${{worker.restart_count}}</div></div>`).join('') : '<div class="sub">No active DVR publisher.</div>'; el('results').textContent=JSON.stringify({{last_start_error:status.last_start_error, last_probe:status.last_probe}}, null, 2); }}
async function refresh() {{ const [config,status]=await Promise.all([request('/config'),request('/status')]); populate(config); renderStatus(status); }}
async function busy(button, work) {{ button.disabled=true; try {{ await work(); }} catch(error) {{ setMessage(error.message, 'error'); }} finally {{ button.disabled=false; }} }}
el('video_mode').addEventListener('change', setMediaVisibility); el('refreshBtn').addEventListener('click',()=>busy(el('refreshBtn'),refresh)); el('saveBtn').addEventListener('click',()=>busy(el('saveBtn'),save)); el('probeBtn').addEventListener('click',()=>busy(el('probeBtn'),async()=>{{ await save(); const data=await request('/probe',{{method:'POST'}}); el('results').textContent=JSON.stringify(data.results,null,2); setMessage('Channel test completed.', 'success'); }})); el('applyBtn').addEventListener('click',()=>busy(el('applyBtn'),async()=>{{ await save(); const data=await request('/workers/reload',{{method:'POST'}}); renderStatus(data); setMessage(data.running ? 'DVR publishers started.' : (data.last_start_error||'No DVR publisher started.'), data.running?'success':'error'); }})); refresh().catch(error=>setMessage(error.message,'error'));
</script>
</body>
</html>'''
