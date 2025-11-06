# --- TEST DECENTRALISATION ET CONFLIT AVEC DÉTAILS ---
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "`n=== TEST DECENTRALISATION ===" -ForegroundColor Cyan

$ports = 5000,5001,5002

function Invoke-ConsensusAll {
    param([int[]]$ports)
    foreach ($p in $ports) {
        try {
            $res = Invoke-RestMethod -Uri "http://localhost:$p/nodes/resolve" -Method Get
            Write-Host "Consensus $($p) -> $($res.message)" -ForegroundColor Green
        } catch {
            Write-Host ("Consensus échoué sur {0}: {1}" -f $p, $_.Exception.Message) -ForegroundColor Red
        }
    }
}

function Show-ChainDetails {
    param($chain, $node)
    Write-Host "`nNoeud $node - Détails de la blockchain:" -ForegroundColor Yellow
    foreach ($block in $chain.chain) {
        Write-Host "Index: $($block.index), Hash: $($block.hash), Nonce: $($block.nonce), Previous: $($block.previous_hash)" -ForegroundColor Cyan
        if ($block.transactions.Count -gt 0) {
            Write-Host "Transactions:" -ForegroundColor Green
            foreach ($tx in $block.transactions) {
                Write-Host ("  {0} -> {1} : {2}" -f $tx.sender, $tx.recipient, $tx.amount)
            }
        } else {
            Write-Host "Pas de transactions dans ce bloc." -ForegroundColor DarkGray
        }
    }
    Write-Host "Nombre total de blocs: $($chain.chain.Count)" -ForegroundColor Magenta
}

function Validate-Node {
    param($port)
    try {
        $res = Invoke-RestMethod -Uri "http://localhost:$port/validate" -Method Get
        Write-Host "Validation noeud $port -> Message: $($res.message), Valide: $($res.valid)" -ForegroundColor Green
    } catch {
        Write-Host ("Validation échouée sur {0}: {1}" -f $port, $_.Exception.Message) -ForegroundColor Red
    }
}

# --- 1) Etat initial ---
foreach ($p in $ports) {
    $chain = Invoke-RestMethod -Uri "http://localhost:$p/chain" -Method Get
    Show-ChainDetails -chain $chain -node $p
}

# --- 2) Transactions et minage sur 5000 ---
Write-Host "`n--- Creation de transactions sur le noeud 5000 ---" -ForegroundColor Cyan

$tx1 = @{ sender = "Alice"; recipient = "Bob"; amount = 20 } | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:5000/transactions/new" -Method Post -Body $tx1 -ContentType "application/json"
Write-Host "Minage du bloc 1 sur noeud 5000..." -ForegroundColor Yellow
Invoke-RestMethod -Uri "http://localhost:5000/mine" -Method Get

$tx2 = @{ sender = "Bob"; recipient = "Charlie"; amount = 10 } | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:5000/transactions/new" -Method Post -Body $tx2 -ContentType "application/json"
Write-Host "Minage du bloc 2 sur noeud 5000..." -ForegroundColor Yellow
Invoke-RestMethod -Uri "http://localhost:5000/mine" -Method Get

# Vérification du noeud 5000
$chain5000 = Invoke-RestMethod -Uri "http://localhost:5000/chain" -Method Get
Show-ChainDetails -chain $chain5000 -node 5000

# --- 3) Test de conflit sur 5002 ---
Write-Host "`n--- Test de conflit sur le noeud 5002 ---" -ForegroundColor Cyan
for ($i = 1; $i -le 3; $i++) {
    $txConflict = @{ sender = "User$i"; recipient = "UserX"; amount = $i * 5 } | ConvertTo-Json
    Invoke-RestMethod -Uri "http://localhost:5002/transactions/new" -Method Post -Body $txConflict -ContentType "application/json"
    Write-Host "Minage du bloc $i sur noeud 5002..." -ForegroundColor Yellow
    Invoke-RestMethod -Uri "http://localhost:5002/mine" -Method Get
}

$chain5002 = Invoke-RestMethod -Uri "http://localhost:5002/chain" -Method Get
Show-ChainDetails -chain $chain5002 -node 5002

# --- 4) Enregistrement des noeuds ---
Write-Host "`n--- Enregistrement des noeuds sur 5000/5001/5002 ---" -ForegroundColor Cyan
$nodesFor5000 = @{ nodes = @("http://localhost:5001","http://localhost:5002") } | ConvertTo-Json
$nodesFor5001 = @{ nodes = @("http://localhost:5000","http://localhost:5002") } | ConvertTo-Json
$nodesFor5002 = @{ nodes = @("http://localhost:5000","http://localhost:5001") } | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:5000/nodes/register" -Method Post -Body $nodesFor5000 -ContentType "application/json"
Invoke-RestMethod -Uri "http://localhost:5001/nodes/register" -Method Post -Body $nodesFor5001 -ContentType "application/json"
Invoke-RestMethod -Uri "http://localhost:5002/nodes/register" -Method Post -Body $nodesFor5002 -ContentType "application/json"

# --- 5) Synchroniser tous les noeuds ---
Write-Host "`n--- Synchronisation globale ---" -ForegroundColor Cyan
Invoke-ConsensusAll -ports $ports

# --- 6) Résultat final et validation ---
Write-Host "`n=== RESULTAT FINAL ===" -ForegroundColor Cyan
foreach ($p in $ports) {
    $chain = Invoke-RestMethod -Uri "http://localhost:$p/chain" -Method Get
    Show-ChainDetails -chain $chain -node $p
    Validate-Node -port $p
}

# --- 7) VALIDATION FINALE ---
Write-Host "`n=== VALIDATION FINALE DU TEST DECENTRALISATION ===" -ForegroundColor Cyan

$allValid = $true
$lengths = @()

foreach ($p in $ports) {
    $chain = Invoke-RestMethod -Uri "http://localhost:$p/chain" -Method Get
    $validation = Invoke-RestMethod -Uri "http://localhost:$p/validate" -Method Get

    Write-Host "Noeud $p -> Nombre de blocs: $($chain.chain.Count), Blockchain valide: $($validation.valid)" -ForegroundColor Yellow

    $lengths += $chain.chain.Count
    if (-not $validation.valid) { $allValid = $false }
}

# Vérifier si tous les nœuds ont la même longueur
$sameLength = ($lengths | Select-Object -Unique).Count -eq 1

if ($allValid -and $sameLength) {
    Write-Host "`nTest de décentralisation réussi : tous les nœuds sont synchronisés et valides. Nombre de blocs par nœud: $($lengths -join ', ')" -ForegroundColor Green
}
else {
    Write-Host "`nTest échoué : incohérence détectée entre les nœuds ou blockchain invalide. Nombre de blocs par nœud: $($lengths -join ', ')" -ForegroundColor Red
}

