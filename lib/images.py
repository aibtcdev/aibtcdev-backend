import openai
import os
import requests
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")


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
        client = openai.OpenAI()
        response = client.images.generate(
            model="dall-e-3", quality="hd", prompt=prompt, n=1, size="1024x1024"
        )
        if not response or not response.data:
            raise ImageGenerationError("No response from image generation service")
        return response.data[0].url
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
    prompt = f"Create a single, bold circular icon for {name}, featuring {symbol} in a minimal geometric style that reflects the DAO's mission: {description}. Use only these colors: • Orange #FF4F03 • Electric Blue #0533D1 • Black #000000 • White #FFFFFF • Grey #58595B • Orange→Blue gradient (sparingly) Keep lines clean, shapes few, and contrast high for immediate recognition, drawing from Swiss minimalism or NASA-inspired design."
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
