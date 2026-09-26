var NM_STATE = {kind:'year', contract:null, benchmark:2025, anchor:'SE4', historyKind:'year', historyYear:2026, metric:'baseload', zone:'SE3'};
var NM_MONTHS = ['jan','feb','mar','apr','maj','jun','jul','aug','sep','okt','nov','dec'];
function nmFmt(v, digits) { return v == null || !Number.isFinite(v) ? '—' : v.toLocaleString('sv-SE',{minimumFractionDigits:digits==null?2:digits,maximumFractionDigits:digits==null?2:digits}); }
function nmDelta(v, suffix) { return v == null ? '—' : (v>0?'+':'')+nmFmt(v,suffix===' %'?1:2)+(suffix||''); }
function nmPeriod(row) { return row.kind==='year'?String(row.year):row.kind==='quarter'?'Q'+row.number+' '+row.year:NM_MONTHS[row.number-1]+' '+row.year; }
function nmOptions(node, entries, value) { node.innerHTML=entries.map(function(e){return '<option value="'+htmlEsc(String(e[0]))+'">'+htmlEsc(String(e[1]))+'</option>';}).join(''); node.value=String(value); }
function nmHistory(zone, kind, year, number, complete) { var d=DATA.nordic_market; return (d.history[zone]||[]).find(function(r){return r.kind===kind&&r.year===Number(year)&&r.number===number&&(!complete||!r.partial);})||null; }
function nmCurrent() { return DATA.nordic_market.futures.find(function(r){return r.id===NM_STATE.contract&&r.kind===NM_STATE.kind;}); }
function nmBase(zone, contract) { return contract?nmHistory(zone,contract.kind,NM_STATE.benchmark,contract.number,true):null; }
function nmAreaPrice(contract, zone) { var a=contract.areas[zone];return nmFmt(a.price)+(a.price==null?'<span class="nm-cell-note">'+(a.epad==null?(contract.kind==='month'?'Månads-EPAD saknas':'EPAD saknas'):'Systempris saknas')+'</span>':''); }
function nmTable(id, heads, rows) { el(id).innerHTML='<thead><tr>'+heads.map(function(h){return '<th scope="col">'+h+'</th>';}).join('')+'</tr></thead><tbody>'+rows.join('')+'</tbody>'; }
function nmActualCell(row) { if(!row)return '—';return nmFmt(row.capture_actual)+'<span class="nm-cell-note">'+(row.capture_actual==null?'Otillräckligt underlag · ':'')+nmFmt(row.actual_coverage_pct,1)+' % täckning'+(row.actual_through?' · t.o.m. '+htmlEsc(row.actual_through):'')+'</span>'; }
function nmPlot(id, traces, extra) {
    if(typeof Plotly==='undefined'){el(id).innerHTML='<p class="nm-note">Diagrammet kunde inte laddas. Alla värden finns i tabellen.</p>';return;}
    var layout=Object.assign({paper_bgcolor:'transparent',plot_bgcolor:'transparent',font:{family:'Arial, sans-serif',size:13,color:'#353d2d'},margin:{l:58,r:20,t:22,b:66},legend:{orientation:'h',y:1.18},yaxis:{title:'EUR/MWh',gridcolor:'#e4e7dc',zerolinecolor:'#939c82'},xaxis:{automargin:true},hovermode:'x unified',barmode:'group'},extra||{});
    Plotly.react(id,traces,layout,{responsive:true,displayModeBar:false});
}
function renderNordicMarket() {
    var d=DATA.nordic_market;
    if(!el('nordic-market'))return;
    if(!d){el('nordic-market').innerHTML='<p class="empty-note">Den utökade marknadsöversikten saknar ännu data.</p>';return;}
    var age=d.settlement_date?Math.floor((Date.now()-Date.parse(d.settlement_date+'T00:00:00Z'))/86400000):null;
    el('nm-status').innerHTML='<span>Avräkning <strong>'+htmlEsc(d.settlement_date||'saknas')+'</strong>'+(age>4?' · äldre notering':'')+'</span><span>Spothistorik t.o.m. <strong>'+htmlEsc(d.through)+'</strong></span><span>6 elområden · EUR/MWh</span>';
    var years=Array.from(new Set(d.history.SE3.map(function(r){return r.year;}))).sort();
    if(years.indexOf(NM_STATE.historyYear)<0)NM_STATE.historyYear=years[years.length-1];
    nmOptions(el('nm-benchmark'),years.map(function(y){return [y,'Samma period '+y];}),NM_STATE.benchmark);
    nmOptions(el('nm-history-year'),years.map(function(y){return [y,y];}),NM_STATE.historyYear);
    nmOptions(el('nm-anchor'),d.zones.map(function(z){return [z,z];}),NM_STATE.anchor);
    nmOptions(el('nm-zone'),d.zones.map(function(z){return [z,z];}),NM_STATE.zone);
    el('nm-kind').querySelectorAll('button').forEach(function(b){b.setAttribute('aria-pressed',String(b.dataset.kind===NM_STATE.kind));b.onclick=function(){NM_STATE.kind=b.dataset.kind;NM_STATE.contract=null;renderNordicMarket();};});
    [['nm-benchmark','benchmark'],['nm-anchor','anchor'],['nm-zone','zone'],['nm-history-kind','historyKind'],['nm-history-year','historyYear'],['nm-metric','metric']].forEach(function(pair){
        var node=el(pair[0]);node.value=String(NM_STATE[pair[1]]);node.onchange=function(){NM_STATE[pair[1]]=['benchmark','historyYear'].indexOf(pair[1])>=0?Number(node.value):node.value;renderNordicMarket();};
    });
    var contracts=d.futures.filter(function(r){return r.kind===NM_STATE.kind&&(r.system!=null||d.zones.some(function(z){return r.areas[z].price!=null;}));});
    if(!contracts.some(function(r){return r.id===NM_STATE.contract;})){var next=contracts.find(function(r){return r.start>d.through;});NM_STATE.contract=next?next.id:contracts.length?contracts[0].id:null;}
    nmOptions(el('nm-contract'),contracts.map(function(r){return [r.id,nmPeriod(r)+(r.start<=d.through?' · under leverans':'')+(d.zones.every(function(z){return r.areas[z].price==null;})?' · endast SYS':'')];}),NM_STATE.contract);
    el('nm-contract').onchange=function(){NM_STATE.contract=this.value;renderNordicMarket();};
    nmTable('nm-forward',['Leverans','SYS'].concat(d.zones),contracts.map(function(r){return '<tr class="'+(r.id===NM_STATE.contract?'nm-selected':'')+'"><td><button type="button" class="nm-contract-button" data-contract="'+r.id+'" aria-pressed="'+(r.id===NM_STATE.contract)+'">'+nmPeriod(r)+'</button></td><td>'+nmFmt(r.system)+'</td>'+d.zones.map(function(z){var a=r.areas[z];return '<td class="nm-primary" title="'+(a.price==null?'Komplett områdesnotering saknas':'EPAD '+nmFmt(a.epad)+' · volym '+nmFmt(a.volume,0)+' · öppna kontrakt '+nmFmt(a.open_interest,0))+'">'+nmFmt(a.price)+'</td>';}).join('')+'</tr>';}));
    el('nm-forward').querySelectorAll('[data-contract]').forEach(function(b){var row=contracts.find(function(r){return r.id===b.dataset.contract;});var cells=b.closest('tr').querySelectorAll('td');d.zones.forEach(function(z,i){cells[i+2].innerHTML=nmAreaPrice(row,z);});if(row.start<=d.through){var note=document.createElement('span');note.className='nm-cell-note';note.textContent='Under leverans';b.after(note);}b.onclick=function(){NM_STATE.contract=b.dataset.contract;renderNordicMarket();};});
    nmRenderComparison();nmRenderHistory();nmRenderMethod();
}
function nmRenderComparison() {
    var d=DATA.nordic_market,c=nmCurrent(),s=NM_STATE;
    if(!c){el('nm-comparison-label').textContent='Inga terminsnoteringar';nmTable('nm-comparison',['Status'],['<tr><td>Data saknas för vald upplösning.</td></tr>']);nmTable('nm-spreads',['Status'],[]);el('nm-insight').textContent='Välj en annan upplösning.';nmPlot('nm-comparison-chart',[]);return;}
    var baselineLabel=nmPeriod({kind:c.kind,year:s.benchmark,number:c.number});
    el('nm-comparison-label').textContent=nmPeriod(c)+' mot '+baselineLabel;
    var diffs=[];
    nmTable('nm-comparison',['Område','Termin','Historisk baseload','Skillnad','Skillnad %','Sol · referens','Sol · rapporterad'],d.zones.map(function(z){
        var a=c.areas[z],h=nmBase(z,c),base=h?h.baseload:null,delta=a.price!=null&&base!=null?a.price-base:null,pct=delta!=null&&base>0?delta/base*100:null;
        if(delta!=null)diffs.push({zone:z,delta:delta});
        return '<tr><td><strong>'+z+'</strong></td><td class="nm-primary">'+nmAreaPrice(c,z)+'</td><td>'+nmFmt(base)+(h?'':'<span class="nm-cell-note">Ingen avslutad jämförelseperiod</span>')+'</td><td class="'+(delta>0?'nm-positive':'nm-negative')+'">'+nmDelta(delta)+'</td><td>'+nmDelta(pct,' %')+'</td><td>'+nmFmt(h?h.capture_reference:null)+'</td><td>'+nmActualCell(h)+'</td></tr>';
    }));
    var anchor=s.anchor,ac=c.areas[anchor].price,ah=nmBase(anchor,c),rows=[],spreadDiffs=[];
    d.zones.filter(function(z){return z!==anchor;}).forEach(function(z){var f=c.areas[z].price,h=nmBase(z,c),fs=f!=null&&ac!=null?f-ac:null,hs=h&&ah&&h.baseload!=null&&ah.baseload!=null?h.baseload-ah.baseload:null,delta=fs!=null&&hs!=null?fs-hs:null;if(delta!=null)spreadDiffs.push({zone:z,delta:delta});rows.push('<tr><td>'+z+' − '+anchor+'</td><td>'+nmDelta(fs)+'</td><td>'+nmDelta(hs)+'</td><td class="'+(delta>0?'nm-positive':'nm-negative')+'">'+nmDelta(delta)+'</td></tr>');});
    nmTable('nm-spreads',['Områdespar','Terminsskillnad','Historisk skillnad','Förändring'],rows);
    diffs.sort(function(a,b){return b.delta-a.delta;});spreadDiffs.sort(function(a,b){return Math.abs(b.delta)-Math.abs(a.delta);});
    var text='';
    if(diffs.length){text=diffs[0].zone+' har högst avvikelse mot '+baselineLabel+': '+nmDelta(diffs[0].delta)+' EUR/MWh. ';if(diffs.length>1){var low=diffs[diffs.length-1];text+=low.zone+' har lägst: '+nmDelta(low.delta)+' EUR/MWh. ';}}
    if(spreadDiffs.length){var sp=spreadDiffs[0];text+='Störst förändring mot '+anchor+': '+sp.zone+' ('+nmDelta(sp.delta)+' EUR/MWh i områdesskillnad). ';}
    if(d.zones.every(function(z){return c.areas[z].price==null;}))text='Endast systempriset är noterat för '+nmPeriod(c)+' ('+nmFmt(c.system)+' EUR/MWh). EPAD saknas för områdena, så områdesterminer och deras avvikelser mot historiken kan inte beräknas. Historiska områdespriser visas som referens.';
    el('nm-insight').textContent=text||'Jämförelsen kräver ett avslutat historiskt år, kvartal eller månad med tillräcklig spotdata. Välj ett tidigare jämförelseår.';
    nmPlot('nm-comparison-chart',[{type:'bar',name:'Termin '+nmPeriod(c),x:d.zones,y:d.zones.map(function(z){return c.areas[z].price;}),marker:{color:'#252c22'}},{type:'bar',name:'Baseload '+baselineLabel,x:d.zones,y:d.zones.map(function(z){var h=nmBase(z,c);return h?h.baseload:null;}),marker:{color:'#a6c74e'}}]);
}
function nmRenderHistory() {
    var d=DATA.nordic_market,s=NM_STATE;
    el('nm-year-label').hidden=s.historyKind==='year';
    var ids={};d.zones.forEach(function(z){(d.history[z]||[]).filter(function(r){return r.kind===s.historyKind&&(s.historyKind==='year'||r.year===s.historyYear);}).forEach(function(r){ids[r.id]=r;});});
    var periods=Object.values(ids).sort(function(a,b){return a.start.localeCompare(b.start);});
    var names={baseload:'Baseload',capture_reference:'Solcapture · referensprofil',capture_actual:'Solcapture · rapporterad produktion'};
    el('nm-history-label').textContent=names[s.metric]+' · EUR/MWh';
    nmTable('nm-history',['Period'].concat(d.zones),periods.map(function(r){
        return '<tr><td>'+nmPeriod(r)+(r.partial?'<span class="nm-cell-note">'+(r.kind==='year'?'YTD':r.kind==='quarter'?'QTD':'MTD')+' t.o.m. '+htmlEsc(d.through)+'</span>':'')+'</td>'+d.zones.map(function(z){var h=nmHistory(z,r.kind,r.year,r.number,false);return '<td>'+(s.metric==='capture_actual'?nmActualCell(h):nmFmt(h?h[s.metric]:null)+(h&&h.coverage_pct<99.99?'<span class="nm-cell-note">'+nmFmt(h.coverage_pct,1)+' % spotdata</span>':''))+'</td>';}).join('')+'</tr>';
    }));
    var zoneRows=periods.map(function(r){return nmHistory(s.zone,r.kind,r.year,r.number,false);});
    nmPlot('nm-history-chart',[['baseload','Baseload','#252c22'],['capture_reference','Sol · referens','#769c20'],['capture_actual','Sol · rapporterad','#237e85']].map(function(spec){return {type:'scatter',mode:'lines+markers',name:spec[1],x:periods.map(function(r){return nmPeriod(r)+(r.partial?' *':'');}),y:zoneRows.map(function(r){return r?r[spec[0]]:null;}),connectgaps:false,line:{color:spec[2],width:2},marker:{size:6}};}),{title:{text:s.zone,font:{size:15},x:0},xaxis:{type:'category',automargin:true},margin:{l:58,r:16,t:64,b:65},legend:{orientation:'h',y:1.18}});
    el('nm-history-note').textContent=s.metric==='capture_actual'?'Rapporterad capture använder endast intervall med både pris och produktion. Under 90 % tidsmässig täckning visas inget pris. Ofullständiga serier är inte direkt jämförbara med kompletta perioder. Saknad produktion ersätts aldrig med noll.':'Baseload är tidsvägt. Referenscapture använder '+d.reference_profile+'. Det är historiska priser viktade med en gemensam modellprofil, inte uppmätt produktion eller en lokal produktionsprognos. * anger pågående period.';
}
function nmRenderMethod() {
    var d=DATA.nordic_market;
    el('nm-method').innerHTML='<p><strong>Terminer.</strong> Områdespris = systempris + EPAD för samma leveransperiod och avräkningsdag. Kalenderår, kvartal och månader har separata kontrakt. Avsaknad av notering innebär aldrig nollpris. Tabellen visar alla leveranser med systempris eller komplett områdesnotering. Leveranser med endast SYS visas med saknad EPAD i områdeskolumnerna; systempriset ersätter aldrig ett områdespris. Komponenter, omsättning och öppna kontrakt framgår när du pekar på priset.</p>'+
    '<p><strong>Baseload.</strong> Summan av pris × intervallängd dividerad med timmar. UTC används för tidsmatchning; kalenderperioder avgränsas i svensk/dansk lokal tid. Timpriser upprepas över fyra kvartar. Ofullständiga år/kvartal/månader markeras YTD/QTD/MTD. Minst 99 % spotdatatäckning krävs för att visa ett pris. Jämförelsen mot terminer använder endast avslutade historiska perioder av samma typ. Procentuell avvikelse visas endast när historisk baseload är positiv.</p>'+
    '<p><strong>Solcapture · referens.</strong> Σ(pris × profilenergi) / Σ(profilenergi). '+htmlEsc(d.reference_profile)+'. Timprofilen hålls konstant inom timmen, även när priset är kvartsvist. 29 februari använder 28 februari. Profilen möjliggör samma jämförelse för alla sex områden men representerar inte deras lokala väder eller teknikmix.</p>'+
    '<p><strong>Solcapture · rapporterad.</strong> Σ(pris × rapporterad solenergi) / Σ(rapporterad solenergi), endast på matchade intervall. Sverige: ENTSO-E:s rapporterade solproduktion, vars anläggningstäckning kan vara begränsad. Danmark: Energinets avräknade solproduktion levererad till nätet, summerad över storleksklasser; egenförbrukning exkluderas. Timproduktion fördelas jämnt inom timmen. Under 90 % täckning eller utan positiv solenergi visas streck. Täckningen gäller tid, inte andel av områdets installerade solkapacitet. Dessa källor är inte identiska mätpopulationer.</p>'+
    '<p><strong>Senaste rapporterade soldata:</strong> '+d.zones.map(function(z){return z+' '+htmlEsc(d.production_through[z]||'saknas');}).join(' · ')+'. Uppdatering av spot innebär inte att produktionen uppdaterats lika långt.</p>'+
    '<p><strong>Tolkning.</strong> En historisk prisskillnad är inte ett rättvist terminspris. Väderscenarier, bränslepriser, nätbegränsningar, förändrad produktion, riskpremier och likviditet kan motivera avvikelsen.</p>'+
    '<p><strong>Källor:</strong> <a href="'+d.sources.futures+'" target="_blank" rel="noopener">Euronext/Nord Pool</a> · <a href="'+d.sources.spot_dk+'" target="_blank" rel="noopener">Energinet spot DK1/DK2/SE3/SE4</a> · <a href="'+d.sources.spot_se+'" target="_blank" rel="noopener">Elprisetjustnu SE1/SE2</a> · <a href="'+d.sources.solar_se+'" target="_blank" rel="noopener">ENTSO-E sol</a> · <a href="'+d.sources.solar_dk+'" target="_blank" rel="noopener">Energinet sol</a>.</p>';
}
