Start-Sleep -Seconds 3
try {
  $r = Invoke-WebRequest -Uri 'http://127.0.0.1:7777/api/pages' -TimeoutSec 5 -UseBasicParsing
  Write-Output "status: $($r.StatusCode)"
  $j = $r.Content | ConvertFrom-Json
  Write-Output "page count: $($j.Count)"
  if ($j.Count -gt 0) { Write-Output "first page: $($j[0].path)" }
} catch {
  Write-Output "FAIL: $_"
}
