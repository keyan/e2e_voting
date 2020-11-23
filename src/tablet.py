from src import proof_server
from src import sv_vote


class Tablet:
    def __init__(self, srv: proof_server.ProofServer):
        self._srv = srv
        self._generate_id()
        self._create_secret_key()
        self._register_with_srv()
        self._proof_srv_rows = srv.get_num_rows()
    
    def _generate_id(self):
        self._id = ''
        
    def _create_secret_key(self):
        self._secret_key = ''
        
    def _register_with_srv(self):
        # TODO: encrypt secret key with public key
        enc = self._secret_key
        self._srv.register_tablet(self._id, enc)
    
    def send_vote(self, vote):
        # TODO: generate bid and get vote hash
        bid = ''
        hash = ''
        v = sv_vote.SVVote()
        self._srv.handle_vote(v)
        
        # return bid and hash
        return bid, hash
