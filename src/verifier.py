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
        
        #t_values = sbb_contents.t_values
        consistency_proof = sbb_contents.consistency_proof
        
        for list_idx, proof in consistency_proof.items():
            for vote_idx in range(len(proof)):
                # TODO: This is somewhat incorrect. We need to sum X, Y, and Z with (T) and return a T per vote, not per row? Maybe?
                proved_sv = proof[vote_idx]
                for row_idx, sv in enumerate(proved_sv):
                    #t_val_uv = t_values[list_idx][row_idx][vote_idx]
                    # TODO: where is the original vote SV?
                    if sv.get('u', None) is not None:
                        val = sv['u_init']
                        original_commitment = sbb_contents.svr_commitments[row_idx][vote_idx]['com_u']
                    else:
                        val = sv['v_init']
                        original_commitment = sbb_contents.svr_commitments[row_idx][vote_idx]['com_v']
                    #compare_val = util.val(t_val, val, self._M)
                    key = sv['k_init']
                    commitement = util.get_COM(util.bigint_to_bytes(key), util.bigint_to_bytes(val))
                    #commitement = util.get_COM(key, util.bigint_to_bytes(val))
                    assert commitement == original_commitment
            
        # TODO
        # Parse SBB
        # Use (t, -t) and prior commitments posted to verify
        return True

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
