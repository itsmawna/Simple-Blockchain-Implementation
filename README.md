# Simple Decentralized Blockchain  

## Overview  
This project implements a **basic blockchain system** featuring:  
- Transaction management  
- Proof of Work (PoW) mining  
- Blockchain validation and integrity check  
- Node registration and **consensus resolution** for decentralization  

Built with **Python** and **Flask**, and tested via **PowerShell automation scripts**.

---

## Features  
- Add and manage transactions  
- Mine blocks with Proof of Work  
- Validate blockchain integrity  
- Register multiple nodes  
- Reach consensus across nodes (longest valid chain rule) 
---
## Execution 

### 1️. Start the Python Blockchain Node(s)  
Run the Python server(s):  
```bash
python blockchain.py -p 5000 --node-id node_A
```
### 2. Start more nodes for testing decentralization:
```bash
python blockchain.py -p 5001 --node-id node_B
```

```bash
python blockchain.py -p 5002 --node-id node_C
```

### 3. Run the PowerShell Script
#### Test local blockchain
After the servers are running, execute the automation script:

```powershell
.\run_blockchain.ps1
```
#### Test decentralization & consensus
For decentralization and consensus testing:

```powershell
.\test_blockchain.ps1
```

These scripts automatically:

* Add and broadcast transactions between nodes
* Mine new blocks using Proof of Work
* Display blockchain content after each block is mined
* Resolve conflicts and synchronize nodes through consensus
* Validate the integrity of all chains


---

## Results

### Local Test (`run_blockchain.ps1`)

* Blockchain starts with the genesis block (Index 0)
* New transactions are added (e.g., Alice → Bob, Bob → Charlie)
* Each block mined includes the miner reward (Network → node_A: 1)
* Final blockchain shows all blocks correctly linked and validated

Example Output:

```
Index: 0, Hash: 0000a3f...
Transactions: []

Index: 1, Hash: 000056b...
Transactions: Alice → Bob, Network → node_A: 1

Blockchain valid: True
```

### Decentralization Test (`test_blockchain.ps1`)

* Three nodes (5000, 5001, 5002) start independently
* Each node mines different blocks → conflict occurs
* Consensus algorithm is triggered → all nodes adopt the longest valid chain
* Synchronization complete: every node has the same blocks

Final Output:

```
Node 5000 -> Blocks: 4 | Valid: True
Node 5001 -> Blocks: 4 | Valid: True
Node 5002 -> Blocks: 4 | Valid: True
```

Decentralization test successful: All nodes are synchronized and the blockchain integrity is verified
