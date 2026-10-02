<#
.SYNOPSIS
  Registrerar (eller tar bort) Elpris-synkens två uppgifter i Windows Schemaläggaren.

.DESCRIPTION
  \Elpris\Elpris morgon  dagligen 06:30   elpris_sync.ps1 -Lage Morgon
  \Elpris\Elpris kväll   mån–fre 19:15    elpris_sync.ps1 -Lage Kvall

  Uppgifterna körs som inloggad användare, startas i efterhand om datorn var
  avstängd vid starttiden och får väcka datorn ur viloläge.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\windows\registrera.ps1
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\windows\registrera.ps1 -Avregistrera
#>
param([switch]$Avregistrera)

$ErrorActionPreference = 'Stop'
$Mapp = '\Elpris\'
$Skript = Join-Path $PSScriptRoot 'elpris_sync.ps1'
$Repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

$Uppgifter = @(
    @{ Namn = 'Elpris morgon'; Lage = 'Morgon'; Trigger = New-ScheduledTaskTrigger -Daily -At '06:30' }
    @{ Namn = 'Elpris kväll'; Lage = 'Kvall'
       Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday -At '19:15' }
)

if ($Avregistrera) {
    foreach ($u in $Uppgifter) {
        if (Get-ScheduledTask -TaskPath $Mapp -TaskName $u.Namn -ErrorAction SilentlyContinue) {
            Unregister-ScheduledTask -TaskPath $Mapp -TaskName $u.Namn -Confirm:$false
            Write-Host "Borttagen: $Mapp$($u.Namn)"
        }
    }
    return
}

$Installningar = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun `
    -ExecutionTimeLimit (New-TimeSpan -Hours 6) -MultipleInstances IgnoreNew `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$Anvandare = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive

foreach ($u in $Uppgifter) {
    $atgard = New-ScheduledTaskAction -Execute 'powershell.exe' -WorkingDirectory $Repo `
        -Argument ("-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"{0}`" -Lage {1}" -f $Skript, $u.Lage)
    Register-ScheduledTask -TaskPath $Mapp -TaskName $u.Namn -Action $atgard -Trigger $u.Trigger `
        -Settings $Installningar -Principal $Anvandare -Force | Out-Null
    $info = Get-ScheduledTaskInfo -TaskPath $Mapp -TaskName $u.Namn
    Write-Host ("Registrerad: {0}{1}, nästa körning {2}" -f $Mapp, $u.Namn, $info.NextRunTime)
}
