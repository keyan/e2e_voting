from src import sbb

class Verifier:
    def __init__(self, sbb: sbb.SBB):
        self._sbb = sbb

    def verify_ballot_consistency(self) -> bool:
        """
        Returns True if the proof posted to SBB is verified to be consistent
        with the cast votes posted to SBB by tablets during Step 3.

        This method utilizes the partially decrypted un-shufffled but still
        obfuscated SVRs posted to SBB by the PS and verifies equality using
        the "Proving Equality of Arrays of Vote Values" procedure described
        in Section II-F.
        """
        # TODO
        # Parse SBB
        # Use (t, -t) and prior commitments posted to verify
        return True
