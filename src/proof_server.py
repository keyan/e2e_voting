import random
from typing import Dict, List, Tuple

from src import sv_vote
from src import sbb
from src import util

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding


class ProofServer:
    """
    ProofServer (henceforth PS), abtracts a mix-net of NxN servers arranged in a matrix.
    The function of the PS is to obfuscate and shuffle split-value-representations of
    ballots before posting to the SBB.
    """
    def __init__(self, M: int, twoM: int, rows: int, sbb: sbb.SBB):
        self._M = M
        self._twoM = twoM
        self._sbb = sbb
        self._generate_key_pair()
        # We implicitly let rows == columns.
        self._rows = rows
        self._tablet_decoders: Dict[str, Fernet] = {}
        self._incoming_vote_rows: List[List[sv_vote.SVVote]] = []

        for _ in range(self._rows):
            self._incoming_vote_rows.append([])

        # Only set after mixing is initiated.
        self._num_votes: int = 0

        # Keep state for each permutation array used for each column in each
        # iteration of mixing (2m total iterations). This is used to recompute
        # the original ballot order for step #7 "Proving consistency with cast
        # votes" (Section I).
        #   - list[i] contains the permutations used during round i of mixing
        #   - list[i][j] " " for the j'th column
        self._permutation_arrays: List[List[List[int]]] = []

    def _generate_key_pair(self):
        """
        Generate a RSA public/private key-pair once at initialization.

        The public key is provided to each tablet when they register with the proof server,
        allowing the tablet to securely share their private symmetric key.

        TODO - consider giving all mix-servers their own keys.
        In the paper each mix-server in the PS has its own key-pair, but for now we relax this
        requirement for the sake of simplifying the PS implementation.
        """
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
        """
        Each initialized tablet must call this function in order to securely
        share its private symmetric key with the PS. This allows for secure
        ballot transmission later.
        """
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
            raise Exception('Tablet failed to register', e)

    def get_public_key(self):
        return self._public_key_bytes

    def get_num_rows(self) -> int:
        return self._rows

    def handle_vote(self, sv_vote: sv_vote.SVVote):
        if sv_vote.proof_server_row is None:
            raise Exception('Cannot handle vote without valid proof_server_row')
        self._incoming_vote_rows[sv_vote.proof_server_row].append(sv_vote)

    def publish_vote_consistency_proof(self) -> None:
        """
        Step #7 from Section I.
        """
        pass

    #
    # Proof server mixing implementation
    #
    def _validate_stored_votes(self) -> None:
        """
        Check that stored vote counts are consistent.
        """
        assert len(self._incoming_vote_rows) == self._rows
        num_votes = {len(votes) for votes in self._incoming_vote_rows}
        assert len(num_votes) == 1, 'All rows should have equal number of votes'
        self._num_votes = num_votes.pop()

    def _mix_round(self) -> None:
        """
        Run one round of randomized vote mixing.

        Follows heading names used in Section VII. When operations are repeated
        across each row, that row is responsible for just one component of the
        SVR for the original ballot.

        In the standard 3x3 PS topology this means:
            row 0 -> x
            row 1 -> y
            row 2 -> z
        """
        # Each row retains a list of length _num_votes components of the ballot.
        # Originally this list will correspond to the true order votes were made,
        # after each stage of obfuscation+shuffling the list represents the current
        # state of the row.
        row_values: List[List[int]] = []

        # Keep all 3 permutation arrays used to add to state later.
        permutation_arrays: List[List[int]] = []

        # Decryption - each server in the first column must decrypt the encrypted
        # SVR component for all votes given to it, and confirm it matches the provided
        # commitments. This ensures man-in-the-middle attacks are avoided.
        for row in range(self._rows):
            # One int per vote, at the end this is e.g. (x_1, ..., x_n).
            vote_components: List[int] = []
            votes = self._incoming_vote_rows[row]

            for vote in votes:
                decoder = self._tablet_decoders[vote.tablet_id]
                plaintext_com: sv_vote.PlaintextCom = vote.enc.decode(decoder)
                if (util.get_COM(plaintext_com.k1, plaintext_com.u) != vote.com_u or
                    util.get_COM(plaintext_com.k2, plaintext_com.v) != vote.com_v):
                    raise Exception('Commitment validation failed')

                component_value = util.val(
                    util.bytes_to_bigint(plaintext_com.u),
                    util.bytes_to_bigint(plaintext_com.v),
                    self._M,
                )
                vote_components.append(component_value)

            assert len(vote_components) == self._num_votes
            row_values.append(vote_components)

        # Obfuscation and shuffling - done once per column.
        for col in range(self._rows):
            # Row 0 generates both obfuscation tuples (explained below) and a
            # random permutation for shuffling, these lists are shared with the
            # other rows. Normally this would be done with secure encrypted
            # communication between the servers.
            pi = list(range(self._num_votes))
            random.shuffle(pi)
            permutation_arrays.append(pi)

            # An obfuscation is a tuple (p, q, r) where (p + q + r) mod M = 0,
            # for each vote. And shares these with the other rows. These are
            # used to obfuscate the vote components by computing, e.g.
            # x' = (p + x) mod M. Note the new value of (x', y', z') is
            # still equal to the original vote.
            obfuscation_tuples: List[List[int]] = [
                util.get_SV_multiple(0, self._rows, self._M)
                for _ in range(self._num_votes)
            ]

            # Create one list for each component (p, q, r) so they can be shared
            # with the appropriate row.
            obfuscation_lists = list(zip(*obfuscation_tuples))

            for row in range(self._rows):
                # Obfuscate
                obfuscation_list = obfuscation_lists[row]
                obfuscated_components = [
                    util.val(u, p, self._M)
                    for (u, p) in zip(obfuscation_list, row_values[row])
                ]
                # Shuffle - all servers in this column use the same shuffle permutation.
                # This reassignment takes the place of secure server transfer, instead
                # the latest component values states are kept in this list.
                row_values[row][:] = [obfuscated_components[i] for i in pi]

        self._permutation_arrays.append(permutation_arrays)

        # Post lists of votes - last column creates and posts SVR commitments for
        # each value in the array of ballot components it contains.
        for row in range(self._rows):
            pass

    def mix_votes(self) -> None:
        """
        Mix votes according to Section VII.

        Implements 2m rounds of randomized vote obfuscation and shuffling across
        all PS rows and columns. Each of the 2m rounds produces 1 of the eventually
        2m lists posted to the SBB.
        """
        self._validate_stored_votes()

        for _ in range(self._twoM):
            self._mix_round()

        assert len(self._permutation_arrays) == self._twoM
