import random
from typing import Optional

from src.tablet import Tablet
from src.sbb import SBBContents
from src.sv_vote import SVVote


class Voter:
    def __init__(self, voter_id: int, M: int, vote: Optional[int] = None):
        self.voter_id: int = voter_id
        self.ballot_hash: str = ''
        self.bid: Optional[int] = None
        self.M: int = M
        self.vote: Optional[int] = vote

    def do_vote(self, tablet: Tablet):
        if self.vote is None or self.vote >= self.M:
            self.vote = random.choice(range(self.M))

        print(f'Voter ID: {self.voter_id}, vote is: {self.vote}')

        self.bid, self.ballot_hash = tablet.send_vote(self.vote)

    def verify(self, sbb_contents: SBBContents) -> bool:
        if self.bid is None:
            raise Exception('Voter does not have a valid bid, cannot verify vote')
        return sbb_contents.get_bid_receipt(self.bid) == self.ballot_hash
