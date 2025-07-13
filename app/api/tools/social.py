from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from starlette.responses import JSONResponse
import httpx

from app.api.tools.models import TwitterEmbedResponse
from app.lib.logger import configure_logger

# Configure logger
logger = configure_logger(__name__)

# Create the router
router = APIRouter()


@router.get(
    "/twitter_embed",
    response_model=TwitterEmbedResponse,
    summary="Get Twitter Embed Data",
    description="Retrieve Twitter oEmbed data for embedding tweets in web applications",
    responses={
        200: {
            "description": "Twitter embed data retrieved successfully",
            "model": TwitterEmbedResponse,
            "content": {
                "application/json": {
                    "example": {
                        "html": '<blockquote class="twitter-tweet"><p lang="en" dir="ltr">This is a sample tweet</p>&mdash; John Doe (@johndoe) <a href="https://twitter.com/johndoe/status/1234567890">January 1, 2024</a></blockquote>',
                        "url": "https://twitter.com/johndoe/status/1234567890",
                        "author_name": "John Doe",
                        "author_url": "https://twitter.com/johndoe",
                        "width": 550,
                        "height": 400,
                        "type": "rich",
                        "version": "1.0",
                    }
                }
            },
        },
        400: {
            "description": "Invalid Twitter URL",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid Twitter URL. URL must start with https://x.com/ or https://twitter.com/"
                    }
                }
            },
        },
        404: {
            "description": "Twitter post not found",
            "content": {
                "application/json": {"example": {"detail": "Twitter post not found"}}
            },
        },
        408: {
            "description": "Request timeout",
            "content": {
                "application/json": {
                    "example": {"detail": "Request to Twitter API timed out"}
                }
            },
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Failed to connect to Twitter API: Connection refused"
                    }
                }
            },
        },
    },
    tags=["social"],
)
async def get_twitter_embed(
    request: Request,
    url: str = Query(
        ...,
        description="Twitter/X.com URL to embed",
        example="https://x.com/johndoe/status/1234567890",
    ),
    media_max_width: Optional[int] = Query(
        560,
        description="Maximum width for embedded media in pixels",
        example=560,
        ge=250,
        le=1200,
    ),
    hide_thread: Optional[bool] = Query(
        False,
        description="Whether to hide the thread context when embedding",
        example=False,
    ),
) -> JSONResponse:
    """
    Retrieve Twitter oEmbed data for embedding tweets in web applications.

    This endpoint acts as a proxy to Twitter's oEmbed API, avoiding CORS issues
    when embedding tweets in web applications. It supports both twitter.com and
    x.com URLs and provides customizable embed options.

    **Supported URLs:**
    - `https://twitter.com/user/status/1234567890`
    - `https://x.com/user/status/1234567890`

    **Embed Customization:**
    - **Media Max Width:** Controls the maximum width of embedded media
    - **Hide Thread:** Option to hide the conversation thread context
    - **Responsive Design:** Embeds automatically adapt to container width

    **Use Cases:**
    - Embedding tweets in DAO proposals and discussions
    - Creating social media feeds in web applications
    - Displaying Twitter content without CORS restrictions
    - Building news aggregators and social dashboards

    **Twitter oEmbed Features:**
    - Rich HTML markup for proper tweet display
    - Author information and profile links
    - Automatic Twitter branding and styling
    - Click-through navigation to original tweet

    **Rate Limiting:** This endpoint respects Twitter's rate limiting policies.
    For high-volume applications, consider implementing caching strategies.

    **Authentication:** No authentication required for this endpoint.
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
