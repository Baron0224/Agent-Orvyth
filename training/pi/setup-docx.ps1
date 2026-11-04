$ErrorActionPreference = 'Stop'
$version = 'v0.27.0'
$destination = Join-Path $env:LOCALAPPDATA "Orvyth\tools\docx-cli\$version"
New-Item -ItemType Directory -Force -Path $destination | Out-Null
$release = "https://github.com/kklimuk/docx-cli/releases/download/$version"
$download = Join-Path $destination 'docx-windows-x64.exe.download'
Invoke-WebRequest "$release/SHA256SUMS" -OutFile (Join-Path $destination 'SHA256SUMS')
Invoke-WebRequest "$release/docx-windows-x64.exe" -OutFile $download
$entry = Get-Content (Join-Path $destination 'SHA256SUMS') | Where-Object { $_ -match '\sdocx-windows-x64\.exe$' }
if (-not $entry -or (Get-FileHash -Algorithm SHA256 $download).Hash.ToLowerInvariant() -ne ($entry -split '\s+')[0]) {
    throw 'docx-cli 校验失败，未安装。'
}
Move-Item -LiteralPath $download -Destination (Join-Path $destination 'docx.exe') -Force
& (Join-Path $destination 'docx.exe') --version
