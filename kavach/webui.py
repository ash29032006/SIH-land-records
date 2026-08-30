"""Render the reviewer's view as one self-contained page.

No server, no build step, no network. `python -m kavach.webui` writes an HTML file
that opens anywhere, with a real engine run embedded in it.

Design notes, so the choices are inspectable rather than assumed:

* The palette is taken from the project's own pipeline diagram — navy `#0F2A44`,
  teal `#10716C` — rather than a generic government blue.
* Finding-class colours were validated for colour-vision separation. Every adjacent
  pair passes the normal-vision and CVD floors. The light-mode teal sits at chroma
  0.098 against a 0.1 floor: a deliberate deviation, legal because these are status
  colours that always ship with a text label, and because moving it would abandon
  the project's own teal.
* `UNVERIFIABLE` is rendered in that teal, not in grey. Abstention is the
  distinctive output of this system, not a failure state, and the palette says so.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from kavach.classifications import default_schemes
from kavach.dashboard import build_payload
from kavach.mutations import apply_mutation
from kavach.records import RecordSet
from kavach.synthetic import DocumentProfile, MouzaSpec, synthetic_mouza
from kavach.units import default_registry

__all__ = ["DEMO_DEFECTS", "demo_register", "render", "render_fragment", "write"]

OUTPUT_PATH = Path(__file__).resolve().parents[1].joinpath("dashboard.html")

_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Kavach Register Review</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Spectral:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root{
  --ink:#0F2A44; --ink-2:#44586A; --ink-3:#7288A0;
  --ground:#E8EDF1; --surface:#FFFFFF; --surface-2:#F4F7F9; --surface-3:#EAF0F4;
  --rule:#C2D0DB; --rule-soft:#DFE7ED;
  --accent:#10716C; --accent-ink:#0B564F; --accent-wash:#E4F0EE;
  --certain:#B02133; --conflict:#A8790A; --anomaly:#6D4CA0; --unverif:#068276;
  --certain-wash:#FBEDEF; --conflict-wash:#FAF4E4; --anomaly-wash:#F3EEFA; --unverif-wash:#E5F2F0;
  --seq-0:#E4EDEB; --seq-1:#C2DAD6; --seq-2:#8FBDB6; --seq-3:#57998F; --seq-4:#2A7C71; --seq-5:#0E5F55;
  --stamp:#8A2B36; --sel:#DCE9F2;
  --topbar:#0F2A44; --topbar-ink:#DCE6EF; --topbar-ink-2:#8FA6BC; --topbar-rule:#22415E;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --ink:#E7EDF2; --ink-2:#A3B4C4; --ink-3:#76889A;
  --ground:#0A121A; --surface:#111C26; --surface-2:#16222E; --surface-3:#1B2934;
  --rule:#2A3B4A; --rule-soft:#1F2E3B;
  --accent:#3DAFA4; --accent-ink:#7FCFC6; --accent-wash:#102A28;
  --certain:#DA5C70; --conflict:#AE821A; --anomaly:#9A7BCC; --unverif:#2AA795;
  --certain-wash:#291620; --conflict-wash:#231C10; --anomaly-wash:#1E1929; --unverif-wash:#0E2521;
  --seq-0:#16222E; --seq-1:#1C3836; --seq-2:#234E47; --seq-3:#2B665C; --seq-4:#348072; --seq-5:#469E90;
  --stamp:#D9707C; --sel:#1C3247;
  --topbar:#08111A; --topbar-ink:#DCE6EF; --topbar-ink-2:#7B92A8; --topbar-rule:#1B2E42;
}}
:root[data-theme="dark"]{
  --ink:#E7EDF2; --ink-2:#A3B4C4; --ink-3:#76889A;
  --ground:#0A121A; --surface:#111C26; --surface-2:#16222E; --surface-3:#1B2934;
  --rule:#2A3B4A; --rule-soft:#1F2E3B;
  --accent:#3DAFA4; --accent-ink:#7FCFC6; --accent-wash:#102A28;
  --certain:#DA5C70; --conflict:#AE821A; --anomaly:#9A7BCC; --unverif:#2AA795;
  --certain-wash:#291620; --conflict-wash:#231C10; --anomaly-wash:#1E1929; --unverif-wash:#0E2521;
  --seq-0:#16222E; --seq-1:#1C3836; --seq-2:#234E47; --seq-3:#2B665C; --seq-4:#348072; --seq-5:#469E90;
  --stamp:#D9707C; --sel:#1C3247;
  --topbar:#08111A; --topbar-ink:#DCE6EF; --topbar-ink-2:#7B92A8; --topbar-rule:#1B2E42;
}

*{box-sizing:border-box}
html{height:100%}
body{
  margin:0; height:100%; overflow:hidden; background:var(--ground); color:var(--ink);
  font-family:"IBM Plex Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  font-size:13px; line-height:1.45; -webkit-font-smoothing:antialiased;
}
.mono{font-family:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace;font-variant-numeric:tabular-nums}
.num{font-variant-numeric:tabular-nums}
:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}
button{font:inherit;color:inherit}

/* ---------------- app shell ---------------- */
.app{height:100dvh;display:grid;grid-template-rows:46px minmax(0,1fr) 26px;background:var(--ground)}
.work{display:grid;grid-template-columns:288px minmax(0,1fr) 384px;min-height:0;background:var(--rule);gap:1px}
.pane{background:var(--surface);min-height:0;display:flex;flex-direction:column;overflow:hidden}
.scroll{overflow-y:auto;overscroll-behavior:contain;min-height:0}
@media (max-width:1320px){.work{grid-template-columns:260px minmax(0,1fr) 340px}}
@media (max-width:1080px){
  .work{grid-template-columns:236px minmax(0,1fr)}
  #detail{position:fixed;top:46px;right:0;bottom:26px;width:min(380px,90vw);
          box-shadow:-14px 0 40px -18px rgba(0,0,0,.45);z-index:40;transform:translateX(101%);
          transition:transform .2s cubic-bezier(.2,.7,.3,1);border-left:1px solid var(--rule)}
  #detail.open{transform:none}
  .closeDetail{display:inline-flex!important}
}
@media (max-width:760px){
  .work{grid-template-columns:minmax(0,1fr)}
  #rail{position:fixed;top:46px;left:0;bottom:26px;width:270px;z-index:39;transform:translateX(-101%);
        transition:transform .2s;border-right:1px solid var(--rule);box-shadow:14px 0 40px -18px rgba(0,0,0,.45)}
  #rail.open{transform:none}
  .railToggle{display:inline-flex!important}
}

/* ---------------- topbar ---------------- */
.topbar{
  background:var(--topbar);color:var(--topbar-ink);display:flex;align-items:center;
  gap:0;padding:0 12px;border-bottom:1px solid var(--topbar-rule);
}
.mark{display:flex;align-items:center;gap:8px;padding-right:14px;margin-right:14px;border-right:1px solid var(--topbar-rule)}
.mark .glyph{
  width:24px;height:24px;border:1.5px solid var(--topbar-ink);display:grid;place-items:center;
  font-family:Spectral,serif;font-weight:700;font-size:13px;line-height:1;
}
.mark b{font-family:Spectral,serif;font-size:15px;font-weight:600;letter-spacing:.01em}
.crumbs{display:flex;align-items:baseline;gap:7px;min-width:0;flex:1}
.crumbs .v{font-weight:600;font-size:13.5px;white-space:nowrap}
.crumbs .s{color:var(--topbar-ink-2);font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.topmeta{display:flex;align-items:center;gap:14px;font-size:11.5px;color:var(--topbar-ink-2);white-space:nowrap}
.topmeta b{color:var(--topbar-ink);font-weight:500}
.badge{
  border:1px solid var(--stamp);color:#F1A7AF;padding:2.5px 8px;font-size:10px;
  letter-spacing:.1em;text-transform:uppercase;font-weight:600;white-space:nowrap;
}
.iconbtn{
  appearance:none;background:transparent;border:1px solid var(--topbar-rule);color:var(--topbar-ink-2);
  width:26px;height:26px;display:grid;place-items:center;cursor:pointer;padding:0;
}
.iconbtn:hover{color:var(--topbar-ink);border-color:var(--topbar-ink-2)}
.railToggle,.closeDetail{display:none}

/* ---------------- rail ---------------- */
.block{padding:13px 14px;border-bottom:1px solid var(--rule-soft)}
.blocktitle{
  font-size:10px;letter-spacing:.13em;text-transform:uppercase;color:var(--ink-3);
  font-weight:600;margin:0 0 9px;display:flex;justify-content:space-between;align-items:baseline;
}
.bignum{display:flex;align-items:baseline;gap:5px}
.bignum b{font-family:Spectral,serif;font-size:46px;line-height:.85;font-weight:700;color:var(--accent);font-variant-numeric:tabular-nums;letter-spacing:-.02em}
.bignum span{font-family:Spectral,serif;font-size:19px;color:var(--accent);font-weight:600}
.bignum em{margin-left:auto;font-style:normal;font-size:11px;color:var(--ink-3);text-align:right;line-height:1.35}
.hint{font-size:11.5px;color:var(--ink-3);margin:7px 0 0;line-height:1.45}

.lrow{display:grid;grid-template-columns:74px 1fr 34px;gap:8px;align-items:center;margin-bottom:7px}
.lrow .n{font-size:11.5px;font-weight:600}
.lrow .p{text-align:right;font-size:11.5px;font-weight:600;font-variant-numeric:tabular-nums}
.bar{height:9px;background:var(--seq-0);position:relative;overflow:hidden}
.bar i{position:absolute;inset:0 auto 0 0;background:var(--accent);transition:width .7s cubic-bezier(.2,.7,.3,1)}
.lnote{font-size:10.5px;color:var(--ink-3);margin:-4px 0 9px 82px;line-height:1.35}

.wrow{display:grid;grid-template-columns:1fr 52px 30px;gap:7px;align-items:center;padding:2.5px 0;font-size:11.5px}
.wrow .wn{color:var(--ink-2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.wrow .wp{text-align:right;color:var(--ink-3);font-size:11px;font-variant-numeric:tabular-nums}
.wrow.na .wn,.wrow.na .wp{opacity:.55;font-style:italic}
.wrow.na .bar{background:repeating-linear-gradient(45deg,var(--rule-soft) 0 3px,transparent 3px 6px)}
.wrow.zero .bar i{background:var(--certain);opacity:.5}

/* ---------------- centre ---------------- */
.toolbar{display:flex;align-items:center;gap:7px;padding:8px 12px;border-bottom:1px solid var(--rule);background:var(--surface-2);flex-wrap:wrap}
.search{position:relative;flex:1;min-width:150px}
.search input{
  width:100%;appearance:none;background:var(--surface);border:1px solid var(--rule);
  padding:5px 26px 5px 27px;font:inherit;font-size:12.5px;color:var(--ink);
}
.search input::placeholder{color:var(--ink-3)}
.search svg{position:absolute;left:8px;top:50%;transform:translateY(-50%);color:var(--ink-3)}
.search kbd{
  position:absolute;right:7px;top:50%;transform:translateY(-50%);font:inherit;font-size:10px;
  color:var(--ink-3);border:1px solid var(--rule);padding:0 4px;font-family:"IBM Plex Mono",monospace;
}
.seg{display:flex;border:1px solid var(--rule);background:var(--surface)}
.seg button{
  appearance:none;background:transparent;border:0;border-right:1px solid var(--rule);
  padding:5px 9px;font-size:11.5px;cursor:pointer;color:var(--ink-3);display:flex;align-items:center;gap:5px;
}
.seg button:last-child{border-right:0}
.seg button[aria-pressed="true"]{background:var(--surface-3);color:var(--ink);font-weight:600}
.seg button i{width:7px;height:7px;border-radius:50%;display:block}
.seg button .c{font-variant-numeric:tabular-nums;font-size:11px;opacity:.75}

.strip{display:flex;gap:1.5px;padding:8px 12px;border-bottom:1px solid var(--rule);background:var(--surface-2);flex-wrap:wrap;align-content:flex-start}
.striplabel{
  width:100%;font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3);
  font-weight:600;margin-bottom:6px;display:flex;justify-content:space-between;
}
.pc{
  height:26px;min-width:15px;border:1px solid transparent;cursor:pointer;position:relative;
  transition:transform .1s ease;
}
.pc:hover{transform:translateY(-2px);z-index:3}
.pc.err{box-shadow:inset 0 0 0 1.5px var(--certain);border-color:var(--certain)}
.pc.on{outline:2px solid var(--ink);outline-offset:1px;z-index:4}

.tablehead{
  display:grid;grid-template-columns:3px 104px 132px minmax(118px,1fr) minmax(190px,1.7fr) 148px;
  gap:10px;padding:7px 12px 7px 0;border-bottom:1px solid var(--rule);background:var(--surface-2);
  font-size:9.5px;letter-spacing:.11em;text-transform:uppercase;color:var(--ink-3);font-weight:600;
}
.tablehead>span:last-child{text-align:right}
.rows{min-height:0}
.r{
  display:grid;grid-template-columns:3px 104px 132px minmax(118px,1fr) minmax(190px,1.7fr) 148px;
  gap:10px;padding:0 12px 0 0;border-bottom:1px solid var(--rule-soft);cursor:pointer;
  align-items:center;min-height:38px;
}
.r:hover{background:var(--surface-2)}
.r.sel{background:var(--sel)}
.r .edge{align-self:stretch}
.r .cls{font-size:11.5px;color:var(--ink-2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.r .rec{font-weight:600;font-size:12.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.r .msg{color:var(--ink-2);font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.r .stk{text-align:right;font-size:11.5px;white-space:nowrap;color:var(--ink-2);overflow:hidden;text-overflow:ellipsis}
.pill{
  display:inline-flex;align-items:center;gap:5px;padding:1px 7px;font-size:10px;font-weight:600;
  letter-spacing:.04em;white-space:nowrap;border:1px solid;text-transform:uppercase;
}
.pill i{width:6px;height:6px;border-radius:50%;display:block;flex:0 0 6px}
.k-certain_error{color:var(--certain);border-color:var(--certain);background:var(--certain-wash)}
.k-certain_error i{background:var(--certain)}
.k-unverifiable{color:var(--unverif);border-color:var(--unverif);background:var(--unverif-wash)}
.k-unverifiable i{background:var(--unverif)}
.k-conflict{color:var(--conflict);border-color:var(--conflict);background:var(--conflict-wash)}
.k-conflict i{background:var(--conflict)}
.k-anomaly{color:var(--anomaly);border-color:var(--anomaly);background:var(--anomaly-wash)}
.k-anomaly i{background:var(--anomaly)}
.empty{padding:40px 16px;text-align:center;color:var(--ink-3);font-size:12.5px}

/* ---------------- detail ---------------- */
.dhead{padding:12px 14px;border-bottom:1px solid var(--rule);background:var(--surface-2);display:flex;gap:10px;align-items:flex-start}
.dhead h2{margin:6px 0 0;font-family:Spectral,serif;font-size:16px;font-weight:600;line-height:1.3}
.drule{font-size:11px;color:var(--ink-3);margin-top:4px}
.dsec{padding:12px 14px;border-bottom:1px solid var(--rule-soft)}
.dsec h3{
  margin:0 0 8px;font-size:9.5px;letter-spacing:.13em;text-transform:uppercase;
  color:var(--ink-3);font-weight:600;
}
.kv{display:grid;grid-template-columns:auto minmax(0,1fr);gap:5px 12px;font-size:12px;align-items:baseline}
.kv dt{color:var(--ink-3);white-space:nowrap;font-size:11px}
.kv dd{margin:0;word-break:break-word}
.subj{display:flex;flex-direction:column;gap:5px}
.subj a{
  display:flex;justify-content:space-between;gap:8px;padding:6px 9px;background:var(--surface-2);
  border:1px solid var(--rule-soft);text-decoration:none;color:var(--ink);font-size:12px;cursor:pointer;
}
.subj a:hover{border-color:var(--rule);background:var(--surface-3)}
.subj .t{color:var(--ink-3);font-size:10.5px;text-transform:uppercase;letter-spacing:.08em}
.wtag{display:inline-flex;align-items:center;gap:5px;font-size:11px;padding:2px 7px;border:1px solid var(--rule-soft);margin:0 4px 4px 0;background:var(--surface-2)}
.wtag i{width:6px;height:6px;border-radius:50%;background:var(--accent)}
.wtag.off{color:var(--ink-3)}.wtag.off i{background:var(--certain);opacity:.55}
.wtag.na{color:var(--ink-3);opacity:.6;font-style:italic}.wtag.na i{background:var(--rule)}
.blank{padding:44px 18px;text-align:center;color:var(--ink-3);font-size:12.5px;line-height:1.6}
.blank b{display:block;color:var(--ink-2);font-weight:600;margin-bottom:5px;font-size:13px}

/* ---------------- statusbar ---------------- */
.statusbar{
  background:var(--surface);border-top:1px solid var(--rule);display:flex;align-items:center;
  gap:14px;padding:0 12px;font-size:11px;color:var(--ink-3);white-space:nowrap;overflow:hidden;
}
.statusbar b{color:var(--ink-2);font-weight:600;font-variant-numeric:tabular-nums}
.statusbar .sp{margin-left:auto;display:flex;gap:12px;align-items:center}
.statusbar kbd{
  font-family:"IBM Plex Mono",monospace;border:1px solid var(--rule);padding:0 3px;font-size:10px;
}
.dot{width:6px;height:6px;border-radius:50%;display:inline-block;margin-right:4px}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
</style>
</head>
<body>
<div class="app">

  <header class="topbar">
    <button class="iconbtn railToggle" id="railToggle" aria-label="Toggle summary panel">&#9776;</button>
    <div class="mark"><div class="glyph">&#2325;</div><b>Kavach</b></div>
    <div class="crumbs">
      <span class="v" id="cVillage"></span>
      <span class="s" id="cWhere"></span>
    </div>
    <div class="topmeta">
      <span>as of <b id="cAsOf"></b></span>
      <span>ladder <b class="mono" id="cLadder"></b></span>
      <span class="badge" id="cBadge"></span>
      <button class="iconbtn" id="themeBtn" aria-label="Switch theme" title="Switch theme">&#9681;</button>
    </div>
  </header>

  <div class="work">

    <aside class="pane scroll" id="rail">
      <div class="block">
        <p class="blocktitle">Verifiability <span>Class 8</span></p>
        <div class="bignum"><b id="vNum">—</b><span>%</span><em id="vExact"></em></div>
        <p class="hint">A rate, not an error rate — the share of checks that have a
           witness at all, against twelve named witnesses per parcel.</p>
      </div>
      <div class="block">
        <p class="blocktitle">By record lineage</p>
        <div id="lineage"></div>
      </div>
      <div class="block" style="border-bottom:0">
        <p class="blocktitle">Witness coverage</p>
        <div id="witness"></div>
      </div>
    </aside>

    <section class="pane" id="centre">
      <div class="toolbar">
        <label class="search">
          <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6">
            <circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5L14 14"/>
          </svg>
          <input id="q" type="search" placeholder="Filter by rule, record or message" autocomplete="off">
          <kbd>/</kbd>
        </label>
        <div class="seg" id="classFilter"></div>
        <button class="seg" id="clearBtn" style="padding:5px 9px;font-size:11.5px;cursor:pointer;background:var(--surface)">Reset</button>
      </div>

      <div class="strip" id="strip">
        <div class="striplabel"><span>Verifiability map — parcels sized by area</span><span id="stripMeta"></span></div>
      </div>

      <div class="tablehead">
        <span></span><span>Finding</span><span>Class</span><span>Record</span>
        <span>What the rule says</span><span>Land at stake</span>
      </div>
      <div class="scroll rows" id="rows" tabindex="0" role="listbox" aria-label="Review queue"></div>
    </section>

    <aside class="pane scroll" id="detail"></aside>
  </div>

  <footer class="statusbar">
    <span><span class="dot" style="background:var(--certain)"></span><b id="sErr">0</b> certain errors</span>
    <span><span class="dot" style="background:var(--unverif)"></span><b id="sUnv">0</b> unverifiable</span>
    <span><b id="sParcels">0</b> parcels · <b id="sKhatas">0</b> khatas</span>
    <span><b id="sRules">0</b> rules ran</span>
    <span class="sp">
      <span id="sShown"></span>
      <span><kbd>&#8593;</kbd><kbd>&#8595;</kbd> move</span>
      <span><kbd>/</kbd> search</span>
      <span><kbd>esc</kbd> clear</span>
    </span>
  </footer>
</div>

<script id="payload" type="application/json">__PAYLOAD__</script>
<script>
(function(){
  "use strict";
  var D = JSON.parse(document.getElementById("payload").textContent);
  var $ = function(id){ return document.getElementById(id); };
  var esc = function(s){
    return String(s == null ? "" : s).replace(/[&<>"']/g, function(c){
      return {"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c];
    });
  };
  var LABEL = {certain_error:"Certain error", conflict:"Conflict",
               anomaly:"Anomaly", unverifiable:"Unverifiable"};
  var VAR = {certain_error:"--certain", conflict:"--conflict",
             anomaly:"--anomaly", unverifiable:"--unverif"};
  var ORDER = ["certain_error","conflict","anomaly","unverifiable"];

  var state = {sel:-1, q:"", classes:{}, parcel:null, view:[]};
  ORDER.forEach(function(c){ state.classes[c] = true; });

  /* ---- chrome ---- */
  var m = D.mouza;
  $("cVillage").textContent = m.name;
  $("cWhere").textContent = [m.subdistrict_term + " " + (m.subdistrict||"—"), m.district].join("  ·  ");
  $("cAsOf").textContent = m.as_of || "—";
  $("cLadder").textContent = m.ladder;
  $("cBadge").textContent = m.is_synthetic ? "Synthetic fixture" : "Live records";
  var T = D.totals;
  $("sErr").textContent = T.certain_errors;
  $("sUnv").textContent = T.unverifiable;
  $("sParcels").textContent = T.parcels;
  $("sKhatas").textContent = T.khatas;
  $("sRules").textContent = T.rules_ran + "/" + T.rules_registered;

  $("themeBtn").addEventListener("click", function(){
    var now = document.documentElement.getAttribute("data-theme");
    var dark = now ? now === "dark"
      : window.matchMedia("(prefers-color-scheme: dark)").matches;
    document.documentElement.setAttribute("data-theme", dark ? "light" : "dark");
  });
  $("railToggle").addEventListener("click", function(){ $("rail").classList.toggle("open"); });

  /* ---- rail ---- */
  var V = D.verifiability;
  $("vNum").textContent = V.percent == null ? "—" : V.percent;
  $("vExact").innerHTML = V.rate
    ? "<span class='mono'>" + esc(V.rate) + "</span><br>checks with a witness"
    : "";
  $("lineage").innerHTML = D.profiles.map(function(p){
    return '<div class="lrow"><span class="n">' + esc(p.profile) + "</span>" +
      '<span class="bar"><i style="width:0" data-w="' + p.percent + '"></i></span>' +
      '<span class="p">' + p.percent + "%</span></div>" +
      '<p class="lnote">' + esc(p.blurb) + "</p>";
  }).join("");
  $("witness").innerHTML = V.witnesses.map(function(w){
    if (w.percent === null){
      return '<div class="wrow na" title="' + esc(w.description) +
        ' — no parcel in this register has that shape"><span class="wn">' +
        esc(w.name.replace(/_/g," ")) + '</span><span class="bar"></span><span class="wp">n/a</span></div>';
    }
    return '<div class="wrow' + (w.percent === 0 ? " zero" : "") + '" title="' + esc(w.description) +
      '"><span class="wn">' + esc(w.name.replace(/_/g," ")) +
      '</span><span class="bar"><i style="width:0" data-w="' + w.percent +
      '"></i></span><span class="wp">' + w.percent + "%</span></div>";
  }).join("");
  requestAnimationFrame(function(){
    Array.prototype.forEach.call(document.querySelectorAll(".bar i"), function(el){
      el.style.width = el.getAttribute("data-w") + "%";
    });
  });

  /* ---- map strip ---- */
  var tone = function(p){
    return p>=90?5:p>=72?4:p>=54?3:p>=36?2:p>=18?1:0;
  };
  var biggest = Math.max.apply(null, D.parcels.map(function(p){ return p.area_units||1; }));
  var mapped = D.parcels.slice().sort(function(a,b){ return (b.area_units||0)-(a.area_units||0); });
  $("stripMeta").textContent = D.parcels.length + " parcels · click to filter";
  $("strip").insertAdjacentHTML("beforeend", mapped.map(function(p){
    var grow = Math.max(1, Math.round(100*(p.area_units||1)/biggest));
    return '<div class="pc' + (p.error_rows.length?" err":"") + '" data-p="' + esc(p.id) +
      '" style="background:var(--seq-' + tone(p.witness_percent) + ');flex:' + grow + ' 1 auto" ' +
      'title="' + esc(p.path) + " · " + esc(p.area||"no stated area") + " · " +
      p.witness_percent + "% witnesses" +
      (p.error_rows.length ? " · " + p.error_rows.length + " error(s)" : "") + '"></div>';
  }).join(""));

  /* ---- filters ---- */
  var counts = {};
  D.queue.forEach(function(r){ counts[r.finding_class] = (counts[r.finding_class]||0)+1; });
  $("classFilter").innerHTML = ORDER.filter(function(c){ return counts[c]; }).map(function(c){
    return '<button aria-pressed="true" data-c="' + c + '"><i style="background:var(' +
      VAR[c] + ')"></i>' + LABEL[c] + '<span class="c">' + counts[c] + "</span></button>";
  }).join("");

  /* ---- queue ---- */
  function matches(r){
    if (!state.classes[r.finding_class]) return false;
    if (state.parcel && r.parcel_ids.indexOf(state.parcel) < 0) return false;
    if (state.q){
      var hay = (r.rule_id + " " + r.primary + " " + r.message + " " + r.class_title).toLowerCase();
      if (hay.indexOf(state.q) < 0) return false;
    }
    return true;
  }
  function renderRows(){
    state.view = D.queue.map(function(r,i){ return {r:r,i:i}; }).filter(function(o){ return matches(o.r); });
    $("sShown").textContent = state.view.length + " of " + D.queue.length + " shown";
    if (!state.view.length){
      $("rows").innerHTML = '<p class="empty">No findings match this filter.</p>';
      return;
    }
    $("rows").innerHTML = state.view.map(function(o){
      var r = o.r;
      return '<div class="r' + (o.i===state.sel?" sel":"") + '" data-i="' + o.i +
        '" role="option" aria-selected="' + (o.i===state.sel) + '">' +
        '<span class="edge" style="background:var(' + VAR[r.finding_class] + ')"></span>' +
        '<span><span class="pill k-' + r.finding_class + '"><i></i>' + LABEL[r.finding_class] + "</span></span>" +
        '<span class="cls"><span class="mono">C' + r.validation_class + "</span> " + esc(r.class_title) + "</span>" +
        '<span class="rec">' + esc(r.primary) + "</span>" +
        '<span class="msg">' + esc(r.message) + "</span>" +
        '<span class="stk mono">' + esc(r.stake_display) + "</span></div>";
    }).join("");
  }

  function renderDetail(reveal){
    var el = $("detail");
    if (state.sel < 0 || !D.queue[state.sel]){
      el.innerHTML = '<div class="blank"><b>No finding selected</b>' +
        "Choose a row to see the rule that fired, the record that disagrees, and the exact evidence." +
        "</div>";
      el.classList.remove("open");
      return;
    }
    var r = D.queue[state.sel];
    var ev = Object.keys(r.evidence).map(function(k){
      return "<dt>" + esc(k.replace(/_/g," ")) + "</dt><dd class='mono'>" + esc(r.evidence[k]) + "</dd>";
    }).join("");
    if (r.missing_witness){
      ev = "<dt>missing witness</dt><dd class='mono'>" + esc(r.missing_witness) + "</dd>" + ev;
    }
    var parcels = r.parcel_ids.map(function(id){
      return D.parcels.filter(function(p){ return p.id === id; })[0];
    }).filter(Boolean);
    var ctx = parcels.map(function(p){
      return '<div class="dsec"><h3>Parcel ' + esc(p.path) + "</h3>" +
        "<dl class='kv'><dt>area</dt><dd class='mono'>" + esc(p.area||"—") + "</dd>" +
        "<dt>as written</dt><dd class='mono'>" + esc(p.as_written||"—") + "</dd>" +
        "<dt>held by</dt><dd class='mono'>" + esc(p.holders.join(", ")||"—") + "</dd>" +
        "<dt>witnesses</dt><dd>" + p.witness_percent + "%</dd></dl>" +
        "<div style='margin-top:8px'>" +
        p.witnesses_present.map(function(w){ return "<span class='wtag'><i></i>" + esc(w.replace(/_/g," ")) + "</span>"; }).join("") +
        p.witnesses_absent.map(function(w){ return "<span class='wtag off'><i></i>" + esc(w.replace(/_/g," ")) + "</span>"; }).join("") +
        p.witnesses_na.map(function(w){ return "<span class='wtag na'><i></i>" + esc(w.replace(/_/g," ")) + "</span>"; }).join("") +
        "</div></div>";
    }).join("");

    el.innerHTML =
      '<div class="dhead"><div style="flex:1">' +
        '<span class="pill k-' + r.finding_class + '"><i></i>' + LABEL[r.finding_class] + "</span>" +
        "<h2>" + esc(r.message) + "</h2>" +
        '<p class="drule mono">' + esc(r.rule_id) + " · class " + r.validation_class +
        " " + esc(r.class_title) + "</p></div>" +
        '<button class="iconbtn closeDetail" id="closeDetail" aria-label="Close">&times;</button></div>' +
      (ev ? '<div class="dsec"><h3>Evidence</h3><dl class="kv">' + ev + "</dl></div>" : "") +
      '<div class="dsec"><h3>Records named</h3><div class="subj">' +
        r.subjects.map(function(s){
          return "<a data-goto='" + esc(s.id) + "'><span>" + esc(s.label) +
            (s.field ? " <span style='color:var(--ink-3)'>· " + esc(s.field) + "</span>" : "") +
            "</span><span class='t'>" + esc(s.type) + "</span></a>";
        }).join("") +
      "</div></div>" +
      '<div class="dsec"><h3>Consequence</h3><dl class="kv">' +
        "<dt>land at stake</dt><dd class='mono'>" + esc(r.stake_display) + "</dd></dl>" +
        "<p class='hint'>Queue order is severity, then land at stake. Never ascending " +
        "confidence — the uncertainty term needs a calibrated model this phase does not have.</p></div>" +
      ctx;
    /* On a wide screen the detail pane is always there and `open` is inert. On a
       narrow one it is an overlay over the table, so it may only appear when the
       reviewer actually picked something — never on load. */
    if (reveal) el.classList.add("open");
    var cd = $("closeDetail");
    if (cd) cd.addEventListener("click", function(){ el.classList.remove("open"); });
  }

  function select(i, scroll, reveal){
    state.sel = i;
    renderRows();
    renderDetail(reveal !== false);
    if (scroll){
      var node = $("rows").querySelector('.r[data-i="' + i + '"]');
      if (node) node.scrollIntoView({block:"nearest"});
    }
  }

  /* ---- events ---- */
  $("rows").addEventListener("click", function(e){
    var row = e.target.closest(".r");
    if (row) select(parseInt(row.getAttribute("data-i"), 10), false, true);
  });
  $("classFilter").addEventListener("click", function(e){
    var b = e.target.closest("button");
    if (!b) return;
    var c = b.getAttribute("data-c");
    state.classes[c] = !state.classes[c];
    b.setAttribute("aria-pressed", String(state.classes[c]));
    renderRows();
  });
  $("strip").addEventListener("click", function(e){
    var cell = e.target.closest(".pc");
    if (!cell) return;
    var id = cell.getAttribute("data-p");
    state.parcel = state.parcel === id ? null : id;
    Array.prototype.forEach.call(document.querySelectorAll(".pc"), function(n){
      n.classList.toggle("on", n.getAttribute("data-p") === state.parcel);
    });
    renderRows();
  });
  $("q").addEventListener("input", function(){
    state.q = this.value.trim().toLowerCase();
    renderRows();
  });
  $("clearBtn").addEventListener("click", function(){
    state.q = ""; state.parcel = null; state.sel = -1;
    $("q").value = "";
    ORDER.forEach(function(c){ state.classes[c] = true; });
    Array.prototype.forEach.call(document.querySelectorAll("#classFilter button"), function(b){
      b.setAttribute("aria-pressed", "true");
    });
    Array.prototype.forEach.call(document.querySelectorAll(".pc"), function(n){ n.classList.remove("on"); });
    renderRows(); renderDetail(false);
  });
  document.addEventListener("click", function(e){
    var go = e.target.closest("[data-goto]");
    if (!go) return;
    var id = go.getAttribute("data-goto");
    var hit = D.parcels.filter(function(p){ return p.id === id; })[0];
    if (!hit) return;
    state.parcel = id;
    Array.prototype.forEach.call(document.querySelectorAll(".pc"), function(n){
      n.classList.toggle("on", n.getAttribute("data-p") === id);
    });
    renderRows();
  });
  document.addEventListener("keydown", function(e){
    if (e.key === "/" && document.activeElement !== $("q")){
      e.preventDefault(); $("q").focus(); $("q").select(); return;
    }
    if (e.key === "Escape"){ $("clearBtn").click(); $("q").blur(); return; }
    if (document.activeElement === $("q")) return;
    var down = e.key === "ArrowDown" || e.key === "j";
    var up = e.key === "ArrowUp" || e.key === "k";
    if (!down && !up) return;
    e.preventDefault();
    var order = state.view.map(function(o){ return o.i; });
    if (!order.length) return;
    var at = order.indexOf(state.sel);
    var next = down ? (at < 0 ? 0 : Math.min(at+1, order.length-1))
                    : (at < 0 ? order.length-1 : Math.max(at-1, 0));
    select(order[next], true, true);
  });

  renderRows();
  /* A review queue opens on its first item. An empty detail pane on load is a
     document waiting to be read, not a tool ready to be worked. */
  if (state.view.length) select(state.view[0].i, false, false);
  else renderDetail(false);
})();
</script>
</body>
</html>
"""


def render(payload: dict) -> str:
    """One self-contained page. The payload is embedded, so it opens offline."""
    embedded = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    return _TEMPLATE.replace("__PAYLOAD__", embedded)


def render_fragment(payload: dict) -> str:
    """The same page without the document skeleton, for hosts that supply their own.

    Keeps the title, the font link, the stylesheet and the body content; drops
    doctype, html, head and body tags.
    """
    full = render(payload)
    head_open = full.index("<title>")
    head_close = full.index("</head>")
    body_open = full.index("<body>") + len("<body>")
    body_close = full.rindex("</body>")
    head = full[head_open:head_close].strip()
    body = full[body_open:body_close].strip()
    return head + "\n" + body + "\n"


DEMO_DEFECTS = (
    "khata_number_zero",
    "one_unit_added_to_parcel",
    "sequence_gap_renumbered",
    "holding_orphaned",
    "identifier_charset_corrupted",
)
"""Several independent defects, as a real register carries.

The mutation harness applies exactly one corruption at a time, because that is what
lets it measure localisation. A demonstration register is a different job: a real
village has more than one thing wrong with it at once, and each of these is grounded
in a document — EVIDENCE.md E5 measures zero and blank identifiers at around six
percent of Bihar RoRs.

The profile is `jamabandi` on purpose. It is the de facto record of rights, it states
no shares and no classification, and roughly half of what the engine could check has
no witness in it. Demonstrating on the reconciled `combined` profile would show a
verifiability rate the real register does not have.
"""


def demo_register(registry=None):
    """The register the dashboard opens on. Synthetic, and labelled as such."""
    registry = registry or default_registry()
    records = synthetic_mouza(MouzaSpec(seed=11, profile=DocumentProfile.JAMABANDI))
    for defect in DEMO_DEFECTS:
        records = apply_mutation(defect, records, registry, seed=3).mutated
    return records


def write(records: RecordSet | None = None, path: Path | None = None) -> Path:
    registry = default_registry()
    schemes = default_schemes()
    if records is None:
        records = demo_register(registry)
    payload = build_payload(records, registry=registry, schemes=schemes)
    target = path or OUTPUT_PATH
    target.write_text(render(payload), encoding="utf-8")
    return target


def main() -> int:
    target = write()
    print(f"wrote {target} ({target.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
