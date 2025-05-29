from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID

from backend.factory import backend
from backend.models import (
    QueueMessage,
    QueueMessageBase,
    QueueMessageFilter,
    QueueMessageType,
    XCredsFilter,
)
import re
from io import BytesIO
from urllib.parse import urlparse

import requests
import tweepy

from lib.logger import configure_logger
from lib.twitter import TwitterService
from lib.utils import extract_image_urls
from services.discord import create_discord_service
from services.runner.base import BaseTask, JobContext, RunnerConfig, RunnerResult

logger = configure_logger(__name__)


@dataclass
class TweetProcessingResult(RunnerResult):
    """Result of tweet processing operation."""

    tweet_id: Optional[str] = None
    dao_id: Optional[UUID] = None


class TweetTask(BaseTask[TweetProcessingResult]):
    """Task for sending tweets."""

    def __init__(self, config: Optional[RunnerConfig] = None):
        super().__init__(config)
        self._pending_messages: Optional[List[QueueMessage]] = None
        self.twitter_service = None

    def _split_text_into_chunks(self, text: str, limit: int = 280) -> List[str]:
        """Split text into chunks not exceeding the limit without cutting words."""
        words = text.split()
        chunks = []
        current = ""
        for word in words:
            if len(current) + len(word) + (1 if current else 0) <= limit:
                current = f"{current} {word}".strip()
            else:
                if current:
                    chunks.append(current)
                current = word
        if current:
            chunks.append(current)
        return chunks

    def _get_extension(self, url: str) -> str:
        path = urlparse(url).path.lower()
        for ext in [".png", ".jpg", ".jpeg", ".gif"]:
            if path.endswith(ext):
                return ext
        return ".jpg"

    def _post_tweet_with_media(
        self,
        image_url: str,
        text: str,
        reply_id: Optional[str] = None,
    ):
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(image_url, headers=headers, timeout=10)
            response.raise_for_status()
            auth = tweepy.OAuth1UserHandler(
                self.twitter_service.consumer_key,
                self.twitter_service.consumer_secret,
                self.twitter_service.access_token,
                self.twitter_service.access_secret,
            )
            api = tweepy.API(auth)
            extension = self._get_extension(image_url)
            media = api.media_upload(
                filename=f"image{extension}",
                file=BytesIO(response.content),
            )

            client = tweepy.Client(
                consumer_key=self.twitter_service.consumer_key,
                consumer_secret=self.twitter_service.consumer_secret,
                access_token=self.twitter_service.access_token,
                access_token_secret=self.twitter_service.access_secret,
            )

            result = client.create_tweet(
                text=text,
                media_ids=[media.media_id_string],
                reply_in_reply_to_tweet_id=reply_id,
            )
            if result and result.data:
                return type("Obj", (), {"id": result.data["id"]})()
        except Exception as e:
            logger.error(f"Failed to post tweet with media: {str(e)}")
        return None

    async def _initialize_twitter_service(self, dao_id: UUID) -> bool:
        """Initialize Twitter service with credentials for the given DAO."""
        try:
            # Get Twitter credentials for the DAO
            creds = backend.list_x_creds(filters=XCredsFilter(dao_id=dao_id))
            if not creds:
                logger.error(f"No Twitter credentials found for DAO {dao_id}")
                return False

            # Initialize Twitter service with the credentials
            self.twitter_service = TwitterService(
                consumer_key=creds[0].consumer_key,
                consumer_secret=creds[0].consumer_secret,
                client_id=creds[0].client_id,
                client_secret=creds[0].client_secret,
                access_token=creds[0].access_token,
                access_secret=creds[0].access_secret,
            )
            await self.twitter_service._ainitialize()
            logger.debug(f"Initialized Twitter service for DAO {dao_id}")
            return True

        except Exception as e:
            logger.error(f"Error initializing Twitter service: {str(e)}", exc_info=True)
            return False

    async def _validate_config(self, context: JobContext) -> bool:
        """Validate task configuration."""
        try:
            # No specific config validation needed as credentials are per-DAO
            return True
        except Exception as e:
            logger.error(f"Error validating tweet task config: {str(e)}", exc_info=True)
            return False

    async def _validate_prerequisites(self, context: JobContext) -> bool:
        """Validate task prerequisites."""
        try:
            # Cache pending messages for later use
            self._pending_messages = backend.list_queue_messages(
                filters=QueueMessageFilter(
                    type=QueueMessageType.TWEET, is_processed=False
                )
            )
            return True
        except Exception as e:
            logger.error(
                f"Error validating tweet prerequisites: {str(e)}", exc_info=True
            )
            self._pending_messages = None
            return False

    async def _validate_task_specific(self, context: JobContext) -> bool:
        """Validate task-specific conditions."""
        try:
            if not self._pending_messages:
                logger.debug("No pending tweet messages found")
                return False

            message_count = len(self._pending_messages)
            if message_count > 0:
                logger.debug(f"Found {message_count} pending tweet messages")
                return True

            logger.debug("No pending tweet messages to process")
            return False

        except Exception as e:
            logger.error(f"Error in tweet task validation: {str(e)}", exc_info=True)
            return False

    async def _validate_message(
        self, message: QueueMessage
    ) -> Optional[TweetProcessingResult]:
        """Validate a single message before processing."""
        try:
            # Check if message exists
            if not message.message:
                return TweetProcessingResult(
                    success=False,
                    message="Tweet message is empty",
                    tweet_id=message.tweet_id,
                )

            # Extract tweet text from the message field
            tweet_text = None
            if isinstance(message.message, dict) and "message" in message.message:
                tweet_text = message.message["message"]
            else:
                return TweetProcessingResult(
                    success=False,
                    message=f"Unsupported tweet message format: {message.message}",
                    tweet_id=message.tweet_id,
                )

            if not tweet_text:
                return TweetProcessingResult(
                    success=False,
                    message="Tweet message content is empty",
                    tweet_id=message.tweet_id,
                )

            if not message.dao_id:
                return TweetProcessingResult(
                    success=False,
                    message="Tweet message has no dao_id",
                    dao_id=None,
                )

            # No need to modify the message structure, keep it as is
            return None

        except Exception as e:
            logger.error(
                f"Error validating message {message.id}: {str(e)}", exc_info=True
            )
            return TweetProcessingResult(
                success=False,
                message=f"Error validating message: {str(e)}",
                error=e,
                tweet_id=message.tweet_id if hasattr(message, "tweet_id") else None,
                dao_id=message.dao_id if hasattr(message, "dao_id") else None,
            )

    async def _process_tweet_message(
        self, message: QueueMessage
    ) -> TweetProcessingResult:
        """Process a single tweet message."""
        try:
            # Validate message first
            validation_result = await self._validate_message(message)
            if validation_result:
                return validation_result

            # Initialize Twitter service for this DAO
            if not await self._initialize_twitter_service(message.dao_id):
                return TweetProcessingResult(
                    success=False,
                    message=f"Failed to initialize Twitter service for DAO: {message.dao_id}",
                    dao_id=message.dao_id,
                )

            # Extract tweet text directly from the message format
            original_text = message.message["message"]
            logger.info(f"Sending tweet for DAO {message.dao_id}")
            logger.debug(f"Tweet content: {original_text}")

            # Look for image URLs in the text
            image_urls = extract_image_urls(original_text)
            image_url = image_urls[0] if image_urls else None
            tweet_text = original_text

            if image_url:
                tweet_text = re.sub(re.escape(image_url), "", original_text).strip()
                tweet_text = re.sub(r"\s+", " ", tweet_text)

            # Split tweet text if necessary
            chunks = self._split_text_into_chunks(tweet_text)
            previous_tweet_id = message.tweet_id
            tweet_response = None

            for index, chunk in enumerate(chunks):
                if index == 0 and image_url:
                    tweet_response = self._post_tweet_with_media(
                        image_url=image_url,
                        text=chunk,
                        reply_id=previous_tweet_id,
                    )
                else:
                    tweet_response = await self.twitter_service._apost_tweet(
                        text=chunk,
                        reply_in_reply_to_tweet_id=previous_tweet_id,
                    )

                if not tweet_response:
                    return TweetProcessingResult(
                        success=False,
                        message="Failed to send tweet",
                        dao_id=message.dao_id,
                        tweet_id=previous_tweet_id,
                    )

                logger.info(f"Successfully posted tweet {tweet_response.id}")
                logger.debug(f"Tweet ID: {tweet_response.id}")
                previous_tweet_id = tweet_response.id

            # Discord Service
            try:
                discord_service = create_discord_service()

                if discord_service:
                    embeds = None
                    if image_url:
                        embeds = [{"image": {"url": image_url}}]
                    discord_result = discord_service.send_message(
                        tweet_text, embeds=embeds
                    )
                    logger.info(f"Discord message sent: {discord_result['success']}")

            except Exception as e:
                logger.warning(f"Failed to send Discord message: {str(e)}")

            return TweetProcessingResult(
                success=True,
                message="Successfully sent tweet",
                tweet_id=previous_tweet_id,
                dao_id=message.dao_id,
            )

        except Exception as e:
            logger.error(
                f"Error processing tweet message {message.id}: {str(e)}", exc_info=True
            )
            return TweetProcessingResult(
                success=False,
                message=f"Error sending tweet: {str(e)}",
                error=e,
                tweet_id=message.tweet_id if hasattr(message, "tweet_id") else None,
                dao_id=message.dao_id if hasattr(message, "dao_id") else None,
            )

    async def _execute_impl(self, context: JobContext) -> List[TweetProcessingResult]:
        """Execute tweet sending task."""
        results: List[TweetProcessingResult] = []
        try:
            if not self._pending_messages:
                return results

            processed_count = 0
            success_count = 0

            for message in self._pending_messages:
                logger.debug(f"Processing tweet message: {message.id}")
                result = await self._process_tweet_message(message)
                results.append(result)
                processed_count += 1

                if result.success:
                    success_count += 1
                    backend.update_queue_message(
                        queue_message_id=message.id,
                        update_data=QueueMessageBase(is_processed=True),
                    )
                    logger.debug(f"Marked message {message.id} as processed")

            logger.debug(
                f"Task metrics - Processed: {processed_count}, Successful: {success_count}"
            )

            return results

        except Exception as e:
            logger.error(f"Error in tweet task: {str(e)}", exc_info=True)
            results.append(
                TweetProcessingResult(
                    success=False,
                    message=f"Error in tweet task: {str(e)}",
                    error=e,
                )
            )
            return results


tweet_task = TweetTask()
