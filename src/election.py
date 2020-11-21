from typing import Optional

from src import sbb
from src import tablet
from src import voter


class Election:
    def __init__(
        self,
        M: int = 4,
        twoM: int = 4,
        num_voters: int = 3,
        num_tablets: int = 3,
    ):
        self.M = M
        self.twoM = twoM
        self.sbb = sbb.SBB()
        self.voters = [voter.Voter() for _ in range(num_voters)]
        self.tablets = [tablet.Tablet() for _ in range(num_tablets)]

    def run(self):
        print('Running election...')
