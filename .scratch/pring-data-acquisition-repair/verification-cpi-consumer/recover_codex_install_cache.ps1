$ErrorActionPreference = 'Stop'
$cacheBase = [IO.Path]::GetFullPath((Join-Path $env:USERPROFILE '.cache\codex-runtimes'))
$destinationRoot = [IO.Path]::GetFullPath('D:\cursor\datasourceRF\.tmp\codex-install-cache-recovery-20260908')
$workspaceRoot = [IO.Path]::GetFullPath('D:\cursor\datasourceRF')
if (-not $destinationRoot.StartsWith($workspaceRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid recovery destination' }
if (Test-Path -LiteralPath $destinationRoot) { throw 'One-time recovery already started' }
$names = @(
    'codex-runtime-install-2KfuiC\node-runtime.tar.xz',
    'codex-runtime-install-8TOPPq\node-runtime.tar.xz',
    'codex-runtime-install-NvPL1u\node-runtime.tar.xz',
    'codex-runtime-install-parVoz\node-runtime.tar.xz',
    'codex-runtime-install-wahX17\node-runtime.tar.gz'
)
$processes = @(Get-CimInstance Win32_Process)
$entries = @()
foreach ($name in $names) {
    $source = [IO.Path]::GetFullPath((Join-Path $cacheBase $name))
    if (-not $source.StartsWith($cacheBase + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Source escaped cache' }
    $file = Get-Item -LiteralPath $source
    if ($file.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Link refused' }
    if ($file.LastWriteTimeUtc -gt [DateTime]::UtcNow.AddDays(-7)) { throw 'Recent installer archive refused' }
    $parent = $file.Directory.FullName
    $references = @($processes | Where-Object { ($_.CommandLine -and $_.CommandLine.IndexOf($parent, [StringComparison]::OrdinalIgnoreCase) -ge 0) -or ($_.ExecutablePath -and $_.ExecutablePath.StartsWith($parent, [StringComparison]::OrdinalIgnoreCase)) })
    if ($references.Count -ne 0) { throw 'Installer process still refers to archive directory' }
    $stream = [IO.File]::Open($source, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::None)
    try {
        $hasher = [Security.Cryptography.SHA256]::Create()
        try { $digest = [BitConverter]::ToString($hasher.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
        finally { $hasher.Dispose() }
    } finally { $stream.Dispose() }
    $entries += [PSCustomObject]@{Source=$source;Destination=(Join-Path $destinationRoot $name);Bytes=$file.Length;SHA256=$digest;LastWriteTimeUtc=$file.LastWriteTimeUtc.ToString('o');ProcessReferences=0;ExclusiveReadSucceeded=$true;Moved=$false}
}
New-Item -ItemType Directory -Path $destinationRoot | Out-Null
$manifest = Join-Path $destinationRoot 'manifest.json'
$entries | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $manifest -Encoding UTF8
foreach ($entry in $entries) {
    New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($entry.Destination)) | Out-Null
    Move-Item -LiteralPath $entry.Source -Destination $entry.Destination
    if ((Get-FileHash -LiteralPath $entry.Destination -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.SHA256) { throw 'Moved archive hash mismatch' }
    if (Test-Path -LiteralPath $entry.Source) { throw 'Source still exists' }
    $entry.Moved = $true
    $entries | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $manifest -Encoding UTF8
}
[PSCustomObject]@{MovedFiles=$entries.Count;PreservedBytes=($entries | Measure-Object Bytes -Sum).Sum;Manifest=$manifest;CFreeBytes=(Get-PSDrive C).Free} | ConvertTo-Json -Compress
