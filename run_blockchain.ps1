# run_blockchain.ps1

# Function to neatly display transactions
function Show-Transactions($transactions) {
    foreach ($tx in $transactions) {
        Write-Host "Sender: $($tx.sender), Recipient: $($tx.recipient), Amount: $($tx.amount)" -ForegroundColor Cyan
    }
}

# Display the initial blockchain
Write-Host "`nBlockchain initiale:" -ForegroundColor Green
$chain = Invoke-RestMethod -Uri "http://localhost:5000/chain" -Method Get
foreach ($block in $chain.chain) {
    Write-Host "Bloc Index: $($block.index), Hash: $($block.hash), Previous Hash: $($block.previous_hash)"
    Show-Transactions $block.transactions
}

# Transactions to be added
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

    # Mining
    Write-Host "Mining in progress for the block $blockIndex..." -ForegroundColor Yellow
    $mineResponse = Invoke-RestMethod -Uri "http://localhost:5000/mine" -Method Get
    Write-Host "Block successfully mined : Index $($mineResponse.block.index), Hash $($mineResponse.block.hash)" -ForegroundColor Green

    $blockIndex++
}

# Display the complete blockchain after mining
Write-Host "`nComplete blockchain:" -ForegroundColor Green
$chain = Invoke-RestMethod -Uri "http://localhost:5000/chain" -Method Get
foreach ($block in $chain.chain) {
    Write-Host "Block Index: $($block.index), Hash: $($block.hash), Previous Hash: $($block.previous_hash)"
    Show-Transactions $block.transactions
}

# Blockchain validation
Write-Host "`nBlockchain validation:" -ForegroundColor Green
$validate = Invoke-RestMethod -Uri "http://localhost:5000/validate" -Method Get
Write-Host "$($validate.message)  Valid: $($validate.valid)" -ForegroundColor Magenta
