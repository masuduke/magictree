"""
social_publisher.py
-------------------
Posts content to Instagram, YouTube Shorts, and TikTok.

Instagram: uses Meta Graph API (requires Business/Creator account)
YouTube:   uses YouTube Data API v3 with OAuth refresh token
TikTok:    uses TikTok Content Posting API
"""
import os
import time
import logging
import requests

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# CLOUDINARY  –  used to host images so Instagram API can fetch them via URL
# ─────────────────────────────────────────────────────────────────────────────

def _upload_to_cloudinary(file_path: str, cloudinary_url: str) -> str | None:
    """
    Uploads image or video and returns a public CDN URL.
    CLOUDINARY_URL format: cloudinary://api_key:api_secret@cloud_name
    """
    try:
        import cloudinary
        import cloudinary.uploader
        cloudinary.config(cloudinary_url=cloudinary_url)
        resource_type = 'video' if file_path.endswith('.mp4') else 'image'
        result = cloudinary.uploader.upload(
            file_path, resource_type=resource_type,
            folder='trading_bot', overwrite=True
        )
        return result.get('secure_url')
    except Exception as exc:
        logger.error(f"Cloudinary upload failed: {exc}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# INSTAGRAM  (Meta Graph API)
# ─────────────────────────────────────────────────────────────────────────────

def _ig_create_container(account_id: str, token: str, media_url: str,
                          caption: str, is_video: bool = False) -> str | None:
    endpoint = f"https://graph.facebook.com/v19.0/{account_id}/media"
    payload  = {
        'access_token': token,
        'caption':      caption,
    }
    if is_video:
        payload['video_url']   = media_url
        payload['media_type']  = 'REELS'
        payload['share_to_feed'] = 'true'
    else:
        payload['image_url']   = media_url

    r = requests.post(endpoint, data=payload, timeout=30)
    if r.ok:
        return r.json().get('id')
    logger.error(f"IG container error: {r.text}")
    return None


def _ig_publish(account_id: str, token: str, container_id: str) -> bool:
    endpoint = f"https://graph.facebook.com/v19.0/{account_id}/media_publish"
    r = requests.post(endpoint, data={
        'creation_id': container_id,
        'access_token': token
    }, timeout=30)
    if r.ok:
        logger.info(f"✅ Instagram published: {r.json()}")
        return True
    logger.error(f"IG publish error: {r.text}")
    return False


def _ig_carousel(account_id: str, token: str, image_urls: list[str], caption: str) -> bool:
    """Posts a carousel of images (up to 10)."""
    child_ids = []
    for url in image_urls[:10]:
        endpoint = f"https://graph.facebook.com/v19.0/{account_id}/media"
        r = requests.post(endpoint, data={
            'image_url':    url,
            'is_carousel_item': True,
            'access_token': token
        }, timeout=30)
        if r.ok:
            child_ids.append(r.json().get('id'))
        else:
            logger.warning(f"Carousel child failed: {r.text}")

    if not child_ids:
        return False

    # Create carousel container
    endpoint = f"https://graph.facebook.com/v19.0/{account_id}/media"
    r = requests.post(endpoint, data={
        'media_type':    'CAROUSEL',
        'children':      ','.join(child_ids),
        'caption':       caption,
        'access_token':  token
    }, timeout=30)
    if not r.ok:
        logger.error(f"Carousel container failed: {r.text}")
        return False

    container_id = r.json().get('id')
    time.sleep(3)
    return _ig_publish(account_id, token, container_id)


def post_instagram(media_files: dict, content: dict, cfg) -> bool:
    token      = cfg.INSTAGRAM_ACCESS_TOKEN
    account_id = cfg.INSTAGRAM_ACCOUNT_ID
    caption    = content.get('ig_caption', '')

    if not token or not account_id:
        logger.warning("Instagram credentials not set – skipping.")
        return False

    # Prefer video (Reel) if available, else carousel of slides
    if media_files.get('video') and os.path.exists(media_files['video']):
        url = _upload_to_cloudinary(media_files['video'], cfg.CLOUDINARY_URL)
        if url:
            cid = _ig_create_container(account_id, token, url, caption, is_video=True)
            if cid:
                time.sleep(10)  # Instagram needs time to process video
                return _ig_publish(account_id, token, cid)

    # Fallback: carousel of slide images
    slide_urls = []
    for slide_path in media_files.get('slides', []):
        if os.path.exists(slide_path):
            url = _upload_to_cloudinary(slide_path, cfg.CLOUDINARY_URL)
            if url:
                slide_urls.append(url)

    if slide_urls:
        return _ig_carousel(account_id, token, slide_urls, caption)

    logger.error("No media available for Instagram.")
    return False


# ─────────────────────────────────────────────────────────────────────────────
# YOUTUBE  (YouTube Data API v3)
# ─────────────────────────────────────────────────────────────────────────────

def _get_yt_access_token(cfg) -> str | None:
    """Uses refresh token to get a short-lived access token."""
    r = requests.post('https://oauth2.googleapis.com/token', data={
        'client_id':     cfg.YOUTUBE_CLIENT_ID,
        'client_secret': cfg.YOUTUBE_CLIENT_SECRET,
        'refresh_token': cfg.YOUTUBE_REFRESH_TOKEN,
        'grant_type':    'refresh_token',
    }, timeout=15)
    if r.ok:
        return r.json().get('access_token')
    logger.error(f"YouTube token refresh failed: {r.text}")
    return None


def post_youtube(media_files: dict, content: dict, cfg) -> bool:
    if not cfg.YOUTUBE_CLIENT_ID:
        logger.warning("YouTube credentials not set – skipping.")
        return False

    video_path = media_files.get('video')
    if not video_path or not os.path.exists(video_path):
        logger.warning("No video for YouTube – skipping.")
        return False

    access_token = _get_yt_access_token(cfg)
    if not access_token:
        return False

    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from google.oauth2.credentials import Credentials

        creds = Credentials(token=access_token)
        yt    = build('youtube', 'v3', credentials=creds)

        body = {
            'snippet': {
                'title':       content.get('yt_title', 'Trading Update'),
                'description': content.get('yt_description', ''),
                'tags':        ['trading', 'crypto', 'gold', 'investing', 'ai', 'bot'],
                'categoryId':  '22',  # People & Blogs
            },
            'status': {'privacyStatus': 'public', 'selfDeclaredMadeForKids': False}
        }

        media = MediaFileUpload(video_path, chunksize=-1, resumable=True,
                                mimetype='video/mp4')
        req   = yt.videos().insert(part=','.join(body.keys()), body=body, media_body=media)
        resp  = None
        while resp is None:
            _, resp = req.next_chunk()

        logger.info(f"✅ YouTube upload complete: {resp.get('id')}")
        return True

    except Exception as exc:
        logger.error(f"YouTube upload failed: {exc}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# TIKTOK  (Content Posting API)
# ─────────────────────────────────────────────────────────────────────────────

def post_tiktok(media_files: dict, content: dict, cfg) -> bool:
    if not cfg.TIKTOK_ACCESS_TOKEN:
        logger.warning("TikTok token not set – skipping.")
        return False

    video_path = media_files.get('video')
    if not video_path or not os.path.exists(video_path):
        logger.warning("No video for TikTok – skipping.")
        return False

    try:
        file_size = os.path.getsize(video_path)

        # Step 1: Initialise upload
        init_r = requests.post(
            'https://open.tiktokapis.com/v2/post/publish/video/init/',
            headers={'Authorization': f"Bearer {cfg.TIKTOK_ACCESS_TOKEN}",
                     'Content-Type': 'application/json; charset=UTF-8'},
            json={
                'post_info': {
                    'title':          content.get('tiktok_caption', ''),
                    'privacy_level':  'SELF_ONLY',   # change to PUBLIC_TO_EVERYONE when ready
                    'disable_duet':   False,
                    'disable_comment': False,
                    'disable_stitch': False,
                },
                'source_info': {
                    'source':           'FILE_UPLOAD',
                    'video_size':       file_size,
                    'chunk_size':       file_size,
                    'total_chunk_count': 1,
                }
            },
            timeout=20
        )

        if not init_r.ok:
            logger.error(f"TikTok init failed: {init_r.text}")
            return False

        upload_url = init_r.json()['data']['upload_url']

        # Step 2: Upload video
        with open(video_path, 'rb') as f:
            up_r = requests.put(
                upload_url,
                data=f,
                headers={
                    'Content-Type':  'video/mp4',
                    'Content-Range': f'bytes 0-{file_size-1}/{file_size}',
                    'Content-Length': str(file_size),
                },
                timeout=120
            )

        if up_r.status_code in (200, 201, 206):
            logger.info("✅ TikTok upload complete.")
            return True

        logger.error(f"TikTok upload error: {up_r.status_code} {up_r.text}")
        return False

    except Exception as exc:
        logger.error(f"TikTok post failed: {exc}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────────────────

def publish_all(media_files: dict, content: dict, cfg) -> dict:
    results = {}
    logger.info("📤 Publishing to social platforms…")

    results['instagram'] = post_instagram(media_files, content, cfg)
    results['youtube']   = post_youtube(media_files, content, cfg)
    results['tiktok']    = post_tiktok(media_files, content, cfg)

    for platform, ok in results.items():
        status = '✅' if ok else '⚠️ skipped/failed'
        logger.info(f"  {platform.capitalize()}: {status}")

    return results
