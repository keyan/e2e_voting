from typing import Optional


class SVVote:
    def __init__(self):
        self.bid = None                 # Ballot ID
        self.com_u = None               # Commitment part 1
        self.com_v = None               # Commitment part 2
        self.enc = None                 # Encrypted K1, u, K2, v, for opening the commitment later
        self.tablet_id = None           # Tablet ID
        self.proof_server_row: Optional[int] = None    # Which proof server row this vote is going to


class EncCom:
    def __init__(self):
        self.k1 = None
        self.k2 = None
        self.u = None
        self.v = None
