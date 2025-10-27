# List documents, pick the most recent, run enrich and fetch results
$base = 'http://127.0.0.1:8000'
try {
    $list = Invoke-RestMethod -Uri ($base + '/api/v1/documents') -TimeoutSec 10
} catch {
    Write-Output "ERROR: could not list documents: $($_.Exception.Message)"
    exit 2
}
if (-not $list.documents -or $list.documents.Count -eq 0) {
    Write-Output "No documents found in the backend. Please upload one and retry."
    exit 0
}
$doc = $list.documents[0]
$docid = $doc.id
Write-Output "Selected docid=$docid filename=$($doc.filename) status=$($doc.status)"
try {
    Write-Output "POST $base/api/v1/documents/$docid/enrich"
    $r = Invoke-RestMethod -Method Post -Uri ($base + "/api/v1/documents/$docid/enrich") -TimeoutSec 120
    $r | ConvertTo-Json -Depth 6 | Write-Output
} catch {
    Write-Output "enrich failed: $($_.Exception.Message)"
}
try {
    Start-Sleep -Seconds 1
    Write-Output "GET $base/api/v1/documents/$docid/results"
    $s = Invoke-RestMethod -Uri ($base + "/api/v1/documents/$docid/results") -TimeoutSec 60
    $s | ConvertTo-Json -Depth 10 | Write-Output
    # compact summary
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
