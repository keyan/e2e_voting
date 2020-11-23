from src.tablet import Tablet
from src.sbb import SBB
from src.sv_vote import SVVote


class Voter:
    def __init__(self):
        self.ballot_hash = None
        self.bid = None
        # TODO: actually create a valid vote
        self.vote = SVVote()

    def do_vote(self, tablet: Tablet):
        self.bid, self.ballot_hash = tablet.send_vote(self.vote)

    def verify(self, sbb: SBB) -> bool:
        return True
