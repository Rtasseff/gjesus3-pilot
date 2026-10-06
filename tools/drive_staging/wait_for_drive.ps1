# wait_for_drive.ps1 -- no admin needed. Waits for a newly plugged-in volume and reports what it is.
param([int]$WaitMinutes = 45)
$known = @(Get-Volume | Where-Object DriveLetter | ForEach-Object DriveLetter)
$deadline = (Get-Date).AddMinutes($WaitMinutes)
while ((Get-Date) -lt $deadline) {
    $new = @(Get-Volume | Where-Object { $_.DriveLetter -and $known -notcontains $_.DriveLetter })
    if ($new) { break }
    Start-Sleep -Seconds 2
}
if (-not $new) { Write-Output "NO NEW DRIVE after $WaitMinutes minutes"; exit 1 }
Start-Sleep -Seconds 5
foreach ($v in Get-Volume | Where-Object { $_.DriveLetter -and $known -notcontains $_.DriveLetter }) {
    $d = Get-Partition -DriveLetter $v.DriveLetter | Get-Disk
    $pd = Get-PhysicalDisk | Where-Object DeviceId -eq "$($d.Number)"
    Write-Output ("NEW DRIVE {0}: | fs {1} | label '{2}' | size {3:N0} GB | used {4:N0} GB | free {5:N0} GB | volume health {6}" -f `
        $v.DriveLetter, $v.FileSystem, $v.FileSystemLabel, ($v.Size / 1e9), (($v.Size - $v.SizeRemaining) / 1e9),
        ($v.SizeRemaining / 1e9), $v.HealthStatus)
    Write-Output ("  disk {0} | {1} | serial {2} | bus {3} | {4:N0} GB | {5} | media {6} | disk health {7} | read-only {8}" -f `
        $d.Number, $d.FriendlyName, $d.SerialNumber, $d.BusType, ($d.Size / 1e9), $d.PartitionStyle,
        $pd.MediaType, $pd.HealthStatus, $d.IsReadOnly)
}
