# PowerShell helper to download a portable tesseract build into backend\tools\tesseract
param(
  [string]$Dest = "backend\tools\tesseract",
  [string]$Url = $env:TESSERACT_DOWNLOAD_URL
)

if (-not (Test-Path $Dest)) { New-Item -ItemType Directory -Path $Dest -Force | Out-Null }

if (-not $Url) {
  Write-Host "TESSERACT_DOWNLOAD_URL not set — trying to auto-detect latest UB-Mannheim release asset..."
  try {
    $rel = Invoke-RestMethod -Uri 'https://api.github.com/repos/UB-Mannheim/tesseract/releases/latest' -UseBasicParsing
    $asset = $rel.assets | Where-Object { $_.name -match '(?i)w64|win|windows|portable|zip|exe' } | Select-Object -First 1
    if ($asset) { $Url = $asset.browser_download_url }
  } catch {
    Write-Host "Failed to query GitHub releases: $_"
  }
  if (-not $Url) {
    Write-Host "Could not auto-detect a UB-Mannheim asset. Please set TESSERACT_DOWNLOAD_URL to a download URL (see https://github.com/UB-Mannheim/tesseract/releases)."
    exit 1
  }
}

$destFile = Join-Path $env:TEMP (Split-Path $Url -Leaf)
Write-Host "Downloading $Url -> $destFile"

Invoke-WebRequest -Uri $Url -OutFile $destFile -UseBasicParsing

# Try to extract zip
if ($destFile -like "*.zip") {
  Add-Type -AssemblyName System.IO.Compression.FileSystem
  [System.IO.Compression.ZipFile]::ExtractToDirectory($destFile, $Dest)
  Remove-Item $destFile
  Write-Host "Extracted zip to $Dest"
} else {
  # If it's an installer executable, just save it and instruct user how to proceed
  Write-Host "Downloaded file saved to $destFile. If this is an installer (exe) run it or extract its contents into $Dest."
}

Write-Host "If needed, ensure backend\tools\tesseract\tesseract.exe exists and is executable."
