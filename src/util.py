import os
from typing import List, Tuple

from cryptography.hazmat.primitives import hashes, hmac
from cryptography.hazmat.backends import default_backend


def bytes_to_bigint(byte_list: bytes):
    return int.from_bytes(byte_list, byteorder='little', signed=False)


def bigint_to_bytes(bigint: int):
    size = 0
    bigint_copy = bigint
    while True:
        bigint_copy = bigint_copy // 256
        size += 1
        if bigint_copy == 0:
            break

    return bigint.to_bytes(size, byteorder='little', signed=False)


def get_SV(x: int, M: int) -> Tuple[int, int]:
    """
    Return a randomized split-value representation of the int x mod M.
    """
    rand_bytes = os.urandom(16)
    rand_int = bytes_to_bigint(rand_bytes)
    u = rand_int % M
    v = (x - u) % M

    assert val(u, v, M) == x
    return u, v


def get_SV_multiple(x: int, n: int, M: int) -> List[int]:
    """
    Return a random SVRs of the value `x` with `n` components.
    """
    split: List[int] = []
    for _ in range(n-1):
        rand_bytes = os.urandom(16)
        rand_int = bytes_to_bigint(rand_bytes)
        split.append(rand_int % M)

    total = sum(split)
    last_val = (x - total) % M
    split.append(last_val)

    assert len(split) == n
    assert sum(split) % M == x
    return split


def get_hash(byte_list: bytes) -> str:
    digest = hashes.Hash(algorithm=hashes.SHA256(), backend=default_backend())
    digest.update(byte_list)
    return digest.finalize().hex()


def get_COM(K: bytes, u: bytes):
    """
    Commits the value u and is computationally hiding.
    To open the commitment, run this again and compare the values.
    This uses HMAC.
    """
    h = hmac.HMAC(K, hashes.SHA256(), backend=default_backend())
    h.update(u)
    return h.finalize()


def val(u: int, v: int, M: int) -> int:
    return (u + v) % M
