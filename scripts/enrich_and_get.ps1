# Wait for backend health and then call enrich + get results for a specific document
$docId = '0d7543d0-29b9-477b-bed7-a1a382145bb0'
$base = 'http://127.0.0.1:8000'
$health = "$base/health"
$maxWait = 60
for ($i=0;$i -lt $maxWait;$i++) {
    try {
        $r = Invoke-RestMethod -Uri $health -TimeoutSec 2
        if ($r.status -eq 'healthy') { Write-Output "backend healthy"; break }
    } catch { Start-Sleep -Seconds 1 }
}

# Enrich
$enrichUrl = "$base/api/v1/documents/$docId/enrich"
try {
    Write-Output "POST $enrichUrl"
    $res = Invoke-RestMethod -Method Post -Uri $enrichUrl -TimeoutSec 120
    $res | ConvertTo-Json -Depth 6 | Write-Output
} catch {
    Write-Output "enrich failed: $($_.Exception.Message)"
}

# Get results
$getUrl = "$base/api/v1/documents/$docId/results"
try {
    Write-Output "GET $getUrl"
    $s = Invoke-RestMethod -Uri $getUrl -TimeoutSec 60
    $s | ConvertTo-Json -Depth 10 | Write-Output
    # Print a compact summary
    try {
        $ed = $s.extracted_data
        $val = $s.aggregates.valor_total_calc
        Write-Output "SUMMARY: valor_total_calc=$val; items_count=$($ed.itens.Count)"
        if ($ed.itens) {
            foreach ($it in $ed.itens) {
                Write-Output ("ITEM: descricao='" + ($it.descricao -replace "\n"," ") + "' quantidade=$($it.quantidade) valor_unitario=$($it.valor_unitario) valor_total=$($it.valor_total)")
            }
        }
    } catch { }
} catch {
    Write-Output "get failed: $($_.Exception.Message)"
}
