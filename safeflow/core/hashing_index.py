"""Fast Perceptual Hash Indexing using Burkhard-Keller Trees (BK-Tree).

Enables sub-millisecond metric-space similarity queries over 64-bit and 128-bit
perceptual hashes (pHash, dHash, wHash) under discrete Hamming distance metrics.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar
import threading

T = TypeVar("T")


def hamming_distance_hex(hash1: str, hash2: str) -> int:
    """Compute Hamming distance between two hex-encoded perceptual hash strings."""
    try:
        h1 = int(hash1.replace("0x", ""), 16)
        h2 = int(hash2.replace("0x", ""), 16)
        xor = h1 ^ h2
        return bin(xor).count("1")
    except Exception:
        return 999


class BKTreeNode:
    """Node in a Burkhard-Keller metric tree.

    Attributes:
        hash_str: Normalized hexadecimal perceptual hash stored at this node.
        payload: Arbitrary caller-provided metadata (e.g., media_id, actor_id, tags).
        children: Mapping from discrete Hamming distance (int) to child BKTreeNode.
    """

    def __init__(self, hash_str: str, payload: Any = None) -> None:
        self.hash_str = hash_str
        self.payload = payload
        self.children: dict[int, BKTreeNode] = {}


class PerceptualHashBKTree:
    """Thread-safe Burkhard-Keller Tree for fast sub-millisecond Hamming distance lookups.

    The BK-Tree indexes perceptual hashes in a metric space (discrete Hamming distance)
    satisfying the triangle inequality:
        d(x, z) <= d(x, y) + d(y, z)

    During queries with radius R around query Q:
    For any node N at distance d(Q, N), any match X must satisfy:
        d(Q, N) - R <= d(N, X) <= d(Q, N) + R
    This prunes non-matching subtrees, enabling $O(\\log N)$ search complexity.
    """

    def __init__(self) -> None:
        self.root: BKTreeNode | None = None
        self._size: int = 0
        self._lock = threading.RLock()

    def __len__(self) -> int:
        """Return total number of unique perceptual hashes indexed."""
        return self._size

    def insert(self, hash_str: str, payload: Any = None) -> None:
        """Insert a perceptual hash string with optional metadata payload into the BK-Tree.

        Args:
            hash_str: Hexadecimal hash representation (e.g. '0x1234abcd5678ef01').
            payload: Optional metadata payload associated with this hash.
        """
        clean_hash = hash_str.lower().strip()
        with self._lock:
            # Case 1: Empty tree initialization
            if self.root is None:
                self.root = BKTreeNode(clean_hash, payload)
                self._size = 1
                return

            # Case 2: Traverse tree to find appropriate branch
            current = self.root
            while True:
                dist = hamming_distance_hex(clean_hash, current.hash_str)
                if dist == 0:
                    # Exact duplicate hash; update payload if provided
                    current.payload = payload or current.payload
                    return

                # Branch along edge corresponding to Hamming distance
                if dist in current.children:
                    current = current.children[dist]
                else:
                    current.children[dist] = BKTreeNode(clean_hash, payload)
                    self._size += 1
                    return

    def batch_insert(self, items: list[tuple[str, Any]]) -> None:
        """Insert multiple (hash_str, payload) pairs in a thread-safe transaction.

        Args:
            items: List of (hex_hash, payload) tuples.
        """
        with self._lock:
            for h_str, p in items:
                self.insert(h_str, p)

    def search(self, query_hash: str, max_distance: int = 10) -> list[dict[str, Any]]:
        """Find all indexed hashes within Hamming distance <= max_distance.

        Args:
            query_hash: Target perceptual hash to compare against.
            max_distance: Maximum Hamming distance bound (radius threshold).

        Returns:
            Sorted list of dicts: [{'hash': str, 'distance': int, 'payload': Any}], closest first.
        """
        results: list[dict[str, Any]] = []
        clean_query = query_hash.lower().strip()

        with self._lock:
            if self.root is None:
                return []

            candidates = [self.root]
            while candidates:
                node = candidates.pop()
                dist = hamming_distance_hex(clean_query, node.hash_str)
                
                # Check if current node is a match
                if dist <= max_distance:
                    results.append({
                        "hash": node.hash_str,
                        "distance": dist,
                        "payload": node.payload,
                    })

                # BK-Tree triangle inequality pruning:
                # Subtrees outside [dist - max_distance, dist + max_distance] cannot contain matches
                min_d = dist - max_distance
                max_d = dist + max_distance
                for edge_weight, child_node in node.children.items():
                    if min_d <= edge_weight <= max_d:
                        candidates.append(child_node)

        # Sort matches closest first
        results.sort(key=lambda r: r["distance"])
        return results
