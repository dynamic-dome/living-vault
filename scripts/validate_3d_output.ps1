$f = 'C:\Users\domes\desktop\vault-3d.html'
$t = Get-Content $f -Raw
$nodeCount = ([regex]::Matches($t, '"path":')).Count
$infoMatch = [regex]::Match($t, '<div id="info">([^<]+)</div>')
$info = $infoMatch.Groups[1].Value
Write-Output "nodes JSON entries (path keys): $nodeCount"
Write-Output "info banner: $info"
Write-Output "file size KB: $([math]::Round((Get-Item $f).Length/1KB, 1))"
