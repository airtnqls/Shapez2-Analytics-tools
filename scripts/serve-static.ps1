param(
  [int]$Port = 4173,
  [switch]$Open
)

$ErrorActionPreference = "Stop"
$Root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\out"))
$Address = [System.Net.IPAddress]::Parse("127.0.0.1")
$Listener = [System.Net.Sockets.TcpListener]::new($Address, $Port)
$Mime = @{
  ".html" = "text/html; charset=utf-8"
  ".js" = "application/javascript; charset=utf-8"
  ".css" = "text/css; charset=utf-8"
  ".json" = "application/json; charset=utf-8"
  ".webmanifest" = "application/manifest+json"
  ".svg" = "image/svg+xml"
  ".png" = "image/png"
  ".jpg" = "image/jpeg"
  ".jpeg" = "image/jpeg"
  ".gz" = "application/gzip"
  ".txt" = "text/plain; charset=utf-8"
  ".wasm" = "application/wasm"
}

function Resolve-StaticPath([string]$RequestPath) {
  try { $Decoded = [System.Uri]::UnescapeDataString(($RequestPath -split '\?')[0]) }
  catch { return $null }
  $Relative = $Decoded.TrimStart('/', '\').Replace('/', [System.IO.Path]::DirectorySeparatorChar)
  if ([string]::IsNullOrWhiteSpace($Relative)) { $Relative = "index.html" }
  if ($Decoded.EndsWith('/')) { $Relative = Join-Path $Relative "index.html" }
  $Candidate = [System.IO.Path]::GetFullPath((Join-Path $Root $Relative))
  if (-not $Candidate.StartsWith($Root, [System.StringComparison]::OrdinalIgnoreCase)) { return $null }
  return $Candidate
}

function Write-Response($Stream, [int]$Status, [string]$StatusText, [byte[]]$Body, [string]$ContentType, [bool]$HeadOnly, [string]$CacheControl) {
  $Header = "HTTP/1.1 $Status $StatusText`r`n" +
    "Content-Type: $ContentType`r`n" +
    "Content-Length: $($Body.Length)`r`n" +
    "Cache-Control: $CacheControl`r`n" +
    "Cross-Origin-Opener-Policy: same-origin`r`n" +
    "Cross-Origin-Embedder-Policy: require-corp`r`n" +
    "X-Content-Type-Options: nosniff`r`n" +
    "Connection: close`r`n`r`n"
  $HeaderBytes = [System.Text.Encoding]::ASCII.GetBytes($Header)
  $Stream.Write($HeaderBytes, 0, $HeaderBytes.Length)
  if (-not $HeadOnly -and $Body.Length -gt 0) { $Stream.Write($Body, 0, $Body.Length) }
  $Stream.Flush()
}

try {
  $Listener.Start()
} catch {
  Write-Host "[ERROR] Port $Port could not be opened: $($_.Exception.Message)" -ForegroundColor Red
  Write-Host "Close the old server window or open http://127.0.0.1:$Port in your browser."
  exit 1
}

$Url = "http://127.0.0.1:$Port"
Write-Host "Shapez2 TMAM Studio 2.1.0: $Url" -ForegroundColor Cyan
Write-Host "Static root: $Root"
Write-Host "Press Ctrl+C to stop."
if ($Open) { Start-Process $Url }

try {
  while ($true) {
    $Client = $Listener.AcceptTcpClient()
    try {
      $Stream = $Client.GetStream()
      $Reader = [System.IO.StreamReader]::new($Stream, [System.Text.Encoding]::ASCII, $false, 4096, $true)
      $RequestLine = $Reader.ReadLine()
      if ([string]::IsNullOrWhiteSpace($RequestLine)) { continue }
      do { $Line = $Reader.ReadLine() } while ($null -ne $Line -and $Line.Length -gt 0)
      $Parts = $RequestLine.Split(' ')
      if ($Parts.Length -lt 2 -or ($Parts[0] -ne 'GET' -and $Parts[0] -ne 'HEAD')) {
        $Body = [System.Text.Encoding]::UTF8.GetBytes('Method not allowed')
        Write-Response $Stream 405 'Method Not Allowed' $Body 'text/plain; charset=utf-8' $false 'no-cache'
        continue
      }
      $HeadOnly = $Parts[0] -eq 'HEAD'
      $File = Resolve-StaticPath $Parts[1]
      if ($null -eq $File -or -not [System.IO.File]::Exists($File)) {
        $Fallback = Join-Path $Root '404.html'
        $Body = if ([System.IO.File]::Exists($Fallback)) { [System.IO.File]::ReadAllBytes($Fallback) } else { [System.Text.Encoding]::UTF8.GetBytes('Not found') }
        Write-Response $Stream 404 'Not Found' $Body 'text/html; charset=utf-8' $HeadOnly 'no-cache'
        continue
      }
      $Body = [System.IO.File]::ReadAllBytes($File)
      $Extension = [System.IO.Path]::GetExtension($File).ToLowerInvariant()
      $ContentType = if ($Mime.ContainsKey($Extension)) { $Mime[$Extension] } else { 'application/octet-stream' }
      $PathOnly = ($Parts[1] -split '\?')[0]
      $Immutable = $PathOnly.StartsWith('/_next/static/') -or $PathOnly.StartsWith('/data/') -or $PathOnly -eq '/solver.worker.js'
      $Cache = if ($Immutable) { 'public, max-age=31536000, immutable' } else { 'no-cache' }
      Write-Response $Stream 200 'OK' $Body $ContentType $HeadOnly $Cache
    } catch {
      Write-Host "Request failed: $($_.Exception.Message)" -ForegroundColor Yellow
    } finally {
      $Client.Close()
    }
  }
} finally {
  $Listener.Stop()
}
