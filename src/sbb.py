import json

# Define SBB headings used to later parse the SBB during proof.
BALLOT_RECEIPTS = 'ballot_receipts'
COMMITMENTS = 'commitments'

class SBB:
    """
    Implements an interface for the Secure Bulletin Board (SBB).
    """
    def __init__(self):
        self._ballot_receipts: List[str] = []
        self._svr_commitments: List[str] = []
        self._db: file = open('sbb.txt', 'w')

    def close(self) -> None:
        self._db.close()

    def add_ballot_receipt(self, bid: int, receipt_str: str) -> None:
        """
        Add a single ballot to local receipt list, these are posted in bulk later.
        """
        self._ballot_receipts.append(json.dumps({'bid': bid, 'receipt': receipt_str}, sort_keys=True))

    def add_ballot_svr_commitment(self, com_u: bytes, com_v: bytes) -> None:
        """
        Add a component of a ballot SVR to local receipt list, these are posted in bulk later.

        It is important that the order of incoming ballots/components be retained for ballot
        verification in the proof step.
        """
        self._svr_commitments.append(json.dumps(
            {'com_u': com_u.hex(), 'com_v': com_v.hex()},
            sort_keys=True,
        ))

    def post_ballots_and_commitments(self) -> None:
        """
        Post all retained ballots and their SVR commitments to SBB.
        """
        self._db.write(BALLOT_RECEIPTS + '\n')
        for receipt in self._ballot_receipts:
            self._db.write(receipt + '\n')

        self._db.write(COMMITMENTS + '\n')
        for com in self._svr_commitments:
            self._db.write(com + '\n')
