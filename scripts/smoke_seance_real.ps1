$body = @{ path = 'concepts/mcp-server.md' } | ConvertTo-Json
try {
  $r = Invoke-RestMethod -Uri 'http://127.0.0.1:7777/api/summon' -Method Post -Body $body -ContentType 'application/json' -TimeoutSec 30
  Write-Output "summon ok, session=$($r.session_id) era=$($r.persona.era_marker)"
  $say = @{ session_id = $r.session_id; text = 'wer bist du in einem satz?' } | ConvertTo-Json
  $r2 = Invoke-RestMethod -Uri 'http://127.0.0.1:7777/api/say' -Method Post -Body $say -ContentType 'application/json' -TimeoutSec 60
  Write-Output "reply: $($r2.reply)"
} catch {
  Write-Output "FAIL: $_"
}
