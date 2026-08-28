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

__all__ = ["DEMO_DEFECTS", "demo_register", "render", "write"]

OUTPUT_PATH = Path(__file__).resolve().parents[1].joinpath("dashboard.html")

_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Kavach Register Review</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Spectral:wght@400;600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
/* ---------- tokens: complete light palette on bare :root ---------- */
:root{
  --ink:#0F2A44; --ink-2:#44586A; --ink-3:#6B7C8C;
  --ground:#EEF2F5; --surface:#FFFFFF; --surface-2:#F7F9FA;
  --rule:#C6D2DC; --rule-soft:#E1E8ED;
  --accent:#10716C; --accent-ink:#0B564F;
  --certain:#B02133; --conflict:#A8790A; --anomaly:#6D4CA0; --unverif:#068276;
  --certain-wash:#FBECEE; --conflict-wash:#FAF3E2; --anomaly-wash:#F2EDF9; --unverif-wash:#E6F2F0;
  --seq-0:#E9F0EF; --seq-1:#C2DAD6; --seq-2:#8FBDB6; --seq-3:#57998F; --seq-4:#2A7C71; --seq-5:#0E5F55;
  --stamp:#8A2B36;
  --shadow:0 1px 2px rgba(15,42,68,.06), 0 8px 24px -16px rgba(15,42,68,.28);
  --edge:1px solid var(--rule-soft);
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --ink:#E7EDF2; --ink-2:#A8B8C6; --ink-3:#7E8FA0;
    --ground:#0D1620; --surface:#131F2B; --surface-2:#17242F;
    --rule:#2C3D4C; --rule-soft:#22313E;
    --accent:#3DAFA4; --accent-ink:#7FCFC6;
    --certain:#DA5C70; --conflict:#AE821A; --anomaly:#9A7BCC; --unverif:#2AA795;
    --certain-wash:#2A1720; --conflict-wash:#241D10; --anomaly-wash:#1F1A2B; --unverif-wash:#0F2622;
    --seq-0:#17242F; --seq-1:#1D3A38; --seq-2:#245049; --seq-3:#2C685E; --seq-4:#358274; --seq-5:#46A091;
    --stamp:#D9707C;
    --shadow:0 1px 2px rgba(0,0,0,.4), 0 10px 30px -18px rgba(0,0,0,.8);
  }
}
:root[data-theme="dark"]{
  --ink:#E7EDF2; --ink-2:#A8B8C6; --ink-3:#7E8FA0;
  --ground:#0D1620; --surface:#131F2B; --surface-2:#17242F;
  --rule:#2C3D4C; --rule-soft:#22313E;
  --accent:#3DAFA4; --accent-ink:#7FCFC6;
  --certain:#DA5C70; --conflict:#AE821A; --anomaly:#9A7BCC; --unverif:#2AA795;
  --certain-wash:#2A1720; --conflict-wash:#241D10; --anomaly-wash:#1F1A2B; --unverif-wash:#0F2622;
  --seq-0:#17242F; --seq-1:#1D3A38; --seq-2:#245049; --seq-3:#2C685E; --seq-4:#358274; --seq-5:#46A091;
  --stamp:#D9707C;
  --shadow:0 1px 2px rgba(0,0,0,.4), 0 10px 30px -18px rgba(0,0,0,.8);
}

*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{
  margin:0; background:var(--ground); color:var(--ink);
  font-family:"IBM Plex Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  font-size:15px; line-height:1.55; -webkit-font-smoothing:antialiased;
}
.mono{font-family:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace;font-variant-numeric:tabular-nums}
.wrap{max-width:1240px;margin:0 auto;padding:0 28px}
h1,h2,h3{font-family:Spectral,Georgia,"Times New Roman",serif;font-weight:600;text-wrap:balance;margin:0}
.eyebrow{
  font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-3);
  font-weight:600;
}
a{color:var(--accent-ink)}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:2px}

/* ---------- masthead: the register cover ---------- */
.masthead{
  background:var(--surface); border-bottom:2px solid var(--ink);
  position:relative; overflow:hidden;
}
.masthead::after{
  content:""; position:absolute; inset:auto 0 0 0; height:3px;
  background:linear-gradient(90deg,var(--accent) 0 22%,var(--rule) 22% 100%);
}
.masthead-inner{display:flex;flex-wrap:wrap;gap:28px;align-items:flex-end;justify-content:space-between;padding:26px 0 22px}
.brand{display:flex;gap:14px;align-items:flex-start}
.crest{
  width:38px;height:38px;flex:0 0 38px;border:1.5px solid var(--ink);
  display:grid;place-items:center;margin-top:3px;
}
.crest span{font-family:Spectral,serif;font-weight:700;font-size:19px;line-height:1;color:var(--ink)}
.brand h1{font-size:25px;letter-spacing:-.01em;line-height:1.15}
.brand p{margin:3px 0 0;font-size:13px;color:var(--ink-2);max-width:58ch;line-height:1.5}
.ident{display:flex;flex-wrap:wrap;gap:0;border:var(--edge);background:var(--surface-2)}
.ident div{padding:9px 16px;border-right:var(--edge)}
.ident div:last-child{border-right:0}
.ident dt{margin:0;font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3);font-weight:600}
.ident dd{margin:2px 0 0;font-size:14px;font-weight:500}
.stamp{
  border:1.5px solid var(--stamp); color:var(--stamp); padding:5px 11px;
  font-size:10.5px;letter-spacing:.13em;text-transform:uppercase;font-weight:600;
  transform:rotate(-1.4deg); align-self:center; white-space:nowrap;
}

/* ---------- trial balance strip ---------- */
.balance{display:grid;grid-template-columns:repeat(auto-fit,minmax(168px,1fr));border:var(--edge);background:var(--surface);margin:26px 0 0}
.cell{padding:16px 18px;border-right:var(--edge);position:relative;display:flex;flex-direction:column;gap:3px}
.cell:last-child{border-right:0}
.cell .fig{font-family:Spectral,serif;font-size:32px;line-height:1;font-weight:600;font-variant-numeric:tabular-nums}
.cell .lab{font-size:12px;color:var(--ink-2)}
.cell.k-certain{background:var(--certain-wash)} .cell.k-certain .fig{color:var(--certain)}
.cell.k-unverif{background:var(--unverif-wash)} .cell.k-unverif .fig{color:var(--unverif)}
.cell.k-conflict .fig{color:var(--conflict)}
.cell.k-anomaly .fig{color:var(--anomaly)}
.cell .edge{position:absolute;left:0;top:0;bottom:0;width:3px}
.cell.k-certain .edge{background:var(--certain)}
.cell.k-unverif .edge{background:var(--unverif)}

/* ---------- panels ---------- */
.panels{display:grid;grid-template-columns:minmax(0,7fr) minmax(0,9fr);gap:20px;margin-top:20px}
@media (max-width:940px){.panels{grid-template-columns:1fr}}
.panel{background:var(--surface);border:var(--edge);box-shadow:var(--shadow)}
.panel-head{padding:15px 18px 13px;border-bottom:var(--edge);display:flex;justify-content:space-between;align-items:baseline;gap:12px}
.panel-head h2{font-size:16px}
.panel-body{padding:18px}

/* verifiability meter */
.rate{display:flex;align-items:baseline;gap:12px;margin-bottom:4px}
.rate .num{font-family:Spectral,serif;font-size:60px;line-height:.9;font-weight:700;color:var(--accent);font-variant-numeric:tabular-nums;letter-spacing:-.02em}
.rate .pct{font-family:Spectral,serif;font-size:26px;color:var(--accent);font-weight:600}
.rate .exact{font-size:12px;color:var(--ink-3);margin-left:auto;text-align:right}
.note{font-size:12.5px;color:var(--ink-2);margin:8px 0 16px;max-width:52ch}
.witness{display:flex;flex-direction:column;gap:7px}
.wrow{display:grid;grid-template-columns:1fr 74px 40px;gap:10px;align-items:center;font-size:12.5px}
.wrow .wname{color:var(--ink-2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.wbar{height:7px;background:var(--seq-0);position:relative;overflow:hidden}
.wbar i{position:absolute;inset:0 auto 0 0;background:var(--accent);border-radius:0 2px 2px 0;transition:width .7s cubic-bezier(.2,.7,.3,1)}
.wrow .wpct{text-align:right;color:var(--ink-3);font-size:11.5px}
.wrow.na .wname,.wrow.na .wpct{color:var(--ink-3);opacity:.65;font-style:italic}
.wrow.na .wbar{background:repeating-linear-gradient(45deg,var(--rule-soft) 0 3px,transparent 3px 6px)}

/* parcel map — cells sized by land area, shaded by witness coverage */
.map{display:flex;flex-wrap:wrap;gap:2px;align-content:flex-start}
.pcell{
  height:52px;border:1px solid transparent;position:relative;cursor:default;
  min-width:58px;
  display:grid;place-items:center;font-size:9.5px;overflow:hidden;
  font-family:"IBM Plex Mono",monospace;color:var(--ink-3);
  transition:transform .12s ease, box-shadow .12s ease, outline-color .12s ease;
  outline:0 solid transparent;
}
.pcell:hover,.pcell:focus-visible{transform:translateY(-2px);z-index:5;box-shadow:var(--shadow)}
.pcell.flagged{border-color:var(--certain);box-shadow:inset 0 0 0 1.5px var(--certain)}
.pcell.dark-fill{color:#EAF2F0}

/* lineage comparison */
.lineage{display:flex;flex-direction:column;gap:11px;margin-top:18px;padding-top:16px;border-top:1px dashed var(--rule)}
.lrow{display:grid;grid-template-columns:96px 1fr 58px;gap:11px;align-items:center}
.lrow .lname{font-size:12.5px;font-weight:600}
.lrow .lbar{height:11px;background:var(--seq-0);position:relative;overflow:hidden}
.lrow .lbar i{position:absolute;inset:0 auto 0 0;background:var(--accent);border-radius:0 2px 2px 0;transition:width .8s cubic-bezier(.2,.7,.3,1)}
.lrow .lpct{text-align:right;font-size:13px;font-weight:600;font-variant-numeric:tabular-nums}
.lblurb{grid-column:2 / span 2;font-size:11.5px;color:var(--ink-3);margin-top:-6px}
.legend{display:flex;align-items:center;gap:8px;margin-top:14px;font-size:11.5px;color:var(--ink-3);flex-wrap:wrap}
.ramp{display:flex;gap:2px}
.ramp i{width:19px;height:9px;display:block}

/* ---------- tabs + table ---------- */
.tabs{display:flex;gap:0;margin:24px 0 0;border-bottom:1px solid var(--rule)}
.tab{
  appearance:none;background:none;border:0;border-bottom:2px solid transparent;
  padding:10px 16px;font:inherit;font-size:13.5px;font-weight:500;color:var(--ink-2);cursor:pointer;
}
.tab[aria-selected="true"]{color:var(--ink);border-bottom-color:var(--accent);font-weight:600}
.tab:hover{color:var(--ink)}
.filters{display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:14px 0}
.chip{
  appearance:none;border:1px solid var(--rule);background:var(--surface);color:var(--ink-2);
  padding:5px 11px;font:inherit;font-size:12px;cursor:pointer;display:inline-flex;gap:7px;align-items:center;
}
.chip[aria-pressed="true"]{border-color:var(--ink);color:var(--ink);background:var(--surface-2);font-weight:500}
.chip i{width:8px;height:8px;border-radius:50%;display:block}
.tablewrap{overflow-x:auto;background:var(--surface);border:var(--edge);box-shadow:var(--shadow)}
table{width:100%;border-collapse:collapse;font-size:13.5px}
thead th{
  text-align:left;font-size:10.5px;letter-spacing:.11em;text-transform:uppercase;color:var(--ink-3);
  font-weight:600;padding:11px 14px;border-bottom:1px solid var(--rule);white-space:nowrap;background:var(--surface-2);
}
tbody tr{border-bottom:1px solid var(--rule-soft)}
tbody tr.row{cursor:pointer}
tbody tr.row:hover{background:var(--surface-2)}
td{padding:11px 14px;vertical-align:top}
td.sev{padding:0;width:3px}
td.sev i{display:block;width:3px;height:100%;min-height:44px}
.pill{
  display:inline-flex;align-items:center;gap:6px;padding:2px 9px;
  font-size:11px;font-weight:600;letter-spacing:.04em;white-space:nowrap;border:1px solid;
}
.pill i{width:7px;height:7px;border-radius:50%;display:block;flex:0 0 7px}
.p-certain{color:var(--certain);border-color:var(--certain);background:var(--certain-wash)}
.p-certain i{background:var(--certain)}
.p-unverifiable{color:var(--unverif);border-color:var(--unverif);background:var(--unverif-wash)}
.p-unverifiable i{background:var(--unverif)}
.p-conflict{color:var(--conflict);border-color:var(--conflict);background:var(--conflict-wash)}
.p-conflict i{background:var(--conflict)}
.p-anomaly{color:var(--anomaly);border-color:var(--anomaly);background:var(--anomaly-wash)}
.p-anomaly i{background:var(--anomaly)}
.subj{font-weight:600}
.msg{color:var(--ink-2);max-width:52ch}
.stake{text-align:right;white-space:nowrap}
.detail td{background:var(--surface-2);padding:0 14px 16px}
.evidence{display:grid;grid-template-columns:auto 1fr;gap:2px 20px;font-size:12.5px;padding-top:12px;border-top:1px dashed var(--rule)}
.evidence dt{color:var(--ink-3);font-size:11px;letter-spacing:.06em;text-transform:uppercase;font-weight:600;padding-top:3px}
.evidence dd{margin:0}
.caret{display:inline-block;width:9px;transition:transform .15s ease;color:var(--ink-3)}
tr.open .caret{transform:rotate(90deg)}
.empty{padding:34px 18px;text-align:center;color:var(--ink-3);font-size:13.5px}
.hidden{display:none}
footer{padding:34px 0 46px;color:var(--ink-3);font-size:12.5px;line-height:1.7}
footer strong{color:var(--ink-2);font-weight:600}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
</style>
</head>
<body>
<header class="masthead">
  <div class="wrap masthead-inner">
    <div class="brand">
      <div class="crest"><span>क</span></div>
      <div>
        <h1>Kavach — Register Review</h1>
        <p>Every field cross-examined against other records of the same land.
           Findings are flags for review, never determinations of title.</p>
      </div>
    </div>
    <div style="display:flex;gap:16px;align-items:center;flex-wrap:wrap">
      <div class="ident" id="ident"></div>
      <div class="stamp" id="stamp"></div>
    </div>
  </div>
</header>

<main class="wrap">
  <section class="balance" id="balance" aria-label="Findings by class"></section>

  <section class="panels">
    <div class="panel">
      <div class="panel-head">
        <h2>Verifiability</h2>
        <span class="eyebrow">Class 8</span>
      </div>
      <div class="panel-body">
        <div class="rate">
          <span class="num" id="rateNum">—</span><span class="pct">%</span>
          <span class="exact" id="rateExact"></span>
        </div>
        <p class="note">A rate, not an error rate. The share of checks that have a
           witness at all, against twelve named witnesses per parcel.</p>
        <div class="witness" id="witness"></div>
      </div>
    </div>

    <div class="panel">
      <div class="panel-head">
        <h2>Verifiability map</h2>
        <span class="eyebrow" id="mapCount"></span>
      </div>
      <div class="panel-body">
        <div class="map" id="map" role="list"></div>
        <div class="lineage" id="lineage"></div>
        <div class="legend">
          <span>Fewer witnesses</span>
          <span class="ramp"><i style="background:var(--seq-0)"></i><i style="background:var(--seq-1)"></i><i style="background:var(--seq-2)"></i><i style="background:var(--seq-3)"></i><i style="background:var(--seq-4)"></i><i style="background:var(--seq-5)"></i></span>
          <span>More</span>
          <span style="margin-left:10px;display:inline-flex;align-items:center;gap:6px">
            <i style="width:11px;height:11px;border:1.5px solid var(--certain);display:block"></i>
            has a certain error
          </span>
        </div>
      </div>
    </div>
  </section>

  <div class="tabs" role="tablist">
    <button class="tab" role="tab" aria-selected="true" data-view="queue">Review queue</button>
    <button class="tab" role="tab" aria-selected="false" data-view="parcels">Parcels</button>
    <button class="tab" role="tab" aria-selected="false" data-view="rules">Rules</button>
  </div>

  <section id="view-queue">
    <div class="filters" id="filters"></div>
    <div class="tablewrap">
      <table>
        <thead><tr>
          <th></th><th>Finding</th><th>Class</th><th>Record</th>
          <th>What the rule says</th><th class="stake">Land at stake</th>
        </tr></thead>
        <tbody id="queueBody"></tbody>
      </table>
    </div>
    <p class="note" style="margin-top:12px">
      Ordered by severity, then by land at stake — never by ascending confidence.
      The uncertainty half of “consequence × uncertainty” needs a calibrated model,
      which this phase does not have, so it is absent rather than invented.
    </p>
  </section>

  <section id="view-parcels" class="hidden">
    <div class="tablewrap" style="margin-top:14px">
      <table>
        <thead><tr>
          <th>Parcel</th><th>Area</th><th>As written</th><th>Tenure</th>
          <th>Held by</th><th>Witnesses</th><th>Findings</th>
        </tr></thead>
        <tbody id="parcelBody"></tbody>
      </table>
    </div>
  </section>

  <section id="view-rules" class="hidden">
    <div id="rulesBody" style="margin-top:14px;display:flex;flex-direction:column;gap:18px"></div>
  </section>

  <footer>
    <p><strong id="footSource"></strong></p>
    <p>Generated <span id="footTime"></span> · Classes 1, 2, 3 and 8 run here.
       Classes 4–7 are specified, have no bodies, and abstain naming the external
       record they lack.</p>
  </footer>
</main>

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
  var CLASSES = ["certain_error","conflict","anomaly","unverifiable"];
  var LABEL = {certain_error:"Certain error", conflict:"Conflict",
               anomaly:"Anomaly", unverifiable:"Unverifiable"};
  var VAR = {certain_error:"--certain", conflict:"--conflict",
             anomaly:"--anomaly", unverifiable:"--unverif"};

  /* ---- masthead ---- */
  var m = D.mouza;
  $("ident").innerHTML = [
    ["Village", m.name], [m.subdistrict_term, m.subdistrict || "—"],
    ["District", m.district], ["Records as of", m.as_of || "—"],
    ["Unit ladder", m.ladder]
  ].map(function(p){
    return "<div><dt>" + esc(p[0]) + "</dt><dd>" + esc(p[1]) + "</dd></div>";
  }).join("");
  $("stamp").textContent = m.is_synthetic ? "Synthetic fixture — not a real village" : "Live records";
  $("footSource").textContent = m.is_synthetic
    ? "Every figure on this page is computed from a synthetic fixture in which the invariants hold by construction. No number here is a measurement of any real corpus."
    : "Computed from " + m.source + ".";
  $("footTime").textContent = D.generated;

  /* ---- trial balance ---- */
  var T = D.totals;
  $("balance").innerHTML = [
    {k:"certain", n:T.certain_errors, l:"Certain errors", s:"grammar or conservation violated"},
    {k:"unverif", n:T.unverifiable, l:"Unverifiable", s:"no witness exists — not a pass"},
    {k:"conflict", n:T.conflicts, l:"Conflicts", s:"two witnesses disagree"},
    {k:"plain", n:T.parcels, l:"Parcels", s:T.khatas + " khatas · " + T.owners + " owners"},
    {k:"plain", n:T.rules_ran, l:"Rules run", s:"of " + T.rules_registered + " registered"}
  ].map(function(c){
    return '<div class="cell k-' + c.k + '"><i class="edge"></i>' +
      '<span class="fig">' + c.n + '</span>' +
      '<span class="lab">' + esc(c.l) + '</span>' +
      '<span class="lab" style="color:var(--ink-3);font-size:11.5px">' + esc(c.s) + '</span></div>';
  }).join("");

  /* ---- verifiability ---- */
  var V = D.verifiability;
  $("rateNum").textContent = V.percent == null ? "—" : V.percent;
  $("rateExact").innerHTML = V.rate ? "exactly <span class='mono'>" + esc(V.rate) + "</span><br>" +
    V.unexaminable + " parcel(s) with no witness at all" : "";
  $("witness").innerHTML = V.witnesses.map(function(w){
    if (w.percent === null){
      return '<div class="wrow na" title="' + esc(w.description) +
        ' — no parcel in this register has that shape">' +
        '<span class="wname">' + esc(w.name.replace(/_/g, " ")) + "</span>" +
        '<span class="wbar"></span>' +
        '<span class="wpct">n/a</span></div>';
    }
    return '<div class="wrow" title="' + esc(w.description) + '">' +
      '<span class="wname">' + esc(w.name.replace(/_/g, " ")) + "</span>" +
      '<span class="wbar"><i style="width:0" data-w="' + w.percent + '"></i></span>' +
      '<span class="wpct">' + w.percent + "%</span></div>";
  }).join("");
  requestAnimationFrame(function(){
    Array.prototype.forEach.call(document.querySelectorAll(".wbar i"), function(el){
      el.style.width = el.getAttribute("data-w") + "%";
    });
  });

  /* ---- parcel map ---- */
  var step = function(pct){
    return pct >= 90 ? 5 : pct >= 72 ? 4 : pct >= 54 ? 3 : pct >= 36 ? 2 : pct >= 18 ? 1 : 0;
  };
  $("mapCount").textContent = D.parcels.length + " parcels, sized by area";
  var areas = D.parcels.map(function(p){ return p.area_units || 1; });
  var biggest = Math.max.apply(null, areas);
  $("map").innerHTML = D.parcels.slice().sort(function(a, b){
    return (b.area_units || 0) - (a.area_units || 0);
  }).map(function(p){
    /* A red ring means an error was found, never "this could not be checked".
       Abstention is carried by the fill tone, which is what it means. */
    var flagged = p.error_rows.length > 0;
    var units = p.area_units || 1;
    var grow = Math.max(1, Math.round(100 * units / biggest));
    var tone = step(p.witness_percent);
    return '<div role="listitem" tabindex="0" class="pcell' + (flagged ? " flagged" : "") +
      (tone >= 4 ? " dark-fill" : "") +
      '" style="background:var(--seq-' + tone + ');flex:' + grow + ' 1 auto"' +
      ' title="' + esc(p.path) + " · " + esc(p.area || "no stated area") +
      " · " + p.witness_percent + '% of witnesses present' +
      (p.error_rows.length ? " · " + p.error_rows.length + " error(s)" : "") +
      (p.finding_rows.length ? " · " + p.finding_rows.length + " finding(s)" : "") + '">' +
      (grow > 22 ? esc(p.path) : "") + "</div>";
  }).join("");

  /* lineage comparison — the gap that is the argument */
  $("lineage").innerHTML = D.profiles.map(function(p){
    return '<div class="lrow">' +
      '<span class="lname">' + esc(p.profile) + "</span>" +
      '<span class="lbar"><i style="width:0" data-w="' + p.percent + '"></i></span>' +
      '<span class="lpct">' + p.percent + "%</span>" +
      '<span class="lblurb">' + esc(p.blurb) + "</span></div>";
  }).join("");
  requestAnimationFrame(function(){
    Array.prototype.forEach.call(document.querySelectorAll(".lbar i"), function(el){
      el.style.width = el.getAttribute("data-w") + "%";
    });
  });

  /* ---- filters ---- */
  var active = {};
  CLASSES.forEach(function(c){ active[c] = true; });
  var counts = {};
  D.queue.forEach(function(r){ counts[r.finding_class] = (counts[r.finding_class] || 0) + 1; });
  $("filters").innerHTML = CLASSES.filter(function(c){ return counts[c]; }).map(function(c){
    return '<button class="chip" aria-pressed="true" data-c="' + c + '">' +
      '<i style="background:var(' + VAR[c] + ')"></i>' + LABEL[c] + " " + counts[c] + "</button>";
  }).join("") + '<span style="font-size:12px;color:var(--ink-3);margin-left:6px">' +
    D.queue.length + " findings — click a row for its evidence</span>";

  /* ---- queue ---- */
  function renderQueue(){
    var rows = D.queue.map(function(r, i){ return [r, i]; })
      .filter(function(p){ return active[p[0].finding_class]; });
    if (!rows.length){
      $("queueBody").innerHTML = '<tr><td colspan="6" class="empty">Nothing selected.</td></tr>';
      return;
    }
    $("queueBody").innerHTML = rows.map(function(pair){
      var r = pair[0], i = pair[1];
      var ev = Object.keys(r.evidence).map(function(k){
        return "<dt>" + esc(k.replace(/_/g, " ")) + "</dt><dd class='mono'>" + esc(r.evidence[k]) + "</dd>";
      }).join("");
      if (r.missing_witness){
        ev = "<dt>missing witness</dt><dd class='mono'>" + esc(r.missing_witness) + "</dd>" + ev;
      }
      var subjects = r.subjects.map(function(s){
        return esc(s.label) + (s.field ? " <span style='color:var(--ink-3)'>· " + esc(s.field) + "</span>" : "");
      }).join("<br>");
      return '<tr class="row" data-i="' + i + '">' +
        '<td class="sev"><i style="background:var(' + VAR[r.finding_class] + ')"></i></td>' +
        '<td><span class="pill p-' + r.finding_class.replace("_error","") + '"><i></i>' +
          LABEL[r.finding_class] + "</span></td>" +
        '<td><span class="mono" style="font-size:12px">C' + r.validation_class + "</span> " +
          esc(r.class_title) + "</td>" +
        '<td class="subj"><span class="caret">▸</span> ' + subjects + "</td>" +
        '<td class="msg">' + esc(r.message) +
          "<div style='color:var(--ink-3);font-size:11.5px;margin-top:3px' class='mono'>" +
          esc(r.rule_id) + "</div></td>" +
        '<td class="stake mono">' + esc(r.stake_display) + "</td></tr>" +
        '<tr class="detail hidden" data-d="' + i + '"><td></td>' +
        '<td colspan="5"><dl class="evidence">' + ev + "</dl></td></tr>";
    }).join("");
  }
  renderQueue();

  document.addEventListener("click", function(e){
    var chip = e.target.closest(".chip");
    if (chip){
      var c = chip.getAttribute("data-c");
      active[c] = !active[c];
      chip.setAttribute("aria-pressed", String(active[c]));
      renderQueue();
      return;
    }
    var row = e.target.closest("tr.row");
    if (row){
      var d = document.querySelector('tr.detail[data-d="' + row.getAttribute("data-i") + '"]');
      if (d){ d.classList.toggle("hidden"); row.classList.toggle("open"); }
    }
  });

  /* ---- parcels ---- */
  $("parcelBody").innerHTML = D.parcels.map(function(p){
    return "<tr><td class='mono subj'>" + esc(p.path) + "</td>" +
      "<td class='mono'>" + esc(p.area || "—") + "</td>" +
      "<td class='mono' style='color:var(--ink-2)'>" + esc(p.as_written || "—") + "</td>" +
      "<td>" + esc(p.tenure ? p.tenure.replace(/_/g, " ") : "—") + "</td>" +
      "<td class='mono' style='font-size:12px'>" + esc(p.holders.join(", ") || "—") + "</td>" +
      "<td><span class='wbar' style='display:inline-block;width:66px;vertical-align:middle'>" +
        "<i style='width:" + p.witness_percent + "%'></i></span> " +
        "<span class='mono' style='font-size:12px'>" + p.witness_percent + "%</span></td>" +
      "<td>" + (p.error_rows.length
        ? "<span class='pill p-certain'><i></i>" + p.error_rows.length + "</span>"
        : p.finding_rows.length
        ? "<span class='pill p-unverifiable'><i></i>" + p.finding_rows.length + "</span>"
        : "<span style='color:var(--ink-3)'>—</span>") + "</td></tr>";
  }).join("");

  /* ---- rules ---- */
  $("rulesBody").innerHTML = D.rule_classes.map(function(g){
    return '<div class="tablewrap"><table>' +
      "<thead><tr><th>Class " + g.validation_class + " — " + esc(g.title) +
      "</th><th>Scope</th><th>Ran</th><th class='stake'>Findings</th></tr></thead><tbody>" +
      g.rules.map(function(r){
        return "<tr><td><span class='mono' style='font-size:12.5px'>" + esc(r.id) + "</span>" +
          "<div class='msg' style='font-size:12.5px;margin-top:2px'>" + esc(r.description) + "</div></td>" +
          "<td style='font-size:12px;color:var(--ink-2)'>" + esc(r.scope.replace(/_/g, " ")) + "</td>" +
          "<td>" + (r.ran ? "yes" : "<span style='color:var(--ink-3)'>abstained</span>") + "</td>" +
          "<td class='stake mono'>" + r.findings + "</td></tr>";
      }).join("") + "</tbody></table></div>";
  }).join("");

  /* ---- tabs ---- */
  Array.prototype.forEach.call(document.querySelectorAll(".tab"), function(t){
    t.addEventListener("click", function(){
      Array.prototype.forEach.call(document.querySelectorAll(".tab"), function(o){
        o.setAttribute("aria-selected", String(o === t));
      });
      ["queue","parcels","rules"].forEach(function(v){
        $("view-" + v).classList.toggle("hidden", v !== t.getAttribute("data-view"));
      });
    });
  });
})();
</script>
</body>
</html>
"""


def render(payload: dict) -> str:
    """One self-contained page. The payload is embedded, so it opens offline."""
    embedded = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    return _TEMPLATE.replace("__PAYLOAD__", embedded)


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
