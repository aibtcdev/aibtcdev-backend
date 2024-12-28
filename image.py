from db.factory import db
from dotenv import load_dotenv
from lib.images import generate_token_image

# Load environment variables
load_dotenv()


def main():
    imageBytes = generate_token_image(
        name="test",
        symbol="test",
        description="test description",
    )
    print("Created image bytes")
    publicImageUrl = db.upload_file(
        "test.png",
        imageBytes,
    )
    print(publicImageUrl)


if __name__ == "__main__":
    main()
