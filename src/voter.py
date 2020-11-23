from src.tablet import Tablet
from src.sbb import SBB


class Voter:
    def __init__(self):
        self.ballot_hash = None
        self.bid = None
        self.vote = None

    def vote(self, tablet: Tablet):
        self.bid, self.ballot_hash = tablet.send_vote(self.vote)

    def verify(self, sbb: SBB) -> True:
        return True
