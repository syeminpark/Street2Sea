import os
import time
import requests
from functools import lru_cache
from typing import Optional, List
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))
GMP_KEY = os.getenv("GOOGLE_STREET_VIEW_API_KEY")

SESSION_URL = "https://tile.googleapis.com/v1/createSession"
META_URL    = "https://tile.googleapis.com/v1/streetview/metadata"

_session_token: Optional[str] = None
_session_expiry: float = 0.0  # epoch seconds


def _get_session_token() -> str:
    """
    Create or reuse a Street View Tiles API session token.
    """
    global _session_token, _session_expiry
    now = time.time()
    if _session_token and now < _session_expiry - 60:
        return _session_token

    r = requests.post(
        SESSION_URL,
        params={"key": GMP_KEY},
        json={"mapType": "streetview"},
        timeout=10,
    )
    try:
        r.raise_for_status()
    except requests.HTTPError:
        # bubble up a helpful message
        raise RuntimeError(f"Tiles session error {r.status_code}: {r.text[:300]}")

    data = r.json()
    _session_token = data["session"]
    # if the API returns a TTL use it; else 30m conservative
    _session_expiry = now + 60 * 30
    return _session_token


@lru_cache(maxsize=4096)
def get_tiles_metadata_by_panoid(pano_id: str) -> Optional[dict]:
    """
    Raw Street View Tiles metadata JSON for a panoId, or None on error.
    """
    if not pano_id:
        return None
    try:
        session = _get_session_token()
        r = requests.get(
            META_URL,
            params={"key": GMP_KEY, "session": session, "panoId": pano_id},
            timeout=10
        )
        if r.status_code != 200:
            print(f"[Tiles meta] {pano_id} -> {r.status_code}: {r.text[:200]}")
            return None
        return r.json()
    except Exception as e:
        print(f"[Tiles meta] exception for {pano_id}: {e}")
        return None


@lru_cache(maxsize=4096)
def get_imagery_type_for_pano(pano_id: str) -> Optional[str]:
    """
    Returns 'outdoor', 'indoor', or None if unknown/error.
    """
    meta = get_tiles_metadata_by_panoid(pano_id)
    if not meta:
        return None
    return meta.get("imageryType")


def get_neighbor_pano_ids(pano_id: str) -> List[str]:
    """
    Returns neighbor panoIds from metadata 'links' array, if present.
    """
    meta = get_tiles_metadata_by_panoid(pano_id)
    if not meta:
        return []
    links = meta.get("links") or []
    out = []
    for link in links:
        pid = link.get("panoId")
        if pid:
            out.append(pid)
    return out


def find_nearest_outdoor_neighbor_id(seed_pano_id: str, max_hops: int = 4) -> Optional[str]:
    """
    BFS a few hops across neighbor links to find the first pano with imageryType == 'outdoor'.
    Returns the panoId or None if not found.
    """
    if not seed_pano_id:
        return None

    visited = set([seed_pano_id])
    frontier = [seed_pano_id]
    hops = 0

    while frontier and hops < max_hops:
        next_frontier = []
        for pid in frontier:
            itype = get_imagery_type_for_pano(pid)
            if itype == "outdoor":
                return pid
            for npid in get_neighbor_pano_ids(pid):
                if npid not in visited:
                    visited.add(npid)
                    next_frontier.append(npid)
        frontier = next_frontier
        hops += 1

    return None


