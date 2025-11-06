# run_blockchain.ps1

# Fonction pour afficher proprement les transactions
function Show-Transactions($transactions) {
    foreach ($tx in $transactions) {
        Write-Host "Sender: $($tx.sender), Recipient: $($tx.recipient), Amount: $($tx.amount)" -ForegroundColor Cyan
    }
}

# Affiche la blockchain initiale
Write-Host "`nBlockchain initiale:" -ForegroundColor Green
$chain = Invoke-RestMethod -Uri "http://localhost:5000/chain" -Method Get
foreach ($block in $chain.chain) {
    Write-Host "Bloc Index: $($block.index), Hash: $($block.hash), Previous Hash: $($block.previous_hash)"
    Show-Transactions $block.transactions
}

# Transactions à ajouter
$transactions = @(
    @{ sender = "Alice"; recipient = "Bob"; amount = 10 },
    @{ sender = "Bob"; recipient = "Charlie"; amount = 5 },
    @{ sender = "Charlie"; recipient = "Alice"; amount = 3 }
)

$blockIndex = 1
foreach ($tx in $transactions) {
    $txJson = $tx | ConvertTo-Json
    $response = Invoke-RestMethod -Uri "http://localhost:5000/transactions/new" -Method Post -Body $txJson -ContentType "application/json"
    Write-Host $response.message -ForegroundColor Cyan

    # Minage
    Write-Host "Minage en cours pour le bloc $blockIndex..." -ForegroundColor Yellow
    $mineResponse = Invoke-RestMethod -Uri "http://localhost:5000/mine" -Method Get
    Write-Host "Bloc miné avec succès : Index $($mineResponse.block.index), Hash $($mineResponse.block.hash)" -ForegroundColor Green

    $blockIndex++
}

# Affiche la blockchain complète après minage
Write-Host "`nBlockchain complète:" -ForegroundColor Green
$chain = Invoke-RestMethod -Uri "http://localhost:5000/chain" -Method Get
foreach ($block in $chain.chain) {
    Write-Host "Bloc Index: $($block.index), Hash: $($block.hash), Previous Hash: $($block.previous_hash)"
    Show-Transactions $block.transactions
}

# Validation de la blockchain
Write-Host "`nValidation de la blockchain:" -ForegroundColor Green
$validate = Invoke-RestMethod -Uri "http://localhost:5000/validate" -Method Get
Write-Host "$($validate.message)  Valid: $($validate.valid)" -ForegroundColor Magenta
