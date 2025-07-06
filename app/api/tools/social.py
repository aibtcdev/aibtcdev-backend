from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from starlette.responses import JSONResponse
import httpx

from app.lib.logger import configure_logger

# Configure logger
logger = configure_logger(__name__)

# Create the router
router = APIRouter()


@router.get("/twitter_embed")
async def get_twitter_embed(
    request: Request,
    url: str = Query(..., description="Twitter/X.com URL to embed"),
    media_max_width: Optional[int] = Query(560, description="Maximum width for media"),
    hide_thread: Optional[bool] = Query(False, description="Hide thread"),
) -> JSONResponse:
    """Proxy endpoint for Twitter oembed API.

    This endpoint acts as a proxy to Twitter's oembed API to avoid CORS issues
    when embedding tweets in web applications.

    Args:
        request: The FastAPI request object.
        url: The Twitter/X.com URL to embed.
        media_max_width: Maximum width for embedded media (default: 560).
        hide_thread: Whether to hide the thread (default: False).

    Returns:
        JSONResponse: The oembed data from Twitter or error details.

    Raises:
        HTTPException: If there's an error with the request or Twitter API.
    """
    try:
        logger.info(
            f"Twitter oembed request received from {request.client.host if request.client else 'unknown'} for URL: {url}"
        )

        # Validate the URL format
        if not url.startswith(("https://x.com/", "https://twitter.com/")):
            logger.warning(f"Invalid Twitter URL provided: {url}")
            raise HTTPException(
                status_code=400,
                detail="Invalid Twitter URL. URL must start with https://x.com/ or https://twitter.com/",
            )

        # Make async request to Twitter oembed API
        async with httpx.AsyncClient() as client:
            oembed_url = "https://publish.twitter.com/oembed"
            params = {
                "url": url,
                "media_max_width": media_max_width,
                "partner": "",
                "hide_thread": hide_thread,
            }

            logger.debug(f"Making request to Twitter oembed API with params: {params}")

            response = await client.get(oembed_url, params=params, timeout=10.0)

            if response.status_code == 200:
                logger.info(f"Successfully retrieved oembed data for URL: {url}")
                return JSONResponse(content=response.json())
            elif response.status_code == 404:
                logger.warning(f"Twitter post not found for URL: {url}")
                raise HTTPException(status_code=404, detail="Twitter post not found")
            else:
                logger.error(f"Twitter API error {response.status_code} for URL: {url}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Twitter API error: {response.status_code}",
                )

    except httpx.TimeoutException:
        logger.error(f"Request timeout for Twitter URL: {url}")
        raise HTTPException(status_code=408, detail="Request to Twitter API timed out")
    except httpx.RequestError as e:
        logger.error(f"Request failed for Twitter URL {url}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to connect to Twitter API: {str(e)}"
        )
    except HTTPException as he:
        # Re-raise HTTPExceptions directly
        raise he
    except Exception as e:
        logger.error(f"Unexpected error for Twitter URL {url}: {str(e)}", exc_info=e)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
