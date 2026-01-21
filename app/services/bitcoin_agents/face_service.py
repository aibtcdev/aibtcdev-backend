"""Bitcoin Faces integration service.

Fetches deterministic faces from bitcoinfaces.xyz API and manages caching.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import httpx

from app.lib.logger import configure_logger

logger = configure_logger(__name__)

# Bitcoin Faces API
BITCOIN_FACES_API = "https://bitcoinfaces.xyz/api"
FACE_CACHE_TTL = timedelta(hours=24)  # Cache faces for 24 hours


class BitcoinFaceService:
    """Service for fetching and caching Bitcoin Faces."""

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        # In-memory cache (TODO: Replace with Supabase storage)
        self._cache: Dict[str, Dict[str, Any]] = {}

    async def get_face_svg(self, address: str) -> Optional[str]:
        """Get SVG face for an address.

        Args:
            address: Stacks address or any seed string

        Returns:
            SVG code string or None if failed
        """
        try:
            # Check cache first
            cached = self._get_cached(address, "svg")
            if cached:
                return cached

            url = f"{BITCOIN_FACES_API}/get-svg-code"
            response = await self.client.get(url, params={"name": address})

            if response.status_code == 200:
                svg_code = response.text
                self._set_cache(address, "svg", svg_code)
                logger.debug(f"Fetched SVG face for {address[:20]}...")
                return svg_code
            else:
                logger.warning(
                    f"Failed to fetch SVG face: {response.status_code}",
                    extra={"address": address},
                )
                return None

        except Exception as e:
            logger.error(f"Error fetching SVG face: {e}", exc_info=e)
            return None

    async def get_face_image_url(self, address: str) -> str:
        """Get image URL for an address.

        This returns the direct URL - no need to fetch content.

        Args:
            address: Stacks address or any seed string

        Returns:
            Image URL string
        """
        return f"{BITCOIN_FACES_API}/get-image?name={address}"

    async def get_face_data(self, address: str) -> Dict[str, Any]:
        """Get all face data for an address.

        Args:
            address: Stacks address or any seed string

        Returns:
            Dict with svg_url, image_url, and cached_at
        """
        svg = await self.get_face_svg(address)
        image_url = await self.get_face_image_url(address)

        return {
            "svg": svg,
            "svg_url": f"{BITCOIN_FACES_API}/get-svg-code?name={address}",
            "image_url": image_url,
            "cached_at": datetime.utcnow().isoformat(),
        }

    def get_evolved_face_url(
        self,
        address: str,
        level: str,
    ) -> str:
        """Get face URL with evolution overlay.

        Different levels get different visual treatments:
        - Hatchling: Base face
        - Junior: +glow effect
        - Senior: +crown
        - Elder: +aura
        - Legendary: +legendary frame

        Args:
            address: Stacks address
            level: Evolution level (hatchling, junior, senior, elder, legendary)

        Returns:
            URL for the evolved face image
        """
        base_url = f"{BITCOIN_FACES_API}/get-image?name={address}"

        # TODO: Implement overlay generation
        # For now, return base URL with level parameter
        # The frontend can handle overlay rendering

        return f"{base_url}&level={level}"

    def _get_cached(self, address: str, cache_type: str) -> Optional[str]:
        """Get cached face data if still valid."""
        key = f"{address}:{cache_type}"
        if key in self._cache:
            entry = self._cache[key]
            if datetime.utcnow() - entry["cached_at"] < FACE_CACHE_TTL:
                return entry["data"]
            else:
                del self._cache[key]
        return None

    def _set_cache(self, address: str, cache_type: str, data: str):
        """Set cache entry."""
        key = f"{address}:{cache_type}"
        self._cache[key] = {
            "data": data,
            "cached_at": datetime.utcnow(),
        }

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


# Singleton instance
_face_service: Optional[BitcoinFaceService] = None


def get_face_service() -> BitcoinFaceService:
    """Get or create the face service singleton."""
    global _face_service
    if _face_service is None:
        _face_service = BitcoinFaceService()
    return _face_service
