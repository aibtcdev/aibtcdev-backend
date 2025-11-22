# Video Support for X Posts - Feature Plan

## Overview

Add support for video media (videos, animated_gifs) from X/Twitter posts, stored as `videos: List[str]` alongside `images`. Use OpenAI-compatible `{"type": "video_url", "video_url": {"url": url, "detail": "auto"}}` format in AI messages. Parse via Twitter API `includes.media`; backward-compatible.

**Status**: Phase 1-2 ✅ Completed

## Tasks (Checklist)

### Phase 1: Models & Backend (DB Schema)

- [x] **1.1** Add `videos: Optional[List[str]] = None` to `XTweetBase`/`XTweetCreate` in `app/backend/models.py`.
- [x] **1.2** Supabase migration: `ALTER TABLE x_tweets ADD COLUMN videos text[]; UPDATE x_tweets SET videos = ARRAY[]::text[];` (run manually).
- [x] **1.3** Verify SupabaseBackend CRUD auto-handles `videos` (Pydantic model_dump).

### Phase 2: Ingestion (twitter_service.py)

- [x] **2.1** In `TweetRepository.store_tweet`: Parse `response.includes.media` → `images=[]` (photo), `videos=[]` (video/animated_gif).
- [x] **2.2** Pass `images`, `videos` to `XTweetCreate`; update tweet post-creation if needed.
- [x] **2.3** Update `TweetData` model: Add `videos: Optional[List[str]]`.

### Phase 3: Fetching/Processing (processors/twitter.py)

- [x] **3.1** `fetch_tweet`: Add `"videos": tweet.videos or []`.
- [x] **3.2** Add `extract_tweet_videos(tweet_data) → List[str]` (mirrors images).
- [x] **3.3** Add `format_tweet_videos(tweet_data, tweet_db_id) → List[Dict]` (`video_url` format, mirrors images).
- [x] **3.4** `format_tweet`: Add `<videos>{str(tweet.videos)}</videos>` XML.
- [x] **3.5** `process_tweets`: `tweet_media = tweet_images + tweet_videos`; return `(content, tweet_media)`.

### Phase 4: Media Utils (processors/images.py → media.py)

- [x] **4.1** Rename `images.py` → `media.py`; update imports.
- [x] **4.2** `process_images → process_media`: Handle images + videos (new `extract_video_urls` in utils.py).
- [x] **4.3** Add `format_videos(video_urls)` (mirrors `format_images`).
- [x] **4.4** `format_images_for_messages → format_media_for_messages(media)`.

### Phase 5: AI Workflows
- [x] **5.1** `evaluation_openrouter_v2.py`: `proposal_images → proposal_media`; append videos to `user_message_content`.
- [x] **5.2** `recommendation.py`/`metadata.py`: Extend `create_chat_messages` to handle `proposal_media` (images + videos).
- [x] **5.3** Updated metadata counters to `media_processed`.

### Phase 6: Utils & Tools
- [x] **6.1** `app/lib/utils.py`: Added `extract_video_urls(text)` (Twitter-focused regex + Content-Type verification).
- [x] **6.2** `tools/twitter.py`: Already exposes videos in media details (duration_ms etc.).
- [x] **6.3** `tweet_task.py`: No changes needed.

### Phase 7: Testing & Monitoring
- [x] **7.1** Test ingestion: Tweet w/video → DB has `videos`.
- [x] **7.2** Test AI: Evaluate tweet w/video → `messages` has `video_url`.
- [x] **7.3** Metrics: Update logs (`media_processed: {"images": N, "videos": M}`).

## Open Questions
**Resolved**: All questions addressed during implementation.

**Status**: ✅ Feature Complete

**Progress**: 7/7 | Last Updated: 2025-11-21
