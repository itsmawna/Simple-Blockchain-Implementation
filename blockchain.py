import hashlib
import json
import time
from flask import Flask, jsonify, request
from urllib.parse import urlparse
import requests

# ==================== CLASSES ====================

class Block:
    """Classe représentant un bloc dans la blockchain"""
    def __init__(self, index, transactions, timestamp, previous_hash, nonce=0):
        self.index = index
        self.transactions = transactions
        self.timestamp = timestamp
        self.previous_hash = previous_hash
        self.nonce = nonce
        self.hash = self.calculate_hash()

    def calculate_hash(self):
        """Calcule le hash SHA256 du bloc"""
        block_string = json.dumps({
            "index": self.index,
            "transactions": self.transactions,
            "timestamp": self.timestamp,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce
        }, sort_keys=True)
        return hashlib.sha256(block_string.encode()).hexdigest()

    def mine_block(self, difficulty):
        """Mine le bloc avec la difficulté spécifiée"""
        target = "0" * difficulty
        while not self.hash.startswith(target):
            self.nonce += 1
            self.hash = self.calculate_hash()
        print(f"Bloc miné: {self.hash}")

    def to_dict(self):
        """Convertit le bloc en dictionnaire"""
        return {
            "index": self.index,
            "transactions": self.transactions,
            "timestamp": self.timestamp,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
            "hash": self.hash
        }


class Blockchain:
    """Classe représentant la blockchain"""
    def __init__(self, difficulty=4, mining_reward=1):
        self.chain = []
        self.pending_transactions = []
        self.mining_reward = mining_reward
        self.difficulty = difficulty
        self.nodes = set()
        self.create_genesis_block()

    # ---------- Blocs ----------
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

    # ---------- Minage + synchro ----------
    def mine_pending_transactions(self, miner_address):
        # 1) Avant de miner, on se met à jour pour éviter de miner sur une chaîne obsolète
        self.resolve_conflicts()

        if not self.pending_transactions:
            print("Aucune transaction à miner")
            return None

        # snapshot pour ce bloc
        transactions_to_mine = self.pending_transactions.copy()

        # Ajout de la récompense
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

        # Ajout du bloc
        self.chain.append(new_block)

        # Retirer uniquement les TX minées (hors récompense qui n'était pas dans la file)
        self.pending_transactions = [
            tx for tx in self.pending_transactions if tx not in transactions_to_mine
        ]

        # 2) Après minage: on demande à tous les voisins de résoudre le consensus
        self.broadcast_resolve()

        return new_block

    # ---------- Validation ----------
    def is_chain_valid(self, chain=None):
        if chain is None:
            chain = self.chain

        # Le bloc 0 doit être un "genesis" cohérent
        if len(chain) == 0:
            return False

        for i in range(1, len(chain)):
            current = chain[i]
            previous = chain[i - 1]

            # Recalculer le hash et vérifier le POW
            if current.hash != current.calculate_hash():
                print(f"Hash invalide pour le bloc {i}")
                return False
            if current.previous_hash != previous.hash:
                print(f"Chaînage invalide au bloc {i}")
                return False
            if not current.hash.startswith("0" * self.difficulty):
                print(f"Preuve de travail invalide pour le bloc {i}")
                return False

        return True

    # ---------- Réseau ----------
    @staticmethod
    def _normalize_address(address: str) -> str:
        """
        Normalise un address potentiel : accepte
        - 'http://host:port' / 'https://host:port'
        - 'host:port'
        - 'host' (dans ce cas, on supposera port par défaut 5000)
        Retourne 'host:port'
        """
        address = address.strip().rstrip('/')
        parsed = urlparse(address if "://" in address else f"http://{address}")
        host = parsed.hostname
        port = parsed.port if parsed.port else 5000
        if not host:
            raise ValueError("URL invalide")
        return f"{host}:{port}"

    def register_node(self, address):
        """
        Ajoute un nœud voisin dans self.nodes.
        - Supporte 'http(s)://host:port', 'host:port', 'host'
        - Déduplique automatiquement via set()
        """
        normalized = self._normalize_address(address)
        self.nodes.add(normalized)

    def get_chain_from_node(self, node):
        """
        Récupère la blockchain complète d'un nœud distant et la
        reconstruit en liste de Block. Retourne (length, chain_as_blocks) ou (None, None) si échec.
        """
        try:
            # on accepte http par défaut (nos petits labs locaux)
            url = f"http://{node}/chain" if not node.startswith("http") else f"{node.rstrip('/')}/chain"
            resp = requests.get(url, timeout=5)
            if resp.status_code != 200:
                return (None, None)
            data = resp.json()
            chain_dicts = data.get("chain", [])
            # reconstruction en objets Block
            chain_blocks = [self.dict_to_block(b) for b in chain_dicts]
            return (len(chain_blocks), chain_blocks)
        except requests.exceptions.RequestException as e:
            print(f"Erreur en contactant {node}: {e}")
            return (None, None)
        except Exception as e:
            print(f"Réponse inattendue de {node}: {e}")
            return (None, None)

    def resolve_conflicts(self):
        """
        Algorithme de consensus :
        - parcourt toutes les chaînes des voisins
        - choisit la plus longue ET valide
        - remplace la chaîne locale si une meilleure est trouvée
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
            print("Chaîne remplacée par une plus longue valide provenant du réseau.")
            return True

        print("Aucun remplacement : notre chaîne reste autorité.")
        return False

    def broadcast_resolve(self):
        """
        Demande à chaque voisin de déclencher son /nodes/resolve,
        afin que tout le réseau converge après un minage local.
        """
        for node in list(self.nodes):
            try:
                url = f"http://{node}/nodes/resolve" if not node.startswith("http") else f"{node.rstrip('/')}/nodes/resolve"
                requests.get(url, timeout=5)
            except requests.exceptions.RequestException:
                # on ignore les erreurs réseau pour ne pas bloquer
                pass

    # ---------- Utilitaires ----------
    def dict_to_block(self, block_dict):
        block = Block(
            block_dict['index'],
            block_dict['transactions'],
            block_dict['timestamp'],
            block_dict['previous_hash'],
            block_dict['nonce']
        )
        # Le constructeur calcule déjà un hash, mais on impose celui reçu
        block.hash = block_dict['hash']
        return block

    def to_dict(self):
        return [block.to_dict() for block in self.chain]


# ==================== API FLASK ====================

app = Flask(__name__)
blockchain = Blockchain()

# Astuce: passer un ID de mineur via variable d'env ou paramètre CLI si tu veux.
node_identifier = "node_1"


@app.route('/mine', methods=['GET'])
def mine():
    block = blockchain.mine_pending_transactions(node_identifier)
    if block is None:
        return jsonify({"message": "Aucune transaction à miner"}), 400
    return jsonify({'message': 'Bloc miné avec succès', 'block': block.to_dict()}), 200


@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()
    required = ['sender', 'recipient', 'amount']
    if not values or not all(k in values for k in required):
        return 'Valeurs manquantes', 400
    index = blockchain.add_transaction(values['sender'], values['recipient'], values['amount'])
    return jsonify({'message': f'Transaction ajoutée au bloc {index}'}), 201


@app.route('/chain', methods=['GET'])
def full_chain():
    return jsonify({'chain': blockchain.to_dict(), 'length': len(blockchain.chain)}), 200


@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()
    nodes = values.get('nodes')
    if not nodes or not isinstance(nodes, list):
        return "Erreur: Veuillez fournir une liste de nœuds", 400

    for node in nodes:
        try:
            blockchain.register_node(node)
        except ValueError:
            return f"URL invalide: {node}", 400

    return jsonify({'message': 'Nœuds ajoutés', 'total_nodes': list(blockchain.nodes)}), 201


@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()
    if replaced:
        return jsonify({'message': 'Notre chaîne a été remplacée', 'new_chain': blockchain.to_dict()}), 200
    else:
        return jsonify({'message': 'Notre chaîne fait autorité', 'chain': blockchain.to_dict()}), 200


@app.route('/pending', methods=['GET'])
def pending_transactions():
    return jsonify({'transactions': blockchain.pending_transactions, 'count': len(blockchain.pending_transactions)}), 200

@app.route('/validate', methods=['GET'])
def validate_chain():
    is_valid = blockchain.is_chain_valid()
    message = "La blockchain est valide" if is_valid else "La blockchain est invalide"
    return jsonify({'message': message, 'valid': is_valid}), 200



if __name__ == '__main__':
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=5000, type=int, help='Port à écouter')
    parser.add_argument('--node-id', default='node_1', help="Identifiant logique du mineur local")
    args = parser.parse_args()
    node_identifier = args.node_id
    app.run(host='0.0.0.0', port=args.port, debug=True)
