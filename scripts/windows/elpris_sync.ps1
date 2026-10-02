<#
.SYNOPSIS
  Automatisk datasync för Electricity Price (Windows Schemaläggaren).

.DESCRIPTION
  Morgon: update_all.py, klar-kontroll med omförsök tills gårdagen är komplett
          (eller klockan passerat -Sista), commit + push av datan, granskning.
  Kvall:  futures_daily.py, generate_oversikt.py --also-artifact, granskning.

  Lyckat bygge och granskning ger Resultat/publicera/klar.json, som Claude-appens
  schemalagda uppgift elpris-publicera läser och publicerar.
  Design: docs/plans/2026-10-02-automatisk-datasync-design.md

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\windows\elpris_sync.ps1 -Lage Morgon -Torrkorning
#>
param(
    [ValidateSet('Morgon', 'Kvall')][string]$Lage = 'Morgon',
    [switch]$Torrkorning,
    [string]$Sista = '11:00',
    [int]$VantaMinuter = 30
)

$ErrorActionPreference = 'Continue'
$Repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $Repo
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
$env:GIT_TERMINAL_PROMPT = '0'
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false } catch {}
$Python = if ($env:ELPRIS_PYTHON) { $env:ELPRIS_PYTHON } else { 'python' }

$Pub = Join-Path $Repo 'Resultat\publicera'
$Loggar = Join-Path $Repo 'Resultat\logs'
New-Item -ItemType Directory -Force -Path $Pub, $Loggar | Out-Null
$Start = Get-Date
$Idag = $Start.ToString('yyyyMMdd')
$Logg = Join-Path $Loggar ("sync_{0}_{1}.log" -f $Lage.ToLower(), $Idag)
$Varningar = New-Object System.Collections.Generic.List[string]

function Logga([string]$Text) {
    $rad = '{0:yyyy-MM-dd HH:mm:ss} {1}' -f (Get-Date), $Text
    Write-Host $rad
    Add-Content -Path $Logg -Value $rad -Encoding UTF8
}

function Kor([string]$Namn, [string]$Exe, [string[]]$Argument) {
    if ($Torrkorning) {
        Logga ("TORRKÖRNING {0}: {1} {2}" -f $Namn, $Exe, ($Argument -join ' '))
        return 0
    }
    Logga "START $Namn"
    $t0 = Get-Date
    & $Exe @Argument 2>&1 | ForEach-Object { "$_" } | Add-Content -Path $Logg -Encoding UTF8
    $kod = $LASTEXITCODE
    Logga ("SLUT {0}: kod {1} efter {2:N0} s" -f $Namn, $kod, ((Get-Date) - $t0).TotalSeconds)
    return $kod
}

function Datastatus {
    $ut = & $Python scripts\datastatus_klar.py 2>&1 | ForEach-Object { "$_" }
    $json = ($ut | Where-Object { $_.StartsWith('{') } | Select-Object -Last 1)
    if (-not $json) { Logga "FEL: datastatus_klar gav inget svar: $ut"; return $null }
    $status = $json | ConvertFrom-Json
    if ($status.komplett) { Logga "Komplett t.o.m. $($status.dag)" }
    else { Logga ("Saknas för {0}: {1}" -f $status.dag, ($status.saknas -join '; ')) }
    return $status
}

function Committa([string]$Dag) {
    $gren = (git rev-parse --abbrev-ref HEAD) 2>$null
    if ($gren -ne 'main') { $Varningar.Add("Ingen commit: repot står på grenen '$gren', inte main"); return }
    $vagar = @('Resultat/marknadsdata', 'Resultat/profiler')
    if ($Torrkorning) { Logga "TORRKÖRNING git: add -u + nya *.csv/futures_*.json i $($vagar -join ', '), commit, push"; return }
    # Bara sådant som brukar committas: ändrade spårade filer, nya CSV-filer och terminsögonblicksbilder.
    git add -u -- @vagar 2>&1 | Out-Null
    $nya = git ls-files --others --exclude-standard -- @vagar |
        Where-Object { $_ -like '*.csv' -or $_ -like 'Resultat/marknadsdata/nordic_market/futures_*.json' }
    foreach ($fil in $nya) { git add -- $fil 2>&1 | Out-Null }
    git diff --cached --quiet -- @vagar
    if ($LASTEXITCODE -eq 0) { Logga 'Git: ingen ny data att committa'; return }
    $meddelande = "data: sync electricity markets and solar parks through $Dag"
    git commit -q -m $meddelande -- @vagar 2>&1 | ForEach-Object { "$_" } | Add-Content -Path $Logg -Encoding UTF8
    if ($LASTEXITCODE -ne 0) { $Varningar.Add('git commit misslyckades (se loggen)'); return }
    Logga "Git: $meddelande"
    git push -q origin main 2>&1 | ForEach-Object { "$_" } | Add-Content -Path $Logg -Encoding UTF8
    if ($LASTEXITCODE -ne 0) { $Varningar.Add('git push misslyckades; commiten ligger lokalt') }
    else { Logga 'Git: pushad till origin/main' }
}

function Granska([string]$Sida) {
    $ut = Join-Path $env:TEMP 'elpris_granskning'
    $url = ([System.Uri]$Sida).AbsoluteUri
    $svar = & node scripts\granska_sidan.mjs $url $ut 1440 light 2>&1 | ForEach-Object { "$_" }
    if ($LASTEXITCODE -ne 0) { return "granskningen kraschade: $($svar -join ' ')" }
    try { $rapport = ($svar -join "`n") | ConvertFrom-Json } catch { return "granskningen gav ogiltig JSON" }
    $fel = @($rapport | ForEach-Object { $_.errors } | Where-Object { $_ })
    if ($fel.Count -gt 0) { return "konsolfel: $($fel -join ' | ')" }
    if (($rapport | Select-Object -First 1).h -lt 3000) { return 'sidan är nästan tom' }
    return $null
}

# --- Lås ---------------------------------------------------------------------
$Las = Join-Path $Pub 'sync.lock'
if ((Test-Path $Las) -and (Get-Item $Las).LastWriteTime -gt (Get-Date).AddHours(-3)) {
    Logga "En annan körning pågår ($Las), avslutar"
    exit 0
}
Set-Content -Path $Las -Value $PID
$Utkod = 0
try {
    Logga "=== Elpris-sync $Lage$(if ($Torrkorning) { ' (torrkörning)' }) ==="

    if ($Lage -eq 'Morgon') {
        $kod = Kor 'update_all' $Python @('update_all.py', '--quiet', '--auto-reports')
        if ($kod -ne 0) { $Varningar.Add("update_all.py avslutade med kod $kod (se loggen)") }
        $status = Datastatus
        $sistaTid = [datetime]::ParseExact($Sista, 'HH:mm', $null)
        while (-not $Torrkorning -and $status -and -not $status.komplett -and
               (Get-Date).AddMinutes($VantaMinuter) -le $sistaTid) {
            Logga "Väntar $VantaMinuter min och hämtar igen"
            Start-Sleep -Seconds ($VantaMinuter * 60)
            $kod = Kor 'update_all (omförsök)' $Python @('update_all.py', '--quiet', '--skip-excel')
            $status = Datastatus
        }
        if ($status -and -not $status.komplett) {
            foreach ($s in $status.saknas) { $Varningar.Add("Saknas för $($status.dag): $s") }
        }
        $dag = if ($status) { $status.dag } else { $Start.AddDays(-1).ToString('yyyy-MM-dd') }
        Committa $dag
    }
    else {
        $kod = Kor 'futures_daily' $Python @('futures_daily.py')
        if ($kod -ne 0) { $Varningar.Add("futures_daily.py avslutade med kod $kod (se Resultat/logs/futures_daily_$Idag.log)") }
        $kod = Kor 'generate_oversikt' $Python @('generate_oversikt.py', '--also-artifact')
        if ($kod -ne 0) { throw "generate_oversikt.py avslutade med kod $kod" }
    }

    $sida = Join-Path $Repo "Resultat\rapporter\electricity_price_$Idag.html"
    $artefakt = Join-Path $Repo "Resultat\rapporter\electricity_price_${Idag}_artifact.html"
    if ($Torrkorning) {
        Logga "TORRKÖRNING granska $sida och skriv $Pub\klar.json för $artefakt"
        return
    }
    foreach ($f in $sida, $artefakt) {
        if (-not (Test-Path $f) -or (Get-Item $f).LastWriteTime -lt $Start) { throw "Sidan byggdes inte i den här körningen: $f" }
    }
    $fel = Granska $sida
    if ($fel) { throw "Granskningen stoppade publiceringen: $fel" }
    Logga 'Granskning OK'

    $innehall = [System.IO.File]::ReadAllText($artefakt, [System.Text.Encoding]::UTF8)
    $m = [regex]::Match($innehall, 'data_end_label":"([^"]+)"')
    if (-not $m.Success) { throw 'Sidan saknar data_end_label' }
    $klar = [ordered]@{
        fil       = $artefakt
        sha256    = (Get-FileHash $artefakt -Algorithm SHA256).Hash.ToLower()
        storlek   = (Get-Item $artefakt).Length
        data_tom  = $m.Groups[1].Value
        lage      = $Lage
        varningar = @($Varningar)
        skapad    = (Get-Date).ToString('yyyy-MM-ddTHH:mm:ss')
    }
    $json = $klar | ConvertTo-Json -Depth 3
    [System.IO.File]::WriteAllText((Join-Path $Pub 'klar.json'), $json, (New-Object System.Text.UTF8Encoding $false))
    Logga "klar.json skriven: data t.o.m. $($klar.data_tom), $($Varningar.Count) varning(ar)"
}
catch {
    Logga "FEL: $($_.Exception.Message)"
    $Utkod = 1
}
finally {
    foreach ($v in $Varningar) { Logga "VARNING: $v" }
    Remove-Item $Las -ErrorAction SilentlyContinue
    Logga "=== Slut, kod $Utkod ==="
}
exit $Utkod
