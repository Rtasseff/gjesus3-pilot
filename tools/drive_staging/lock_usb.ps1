# lock_usb.ps1 -- run as administrator. Protects a one-copy source drive before Windows touches it:
#   1. turns off automatic mounting of new volumes (mountvol /N), so plugging in writes nothing;
#   2. waits for the drive, sets the whole disk read-only, and checks that it took;
#   3. only then mounts its data partition(s) with a drive letter and records model, serial, health.
# The read-only flag is kept by this PC for that disk; nothing is written to the drive itself.
#   lock_usb.ps1            protect + mount the next drive plugged in (or any already attached)
#   lock_usb.ps1 -Restore   turn automatic mounting back on (after the last drive is done)
param([switch]$Restore, [int]$WaitMinutes = 20)
$ErrorActionPreference = 'Stop'
$log = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) 'lock_usb.log'
function Say($msg, $color = 'Gray') {
    Write-Host $msg -ForegroundColor $color
    Add-Content -Path $log -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $msg" -Encoding utf8
}

try {
    if ($Restore) { mountvol /E; Say 'Automatic mounting turned back ON (mountvol /E).' 'Green'; return }

    $system = @('C', 'D' | ForEach-Object { (Get-Partition -DriveLetter $_).DiskNumber })
    Say "=== lock_usb start. System disks, never touched: $($system -join ', ')"
    mountvol /N
    Say 'Automatic mounting OFF (mountvol /N).'

    $others = { @(Get-Disk | Where-Object { $system -notcontains $_.Number }) }
    $targets = & $others
    if (-not $targets) {
        Say ">>> Plug in ONE drive now. Waiting up to $WaitMinutes minutes... <<<" 'Yellow'
        $deadline = (Get-Date).AddMinutes($WaitMinutes)
        while (-not $targets -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 500; $targets = & $others }
        if (-not $targets) { throw 'No new drive appeared.' }
    }

    foreach ($t in $targets) {
        $n = $t.Number
        Set-Disk -Number $n -IsReadOnly $true          # lock first, before anything else
        if ((Get-Disk -Number $n).IsOffline) { Set-Disk -Number $n -IsOffline $false }
        $d = Get-Disk -Number $n
        if (-not $d.IsReadOnly) { throw "Disk $n is NOT read-only. Unplug it and stop." }
        Say ("LOCKED READ-ONLY: disk {0} | {1} | serial {2} | bus {3} | {4:N0} GB | {5}" -f `
            $n, $d.FriendlyName, $d.SerialNumber, $d.BusType, ($d.Size / 1e9), $d.PartitionStyle) 'Green'

        foreach ($p in Get-Partition -DiskNumber $n) {
            if ($p.Type -in 'System', 'Reserved', 'Recovery' -or $p.Size -lt 1GB) { continue }
            if (-not [char]::IsLetter([char]$p.DriveLetter)) {
                try { Add-PartitionAccessPath -DiskNumber $n -PartitionNumber $p.PartitionNumber -AssignDriveLetter }
                catch {
                    $free = [char[]]'RTUVQPONML' | Where-Object { -not (Test-Path "${_}:\") } | Select-Object -First 1
                    $guid = $p.AccessPaths | Where-Object { $_ -like '\\?\Volume*' } | Select-Object -First 1
                    Say "AssignDriveLetter failed ($_); mounting $guid as ${free}: via mountvol"
                    mountvol "${free}:" $guid
                }
            }
            $p = Get-Partition -DiskNumber $n -PartitionNumber $p.PartitionNumber
            $v = Get-Volume -Partition $p -ErrorAction SilentlyContinue
            Say ("  partition {0}: letter {1}: | {2} | label '{3}' | size {4:N0} GB | used {5:N0} GB | health {6}" -f `
                $p.PartitionNumber, $p.DriveLetter, $v.FileSystem, $v.FileSystemLabel, ($v.Size / 1e9),
                (($v.Size - $v.SizeRemaining) / 1e9), $v.HealthStatus) 'Green'
        }

        $pd = Get-PhysicalDisk | Where-Object DeviceId -eq "$n"
        Say "  physical disk: media $($pd.MediaType) | health $($pd.HealthStatus) | status $($pd.OperationalStatus)"
        try {
            $r = $pd | Get-StorageReliabilityCounter
            Say ("  SMART via Windows: temp {0} C | power-on hours {1} | read errors total {2} | uncorrected {3}" -f `
                $r.Temperature, $r.PowerOnHours, $r.ReadErrorsTotal, $r.ReadErrorsUncorrected)
        } catch { Say '  SMART via Windows: not available through this USB enclosure.' }
    }
    Say '=== Done. The drive is read-only and mounted. You can close this window.' 'Green'
}
catch { Say "ERROR: $_" 'Red' }
finally { Read-Host 'Press Enter to close' | Out-Null }
