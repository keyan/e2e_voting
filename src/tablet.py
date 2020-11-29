import json
import os
import uuid
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding

from src import proof_server
from src import sv_vote
from src import util


class Tablet:
    def __init__(self, srv: proof_server.ProofServer, M: int):
        self._srv = srv
        self._M = M
        self._generate_id()
        self._create_secret_key()
        self._register_with_srv()
        self._proof_srv_rows = srv.get_num_rows()

    def _generate_id(self):
        self._id = str(uuid.uuid4())

    def _create_secret_key(self):
        # Generate the secret key and encoder so that it doesn't need to be created for every vote.
        self._secret_key = Fernet.generate_key()
        self._encoder = Fernet(self._secret_key)

    def _register_with_srv(self):
        # Get the public key from the server and load into a usable key object
        pk = self._srv.get_public_key()
        public_key = serialization.load_pem_public_key(
            pk,
        )
        
        # Encrypt the symmetric secret key
        enc = public_key.encrypt(
            self._secret_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            )
        )
        
        # Register the tablet with the server so it has the secret key
        self._srv.register_tablet(self._id, enc)

    #
    # Voting-related code
    #
    def send_vote(self, vote_int: int):
        assert vote_int < self._M
        
        # TODO: use string votes and prime number generation?
        # vote_int = util.bytes_to_bigint(vote.encode())
        bid = os.urandom(32)
        
        # Voter gets a hash of the receipt at the end, which contains the ballot ID and the commitments.
        receipt = {
            'bid': util.bytes_to_bigint(bid),
            'commitments': {}
        }
        
        # These are the x, y, z from w = (x, y, z) mod M in the paper
        split_vote = util.get_SV_multiple(vote_int, self._proof_srv_rows, self._M)
        for row, val in enumerate(split_vote):
            vote = sv_vote.SVVote()
            vote.bid = bid
            vote.tablet_id = self._id
            vote.proof_server_row = row
            
            # Generate 2 random keys for the split-value representation
            K1 = os.urandom(16)
            K2 = os.urandom(16)
            
            # Create the commitment and set it on the vote. Together com_u and com_v make up ComSV in the paper
            u, v = util.get_SV(val, self._M)
            u_bytes = util.bigint_to_bytes(u)
            v_bytes = util.bigint_to_bytes(v)
            com_u = util.get_COM(K1, u_bytes)
            com_v = util.get_COM(K2, v_bytes)
            vote.com_u = com_u
            vote.com_v = com_v
            
            # Store the commitments in the receipt. Need to use int for it to be json serializable
            receipt['commitments'][row] = {'u': util.bytes_to_bigint(com_u), 'v': util.bytes_to_bigint(com_v)}
            
            # Encode the values (this is done as a concatenation in the paper, however it is easier to decode this way)
            enc = sv_vote.EncCom()
            enc.k1 = self._encoder.encrypt(K1)
            enc.k2 = self._encoder.encrypt(K2)
            enc.u = self._encoder.encrypt(u_bytes)
            enc.v = self._encoder.encrypt(v_bytes)
            vote.enc = enc
            
            # Send one vote per row to the proof servers
            self._srv.handle_vote(vote)

        # Hash the receipt and return to the voter
        receipt_str = json.dumps(receipt, sort_keys=True)
        receipt_hash = util.get_hash(receipt_str.encode())
        return bid, receipt_hash
