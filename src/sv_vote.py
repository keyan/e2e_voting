from typing import Optional

from cryptography.fernet import Fernet


class PlaintextSVR:
    """
    PlaintextSVR represents one SVR tuple (u, v) and the keys
    encryption keys used to make a commitment to this SVR.
    """
    def __init__(self, k1: bytes, k2: bytes, u: bytes, v: bytes):
        self.k1 = k1
        self.k2 = k2
        self.u = u
        self.v = v


class EncCom:
    """
    EncCom represents one encrypted commitment to a SVR tuple (u, v) and the
    encrypted encryption keys used to make the commitment.
    """
    def __init__(self):
        self.k1: bytes = None
        self.k2: bytes = None
        self.u: bytes = None
        self.v: bytes = None

    def decode(self, decoder: Fernet) -> PlaintextSVR:
        k1 = decoder.decrypt(self.k1)
        k2 = decoder.decrypt(self.k2)
        u = decoder.decrypt(self.u)
        v = decoder.decrypt(self.v)

        return PlaintextSVR(k1, k2, u, v)


class SVVote:
    def __init__(self):
        self.bid = None                                    # Ballot ID
        self.com_u = None                                  # Commitment part 1
        self.com_v = None                                  # Commitment part 2
        self.enc: EnvCom = None                            # Encrypted K1, u, K2, v, for opening the commitment later
        self.tablet_id = None                              # Tablet ID
        self.proof_server_row: Optional[int] = None        # Which proof server row this vote is going to
