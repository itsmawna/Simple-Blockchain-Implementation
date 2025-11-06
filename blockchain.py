import hashlib
import json
import time
from flask import Flask, jsonify, request
from urllib.parse import urlparse
import requests

# ==================== CLASSES ====================

class Block:
    """Class representing a block in the blockchain"""
    def __init__(self, index, transactions, timestamp, previous_hash, nonce=0):
        self.index = index
        self.transactions = transactions
        self.timestamp = timestamp
        self.previous_hash = previous_hash
        self.nonce = nonce
        self.hash = self.calculate_hash()

    def calculate_hash(self):
        """# Calculate the SHA256 hash of the block"""
        block_string = json.dumps({
            "index": self.index,
            "transactions": self.transactions,
            "timestamp": self.timestamp,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce
        }, sort_keys=True)
        return hashlib.sha256(block_string.encode()).hexdigest()

    def mine_block(self, difficulty):
        """Mine the block with the specified difficulty"""
        target = "0" * difficulty
        while not self.hash.startswith(target):
            self.nonce += 1
            self.hash = self.calculate_hash()
        print(f"Block mined: {self.hash}")

    def to_dict(self):
        """Convert the block to a dictionary"""
        return {
            "index": self.index,
            "transactions": self.transactions,
            "timestamp": self.timestamp,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
            "hash": self.hash
        }


class Blockchain:
    """Class representing the blockchain"""
    def __init__(self, difficulty=4, mining_reward=1):
        self.chain = []
        self.pending_transactions = []
        self.mining_reward = mining_reward
        self.difficulty = difficulty
        self.nodes = set()
        self.create_genesis_block()

    # ---------- Blocks ----------
    def create_genesis_block(self):
        genesis_block = Block(0, [], time.time(), "0")
        genesis_block.mine_block(self.difficulty)
        self.chain.append(genesis_block)

    def get_latest_block(self):
        return self.chain[-1]

    # ---------- Transactions ----------
    def add_transaction(self, sender, recipient, amount):
        tx = {
            "sender": sender,
            "recipient": recipient,
            "amount": amount,
            "timestamp": time.time()
        }
        self.pending_transactions.append(tx)
        return self.get_latest_block().index + 1

    # ---------- Mining + synchro ----------
    def mine_pending_transactions(self, miner_address):
        # 1) Before mining, update to avoid mining on an outdated chain
        self.resolve_conflicts()

        if not self.pending_transactions:
            print("No transactions to mine")
            return None

        # Snapshot for this block
        transactions_to_mine = self.pending_transactions.copy()

        # Adding the reward
        reward_tx = {
            "sender": "Network",
            "recipient": miner_address,
            "amount": self.mining_reward,
            "timestamp": time.time()
        }
        transactions_to_mine.append(reward_tx)

        new_block = Block(
            index=len(self.chain),
            transactions=transactions_to_mine,
            timestamp=time.time(),
            previous_hash=self.get_latest_block().hash
        )
        new_block.mine_block(self.difficulty)

        #  Adding the block
        self.chain.append(new_block)

        # # Remove only the mined transactions (excluding the reward which was not in the queue)
        self.pending_transactions = [
            tx for tx in self.pending_transactions if tx not in transactions_to_mine
        ]

        # 2) After mining: request all neighbors to resolve consensus
        self.broadcast_resolve()

        return new_block

    # ---------- Validation ----------
    def is_chain_valid(self, chain=None):
        if chain is None:
            chain = self.chain

        #Block 0 must be a consistent "genesis" block
        if len(chain) == 0:
            return False

        for i in range(1, len(chain)):
            current = chain[i]
            previous = chain[i - 1]

            # Recalculate the hash and verify the Proof of Work (PoW)
            if current.hash != current.calculate_hash():
                print(f" Invalid hash for the block {i}")
                return False
            if current.previous_hash != previous.hash:
                print(f"Invalid chain at block {i}")
                return False
            if not current.hash.startswith("0" * self.difficulty):
                print(f"Invalid proof of work for the block {i}")
                return False

        return True

    # ---------- Network ----------
    @staticmethod
    def _normalize_address(address: str) -> str:
        """
        Normalize a potential address: accepts
        - 'http://host:port' / 'https://host:port'
        - 'host:port'
        - 'host' (in this case, the default port 5000 is assumed)
        Returns 'host:port'
        """
        address = address.strip().rstrip('/')
        parsed = urlparse(address if "://" in address else f"http://{address}")
        host = parsed.hostname
        port = parsed.port if parsed.port else 5000
        if not host:
            raise ValueError("invalid URL")
        return f"{host}:{port}"

    def register_node(self, address):
        """
        Adds a neighboring node to self.nodes.
        - Supports 'http(s)://host:port', 'host:port', 'host'
        - Automatically deduplicates using set()
        """
        normalized = self._normalize_address(address)
        self.nodes.add(normalized)

    def get_chain_from_node(self, node):
        """
        Retrieves the full blockchain from a remote node and reconstructs it as a list of Block objects.
        Returns (length, chain_as_blocks) or (None, None) if retrieval fails.
        """
        try:
            # Default to HTTP (useful for our local test labs)
            url = f"http://{node}/chain" if not node.startswith("http") else f"{node.rstrip('/')}/chain"
            resp = requests.get(url, timeout=5)
            if resp.status_code != 200:
                return (None, None)
            data = resp.json()
            chain_dicts = data.get("chain", [])
            # Reconstruct into Block objects
            chain_blocks = [self.dict_to_block(b) for b in chain_dicts]
            return (len(chain_blocks), chain_blocks)
        except requests.exceptions.RequestException as e:
            print(f" Error contacting {node}: {e}")
            return (None, None)
        except Exception as e:
            print(f"Unexpected response from {node}: {e}")
            return (None, None)

    def resolve_conflicts(self):
        """
        Consensus algorithm:
        - Iterate over all neighbor chains
        - Select the longest AND valid chain
        - Replace local chain if a better one is found
        """
        max_length = len(self.chain)
        new_chain = None

        for node in list(self.nodes):
            length, candidate_chain = self.get_chain_from_node(node)
            if not length or not candidate_chain:
                continue

            if length > max_length and self.is_chain_valid(candidate_chain):
                max_length = length
                new_chain = candidate_chain

        if new_chain:
            self.chain = new_chain
            print("Chain replaced by a longer valid chain from the network.")
            return True

        print("No replacement: our chain remains authoritative.")
        return False

    def broadcast_resolve(self):
        """
        Ask each neighbor to trigger their /nodes/resolve
        so that the entire network converges after a local mining.
        """
        for node in list(self.nodes):
            try:
                url = f"http://{node}/nodes/resolve" if not node.startswith("http") else f"{node.rstrip('/')}/nodes/resolve"
                requests.get(url, timeout=5)
            except requests.exceptions.RequestException:
                # Ignore network errors to avoid blocking execution
                pass

    # ---------- Utilities ----------
    def dict_to_block(self, block_dict):
        block = Block(
            block_dict['index'],
            block_dict['transactions'],
            block_dict['timestamp'],
            block_dict['previous_hash'],
            block_dict['nonce']
        )
        # The constructor already computes a hash, but we enforce the received one
        block.hash = block_dict['hash']
        return block

    def to_dict(self):
        return [block.to_dict() for block in self.chain]


# ==================== API FLASK ====================

app = Flask(__name__)
blockchain = Blockchain()
node_identifier = "node_1"


@app.route('/mine', methods=['GET'])
def mine():
    block = blockchain.mine_pending_transactions(node_identifier)
    if block is None:
        return jsonify({"message": "No transactions to mine"}), 400
    return jsonify({'message': 'Block successfully mined', 'block': block.to_dict()}), 200


@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()
    required = ['sender', 'recipient', 'amount']
    if not values or not all(k in values for k in required):
        return 'Missing values', 400
    index = blockchain.add_transaction(values['sender'], values['recipient'], values['amount'])
    return jsonify({'message': f'Transaction added to the block {index}'}), 201


@app.route('/chain', methods=['GET'])
def full_chain():
    return jsonify({'chain': blockchain.to_dict(), 'length': len(blockchain.chain)}), 200


@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()
    nodes = values.get('nodes')
    if not nodes or not isinstance(nodes, list):
        return "Error: Please provide a list of nodes", 400

    for node in nodes:
        try:
            blockchain.register_node(node)
        except ValueError:
            return f"Invalid URL: {node}", 400

    return jsonify({'message': 'Nodes addes', 'total_nodes': list(blockchain.nodes)}), 201


@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()
    if replaced:
        return jsonify({'message': 'Our chain has been replaced', 'new_chain': blockchain.to_dict()}), 200
    else:
        return jsonify({'message': 'Our chain is authoritative', 'chain': blockchain.to_dict()}), 200


@app.route('/pending', methods=['GET'])
def pending_transactions():
    return jsonify({'transactions': blockchain.pending_transactions, 'count': len(blockchain.pending_transactions)}), 200

@app.route('/validate', methods=['GET'])
def validate_chain():
    is_valid = blockchain.is_chain_valid()
    message = "The blockchain is valid" if is_valid else "the blockchain is not valid"
    return jsonify({'message': message, 'valid': is_valid}), 200



if __name__ == '__main__':
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=5000, type=int, help='Port à écouter')
    parser.add_argument('--node-id', default='node_1', help="Identifiant logique du mineur local")
    args = parser.parse_args()
    node_identifier = args.node_id
    app.run(host='0.0.0.0', port=args.port, debug=True)
