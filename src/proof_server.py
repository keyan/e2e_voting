from src import sv_vote


class ProofServer:
    def __init__(self, rows: int):
        self._generate_key_pair()
        self._rows = rows

    #
    # Proof server initialization
    #
    def _generate_key_pair(self):
        self._public_key = ''
        self._secret_key = ''

    #
    # Public proof server functions/endpoints
    #
    def register_tablet(self, tablet_id: str, pk_encrypted_sk):
        pass

    def get_public_key(self):
        return self._public_key

    def get_num_rows(self) -> int:
        return self._rows

    def handle_vote(self, sv_vote: sv_vote.SVVote):
        pass

    #
    # Proof server mixing implementation
    #
    def _publish_proof(self):
        pass

    def mix_votes(self):
        pass



