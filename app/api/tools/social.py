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
        logger.debug(
            "Twitter oembed request", extra={"url": url, "event_type": "twitter_embed"}
        )

        # Validate the URL format
        if not url.startswith(("https://x.com/", "https://twitter.com/")):
            logger.warning("Invalid Twitter URL format", extra={"url": url})
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

            logger.debug(
                "Twitter API request initiated",
                extra={"url": url, "media_max_width": media_max_width},
            )

            response = await client.get(oembed_url, params=params, timeout=10.0)

            if response.status_code == 200:
                logger.info("Twitter oembed retrieved", extra={"url": url})
                return JSONResponse(content=response.json())
            elif response.status_code == 404:
                logger.warning("Twitter post not found", extra={"url": url})
                raise HTTPException(status_code=404, detail="Twitter post not found")
            else:
                logger.warning(
                    "Twitter API error",
                    extra={"url": url, "status_code": response.status_code},
                )
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Twitter API error: {response.status_code}",
                )

    except httpx.TimeoutException:
        logger.warning("Twitter API timeout", extra={"url": url})
        raise HTTPException(status_code=408, detail="Request to Twitter API timed out")
    except httpx.RequestError as e:
        logger.error("Twitter API request failed", extra={"url": url, "error": str(e)})
        raise HTTPException(
            status_code=500, detail=f"Failed to connect to Twitter API: {str(e)}"
        )
    except HTTPException as he:
        # Re-raise HTTPExceptions directly
        raise he
    except Exception as e:
        logger.error(
            "Twitter oembed unexpected error",
            extra={"url": url, "error": str(e)},
            exc_info=e,
        )
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
