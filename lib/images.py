import requests
from dotenv import load_dotenv
from litellm import image_generation

load_dotenv()


class ImageGenerationError(Exception):
    """Raised when image generation fails"""

    pass


def generate_image(prompt: str) -> str:
    """Generate an image URL using the specified prompt.

    Args:
        prompt: The prompt to generate the image from

    Returns:
        str: The URL of the generated image

    Raises:
        ImageGenerationError: If image generation fails
    """
    try:
        response = image_generation(model="dall-e-3", prompt=prompt)
        if not response or not response.data:
            raise ImageGenerationError("No response from image generation service")
        return response.data[0]["url"]
    except Exception as e:
        raise ImageGenerationError(f"Failed to generate image: {str(e)}") from e


def generate_token_image(name: str, symbol: str, description: str) -> bytes:
    """Generate a token image using the specified parameters.

    Args:
        name: Token name
        symbol: Token symbol
        description: Token description

    Returns:
        bytes: The image content in bytes

    Raises:
        ImageGenerationError: If image generation fails
    """
    prompt = f"Draw from iconic, yet not overplayed references (Bauhaus geometry, Swiss minimalism, NASA mission patches, mid-century graphics, Apples refined approach, and subtle 80s neon). Synthesize or pick styles based on {description} to create a bold, circular icon for {name}, featuring {symbol}. Keep it minimal, high-contrast, and recognizable at small sizes. Avoid clutter, extraneous text, or clichés. Aim for a universal, timeless, visually striking design."
    try:
        image_url = generate_image(prompt)
        if not image_url:
            raise ImageGenerationError("Failed to get image URL")

        response = requests.get(image_url)
        if response.status_code != 200:
            raise ImageGenerationError(
                f"Failed to download image: HTTP {response.status_code}"
            )

        if not response.content:
            raise ImageGenerationError("Downloaded image is empty")

        return response.content

    except ImageGenerationError as e:
        raise  # Re-raise ImageGenerationError as is
    except Exception as e:
        raise ImageGenerationError(
            f"Unexpected error generating token image: {str(e)}"
        ) from e
