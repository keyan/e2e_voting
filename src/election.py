from typing import Optional

from src import sbb
from src import tablet
from src import voter
from src import proof_server


class Election:
    def __init__(
        self,
        M: int = 4,
        twoM: int = 4,
        num_voters: int = 3,
        num_tablets: int = 3,
        num_proof_srv_rows: int = 3,
    ):
        self.M = M
        self.twoM = twoM
        self.sbb = sbb.SBB()
        self.proof_server = proof_server.ProofServer(rows=num_proof_srv_rows)
        self.voters = [voter.Voter() for _ in range(num_voters)]
        self.tablets = [tablet.Tablet(srv=self.proof_server) for _ in range(num_tablets)]
        
    def run(self):
        print('Running election...')
        for v in self.voters:
            t = self._get_tablet()
            v.vote(t)
            
        # End the election and mix votes
        self.proof_server.mix_votes()
        
        # Verify election results for each voter
        for v in self.voters:
            if not v.verify(self.sbb):
                print('Das nicht gut')
        
    def _get_tablet(self) -> tablet.Tablet:
        """
        Select random tablet and return it
        :return:
        """
        # TODO
        return self.tablets[0]
