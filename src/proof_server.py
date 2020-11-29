from typing import Dict, List

from src import sv_vote

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding


class ProofServer:
    def __init__(self, rows: int):
        self._generate_key_pair()
        self._rows = rows
        self._tablet_decoders: Dict[str, Fernet] = {}
        self._incoming_vote_rows: List[List[sv_vote.SVVote]] = []

        for _ in range(self._rows):
            self._incoming_vote_rows.append([])

    #
    # Proof server initialization
    #
    def _generate_key_pair(self):
        self._private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self._public_key = self._private_key.public_key()
        self._public_key_bytes = self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

    #
    # Public proof server functions/endpoints
    #
    def register_tablet(self, tablet_id: str, pk_encrypted_sk):
        try:
            tablet_secret_key = self._private_key.decrypt(
                pk_encrypted_sk,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                )
            )
            self._tablet_decoders[tablet_id] = Fernet(tablet_secret_key)
        except Exception as e:
            print("Tablet failed to register: %s" % e)

    def get_public_key(self):
        return self._public_key_bytes

    def get_num_rows(self) -> int:
        return self._rows

    def handle_vote(self, sv_vote: sv_vote.SVVote):
        if sv_vote.proof_server_row is None:
            raise Exception('Cannot handle vote without valid proof_server_row')
        self._incoming_vote_rows[sv_vote.proof_server_row].append(sv_vote)

    #
    # Proof server mixing implementation
    #
    def _publish_proof(self):
        pass

    def mix_votes(self):
        pass



