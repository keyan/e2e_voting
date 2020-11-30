import random
from typing import Optional

from src import sbb
from src import tablet
from src import voter
from src import proof_server


class Election:
    def __init__(
        self,
        M: int = 3,
        twoM: int = 2,
        num_voters: int = 3,
        num_tablets: int = 3,
        num_proof_srv_rows: int = 3,
    ):
        # M should be prime
        self.M = M
        # Explained in detail in Section IX, the higher this value is the greater the
        # level of assurance in the SBB posted proof. But increasing 2m also increases
        # memory usage and computation time.
        self.twoM = twoM
        self.sbb = sbb.SBB()
        self.proof_server = proof_server.ProofServer(
            twoM=self.twoM, rows=num_proof_srv_rows, sbb=self.sbb,
        )
        self.voters = [voter.Voter(voter_id=i, M=self.M) for i in range(num_voters)]
        self.tablets = [
            tablet.Tablet(srv=self.proof_server, M=self.M, sbb=self.sbb)
            for _ in range(num_tablets)
        ]

    def run(self):
        print('Running election...')
        for v in self.voters:
            t = self._get_tablet()
            v.do_vote(t)

        self.sbb.post_ballots_and_commitments()

        # End the election and mix votes
        self.proof_server.mix_votes()

        # Verify election results for each voter
        for v in self.voters:
            if not v.verify(self.sbb):
                raise Exception('Voter ballot failed validation')
            else:
                print(f'Verified ballot for voter: {v.voter_id}')

        # Election complete, cleanup steps.
        self.sbb.close()

        print('Election complete')

    def _get_tablet(self) -> tablet.Tablet:
        """
        Select random tablet and return it.
        """
        return random.choice(self.tablets)
