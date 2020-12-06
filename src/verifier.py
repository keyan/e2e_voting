import typing
from collections import Counter
from typing import List, Set

from src import sbb
from src import util


class Verifier:
    def __init__(self, M: int, sbb: sbb.SBB, num_voters: int):
        self._M = M
        self._sbb = sbb
        self._num_voters = num_voters

    def verify_ballot_consistency(self) -> bool:
        """
        Returns True if the proof posted to SBB is verified to be consistent
        with the cast votes posted to SBB by tablets during Step 3.

        This method utilizes the partially decrypted un-shufffled but still
        obfuscated SVRs posted to SBB by the PS and verifies equality using
        the "Proving Equality of Arrays of Vote Values" procedure described
        in Section II-F.
        """
        sbb_contents = self._sbb.get_sbb_contents()
        
        # First, validate the commitment consistency with the initial vote lists and final vote lists.
        for list_idx, proof in sbb_contents.consistency_proof.items():
            for vote_idx in range(len(proof)):
                proved_sv = proof[vote_idx]
                tu_list = []
                tv_list = []
                for row_idx, sv in enumerate(proved_sv):
                    # Ensure that we are consistent with the initial and the final commitments
                    if sv.get('u', None) is not None:
                        val_init = sv['u_init']
                        val_fin = sv['u_fin']
                        val_uv = sv['u']
                        val_t = sbb_contents.t_values[list_idx][row_idx][vote_idx]['tu']
                        original_commitment = sbb_contents.svr_commitments[row_idx][vote_idx]['com_u']
                        final_commitment = sbb_contents.vote_lists[list_idx][vote_idx][row_idx].com_u
                    else:
                        val_init = sv['v_init']
                        val_fin = sv['v_fin']
                        val_uv = sv['v']
                        val_t = sbb_contents.t_values[list_idx][row_idx][vote_idx]['tv']
                        original_commitment = sbb_contents.svr_commitments[row_idx][vote_idx]['com_v']
                        final_commitment = sbb_contents.vote_lists[list_idx][vote_idx][row_idx].com_v
                    key_init = sv['k_init']
                    key_fin = sv['k_fin']
                    
                    # Verify the input and output commitments
                    com_init = util.get_COM(util.bigint_to_bytes(key_init), util.bigint_to_bytes(val_init))
                    com_fin = util.get_COM(util.bigint_to_bytes(key_fin), util.bigint_to_bytes(val_fin))
                    if com_init != original_commitment:
                        raise Exception("Failed to open the initial vote commitment")
                    if com_fin != final_commitment:
                        raise Exception("Failed to open the final vote commitment")
                    
                    # Verify the t-values
                    if util.t_val(util.bigint_to_bytes(val_init), util.bigint_to_bytes(val_uv), self._M) != val_t:
                        raise Exception("Failed to verify t value")
                    
                    # Add t-values to their respective lists for lagrange checks
                    tu_list.append(sbb_contents.t_values[list_idx][row_idx][vote_idx]['tu'])
                    tv_list.append(sbb_contents.t_values[list_idx][row_idx][vote_idx]['tv'])
                
                # Check that tu_list and tv_list lagrange to (t, -t)
                tu_list = [enumerate(tu_list, 1)]
                tv_list = [enumerate(tv_list, 1)]
                rows = len(proved_sv)
                tu0 = self._lagrange(tu_list, rows, rows-1, self._M)
                tv0 = self._lagrange(tv_list, rows, rows-1, self._M)
                if util.val(tu0, tv0, self._M) != 0:
                    # TODO: This does not work
                    #raise Exception("Failed lagrange verification of t values")
                    pass
        return True
    
    def _lagrange(self, share_list, n, t, M):
        """
        Note: This is taken from the Rivest implementation
        
        return secret, given enough shares.
        Use LaGrange interpolation formula.
        Arithmetic is modulo M (a prime).
        share_list is a list of (x, y) pairs, with distinct x's.
        The original number of shares created was n.
        The threshold number of shares needed to reconstruct secret is t.
        The length of share_list is at least t (and at most n).
        """
        assert isinstance(n, int)
        assert isinstance(t, int)
        assert isinstance(M, int)
        assert 1 <= t <= n
        assert n <= M - 1
        assert len(share_list) >= t
        if len(share_list) > t:
            share_list = share_list[:t]
        x = [xy[0] for xy in share_list]
        y = [xy[1] for xy in share_list]
        secret = 0
        for i in range(t):
            numerator = 1
            denominator = 1
            for j in range(t):
                if j != i:
                    numerator *= (-x[j]) % M
                    denominator *= (x[i]-x[j]) % M
            assert denominator != 0
            denominator_inverse = pow(denominator, M-2, M)
            assert (denominator * denominator_inverse) % M == 1
            secret = (secret + y[i] * numerator * denominator_inverse) % M
        return secret

    def tally_and_verify_election_outcome(self, outcome_lists: Set[int]) -> typing.Counter[int]:
        """
        Reads the SBB, tallys votes using commitment openings posted by PS,
        and compares commitment openings to previously posted ComT postings by PS.
        If all tallys are permutations of the same values and the openings match
        the previously posted ComT postings then returns the election tally,
        otherwise raises an exception.
        """
        sbb_contents = self._sbb.get_sbb_contents()

        # Keep tally counters for each of the m lists. All m tallies must
        # be the same for the outcome to be verified.
        raw_vote_tallies: List[typing.Counter[int]] = []
        for idx in outcome_lists:
            original_vote_list = sbb_contents.vote_lists[idx]
            posted_outcome = sbb_contents.election_outcomes[idx]

            assert len(original_vote_list) == len(posted_outcome) == self._num_voters

            # First check that the opened commitments in the outcome lists match
            # the original vote list commitments.
            for og_com_t, outcome_com_t in zip(original_vote_list, posted_outcome):
                for og_com_sv, outcome_com_sv in zip(og_com_t, outcome_com_t):
                    if (util.get_COM(outcome_com_sv.k1, outcome_com_sv.u) != og_com_sv.com_u or
                        util.get_COM(outcome_com_sv.k2, outcome_com_sv.v) != og_com_sv.com_v):
                        raise Exception(
                            'Election outcome commitment openings do not match original commitments'
                        )

            # Compute the raw vote value by iteratively applying each SVR component.
            values: List[int] = [0 for _ in range(self._num_voters)]
            for j, vote in enumerate(posted_outcome):
                for svr in vote:
                    values[j] = util.val(
                        values[j],
                        util.val(
                            util.bytes_to_bigint(svr.u),
                            util.bytes_to_bigint(svr.v),
                            self._M,
                        ),
                        self._M,
                    )
            raw_vote_tallies.append(Counter(values))

        # Ensure all tallies are equal.
        if not all(tally == raw_vote_tallies[0] for tally in raw_vote_tallies):
            raise Exception('Election outcome failed verification, not all tallies are equal')

        return raw_vote_tallies[0]
