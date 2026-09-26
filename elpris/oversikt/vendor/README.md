# Vendorad Plotly

`plotly-cartesian.min.js` är plotly.js v3.3.0, det officiella delpaketet
`plotly.js-cartesian-dist-min` (MIT-licens, © Plotly, Inc.), hämtat från
jsdelivr 2026-09-26. Delpaketet har de diagramtyper sidan använder (scatter,
bar och heatmap) och är 1,4 MB mot 4,8 MB för hela Plotly. Licensen ligger i
`LICENSE-plotly.txt`.

Electricity Price bäddar in filen i HTML:en så att sidan fungerar utan
nätåtkomst: i appens förhandsvisning (som blockerar externa skript), offline
och som mejlbilaga. Renderaren avbryter om filen saknas eller innehåller
`</script`.

Uppdatera genom att ersätta filen med samma paket i en nyare version.
