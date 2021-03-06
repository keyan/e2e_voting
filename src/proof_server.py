import copy
import random
from typing import Any, Dict, List, Set, Tuple

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
        
        # Keeps the original split-value representations of votes per server row.
        # This is later used for computing t-values.
        #   - list[i] contains the SV for all votes in server row i
        #   - list[i][j] contains the plaintext SVR for vote j
        self._initial_sv: List[List[sv_vote.PlaintextSVR]] = []

        # Keep state for each permutation array used for each column in each
        # iteration of mixing (2m total iterations). This is used to recompute
        # the original ballot order for step #7 "Proving consistency with cast
        # votes" (Section I).
        #   - list[i] contains the permutations used during round i of mixing
        #   - list[i][j] " " for the j'th column
        self._permutation_arrays: List[List[List[int]]] = []

        # Keep state for each commitment made to ComT SVRs for each row in each
        # iteration of mixing (2m total iterations). This is used to open `m`
        # of the commitments in each row during step #7 "Proving consistency
        # with cast votes" (Section I).
        #   - list[i] contains the commitments used during round i of mixing
        #   - list[i][j] " " for the last column of the j'th row
        self._commitment_arrays: List[List[List[sv_vote.PlaintextSVR]]] = []
        
        # Same as commitment arrays, except backtracked to unmix
        self._unmixed_commitment_arrays: List[List[List[sv_vote.PlaintextSVR]]] = []

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
        
    def _reverse_permutation(self, permutation: List[int], values: List[Any]):
        back_tracked: List[Any] = [None for _ in values]
        for i, val in enumerate(values):
            back_tracked[permutation[i]] = val
        return back_tracked
    
    def _unmix_commitments(self):
        """
        This function unmixes all final outputs, but does NOT de-obfuscate any of them.
        """
        commitment_arrays_unmixed = copy.deepcopy(self._commitment_arrays)
        for list_idx in range(self._twoM):
            for perm_array in reversed(self._permutation_arrays[list_idx]):
                for row, row_svrs in enumerate(commitment_arrays_unmixed[list_idx]):
                    un_mixed = self._reverse_permutation(perm_array, row_svrs)
                    commitment_arrays_unmixed[list_idx][row] = un_mixed
        self._unmixed_commitment_arrays = commitment_arrays_unmixed
        
    def _publish_t_values(self):
        """
        This also publishes the t-values per section II E, where u2 and v2 are the SV components
        after obfuscation (in the mixing step) and u1 and v1 are the original components.
        
        This is part of step #7 from Section I and is briefly mentioned in Section IX
        under "Proving consistency with cast votes"
        """
        self._sbb.post_start_tvalue_commitments()
        
        t_values: List[List[List[Dict[str, int]]]]= []
        for list_idx in range(self._twoM):
            row_list = []
            for row, final_svrs in enumerate(self._unmixed_commitment_arrays[list_idx]):
                vote_list = []
                initial_svrs = self._initial_sv[row]
                assert len(initial_svrs) == len(final_svrs)
                for vote_idx in range(len(initial_svrs)):
                    initial_sv = initial_svrs[vote_idx]
                    final_sv = final_svrs[vote_idx]
                    tu = util.t_val(initial_sv.u, final_sv.u, self._M)
                    tv = util.t_val(initial_sv.v, final_sv.v, self._M)
                    vote_list.append({'tu': tu, 'tv': tv})
                row_list.append(vote_list)
            t_values.append(row_list)
        self._sbb.post_tvalue_commitments(t_values)
            
    def publish_vote_consistency_proof(self, proof_lists: Set[int], select_u_v: List[int]) -> None:
        """
        Publishes the arrays in the order of ballots received, by backtracking the permutation.
        The select_u_v list is the same size as number of votes, and determines whether the "u"
        or the "v" component is opened and returned.
        
        Step #7 from Section I.
        """
        self._sbb.post_start_consistency_proof()
        
        list_indices = sorted(list(proof_lists))
        for list_idx in list_indices:
            svrs: List[List[Dict[str, int]]] = [[] for _ in range(self._num_votes)]
            for row, row_svrs in enumerate(self._unmixed_commitment_arrays[list_idx]):
                for vote_idx, svr in enumerate(row_svrs):
                    # From the paper: "Now the randomness is used to open one coordinate in each
                    # of the commitments in the posted concealed ballots and the
                    # corresponding commitment in each of the m rearranged arrays."
                    # This means that we post the initial ballot u/v and k, and the obfuscated
                    # u/v and k (that corresponds to the same ballot.)
                    if select_u_v[vote_idx] == 0:
                        svrs[vote_idx].append({
                            'u': util.bytes_to_bigint(svr.u),
                            'k': util.bytes_to_bigint(svr.k1),
                            'u_init': util.bytes_to_bigint(self._initial_sv[row][vote_idx].u),
                            'k_init': util.bytes_to_bigint(self._initial_sv[row][vote_idx].k1),
                            'u_fin': util.bytes_to_bigint(self._commitment_arrays[list_idx][row][vote_idx].u),
                            'k_fin': util.bytes_to_bigint(self._commitment_arrays[list_idx][row][vote_idx].k1),
                        })
                    else:
                        svrs[vote_idx].append({
                            'v': util.bytes_to_bigint(svr.v),
                            'k': util.bytes_to_bigint(svr.k2),
                            'v_init': util.bytes_to_bigint(self._initial_sv[row][vote_idx].v),
                            'k_init': util.bytes_to_bigint(self._initial_sv[row][vote_idx].k2),
                            'v_fin': util.bytes_to_bigint(self._commitment_arrays[list_idx][row][vote_idx].v),
                            'k_fin': util.bytes_to_bigint(self._commitment_arrays[list_idx][row][vote_idx].k2),
                        })
            self._sbb.post_consistency_proof(list_idx, svrs)
        self._sbb.consistency_proof_end()

    def publish_election_outcome(self, outcome_lists: Set[int]) -> None:
        """
        Publishes fully decrypted but still shuffled votes from all m
        of the outcome_lists provided to the SBB.

        Step #8 from Section I.
        """
        self._sbb.post_start_election_outcome_proof()

        list_indices = sorted(list(outcome_lists))
        for list_idx in list_indices:
            svrs: List[List[Dict[str, int]]] = [[] for _ in range(self._num_votes)]
            for row, row_svrs in enumerate(self._commitment_arrays[list_idx]):
                for vote_idx, svr in enumerate(row_svrs):
                    svrs[vote_idx].append({
                        'u': util.bytes_to_bigint(svr.u),
                        'v': util.bytes_to_bigint(svr.v),
                        'k1': util.bytes_to_bigint(svr.k1),
                        'k2': util.bytes_to_bigint(svr.k2),
                    })
            self._sbb.post_one_election_outcome_proof(list_idx, svrs)
        self._sbb.post_end_section()

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
            initial_svr: List[sv_vote.PlaintextSVR] = []

            for vote in votes:
                decoder = self._tablet_decoders[vote.tablet_id]
                plaintext_svr: sv_vote.PlaintextSVR = vote.enc.decode(decoder)
                if (util.get_COM(plaintext_svr.k1, plaintext_svr.u) != vote.com_u or
                    util.get_COM(plaintext_svr.k2, plaintext_svr.v) != vote.com_v):
                    raise Exception('Commitment validation failed')

                component_value = util.val(
                    util.bytes_to_bigint(plaintext_svr.u),
                    util.bytes_to_bigint(plaintext_svr.v),
                    self._M,
                )
                vote_components.append(component_value)
                initial_svr.append(plaintext_svr)

            assert len(vote_components) == self._num_votes
            
            # We only need to do this one time, since this will be the same for every iteration
            if len(self._initial_sv) < self._rows:
                self._initial_sv.append(initial_svr)
            row_values.append(vote_components)

        # Obfuscation and shuffling - done once per column. Column here is only conceptual,
        # whereas in a real implementation, the data would be sent across servers.
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
            # with the appropriate row. obfuscation_lists has dimensions (_rows, _num_votes)
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
                
                # Insert a reverse permutation test here as a sanity check
                unshuffled = self._reverse_permutation(pi, row_values[row])
                assert unshuffled == obfuscated_components

        self._permutation_arrays.append(permutation_arrays)

        # Post lists of votes - last column creates and posts SVR commitments for
        # each value in the array of ballot components it contains.
        com_t: List[List[Dict[str, int]]] = [[] for _ in range(self._num_votes)]
        round_commitments: List[List[sv_vote.PlaintextSVR]] = []
        for row in range(self._rows):
            commitment_array: List[sv_vote.PlaintextSVR] = []
            for i, comp_val in enumerate(row_values[row]):
                svr = util.get_SVR(comp_val, self._M)
                commitment_array.append(svr)
                com_u = util.get_COM(svr.k1, svr.u)
                com_v = util.get_COM(svr.k2, svr.v)
                com_t[i].append({'com_u': com_u, 'com_v': com_v})

            round_commitments.append(commitment_array)

        self._sbb.post_one_mixnet_output_list(com_t)
        self._commitment_arrays.append(round_commitments)

    def mix_votes(self) -> None:
        """
        Mix votes according to Section VII.

        Implements 2m rounds of randomized vote obfuscation and shuffling across
        all PS rows and columns. Each of the 2m rounds produces 1 of the eventually
        2m lists posted to the SBB.
        """
        self._validate_stored_votes()

        self._sbb.post_start_mixnet_output_list()

        for _ in range(self._twoM):
            self._mix_round()

        self._sbb.post_end_section()
        
        # We unmix all commitments and publish t values because all t-values
        # should be published prior to the getting a random challenge request.
        self._unmix_commitments()
        self._publish_t_values()

        # Validation of PS state that we need to reconstruct original ballot
        # order and to open `m` commitments later.
        assert len(self._permutation_arrays) == self._twoM
        assert len(self._permutation_arrays[0]) == self._rows
        assert len(self._permutation_arrays[0][0]) == self._num_votes
        assert len(self._commitment_arrays) == self._twoM
        assert len(self._commitment_arrays[0]) == self._rows
        assert len(self._commitment_arrays[0][0]) == self._num_votes
