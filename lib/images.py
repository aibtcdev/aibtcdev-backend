import openai
import requests
from config import config

openai.api_key = config.api.openai_api_key


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
    prompt = f"""
    Design a bold, circular icon for {name}, showcasing the {symbol} in a minimal geometric style that reflects the DAOs {description}. Center on one iconic focal point, use negative space strategically, and maintain a flat or subtly patterned background. Limit the color palette to 2-3 key hues from the DAOs thematic palette (see guidelines below), with rare gradients for subtle emphasis. Geometry should be symmetrical and scalable. Vary the central symbol, accent colors, and minimal support elements to create a unique yet mission-driven design.

Guidelines
	1.	Central Symbol: Choose a simple, powerful shape (e.g. shield, star, rocket) that embodies the DAOs purpose.
	2.	Negative Space: Integrate hidden shapes or letters for subtle meaning.
	3.	Flat Background: Optionally include faint, geometric patterns (e.g. concentric circles, soft grid).
	4.	Color Adaptability:
	•	Sustainability: #28A745, #85C341, #FFFFFF
	•	Finance: #FFC107, #FFECB3, #58595B
	•	Tech/AI: #0533D1, #5D8BF4, #000000
	•	Creativity/Art: #800080, #D896FF, #FFFFFF
	•	Patriotism: #FF0000, #0533D1, #FFFFFF, #FFC107
	•	Custom: Pick 2-3 colors aligned with the DAOs theme.
	5.	Scalable Shapes: Stick to geometric forms (circles, triangles, lines) that work in small tokens or large prints.
	6.	Mission-Driven Variation: Adapt the main symbol, color selection, and subtle highlights to ensure each DAOs icon is distinct, memorable, and professionally cohesive.

Result
An easily recognizable, mission-aligned icon with one strong centerpiece, minimal but strategic support elements, and a streamlined color palette—scalable for all uses from tiny badges to large banners.
"""
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
