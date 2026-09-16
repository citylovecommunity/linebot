from __future__ import annotations

import cloudinary
import cloudinary.uploader
from cloudinary import CloudinaryImage

from form_app.config import settings

cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
)


def derive_face_cropped_photo(source_url: str) -> tuple[str, str] | None:
    """Re-upload a remote image and return (photo_url, public_id) face-cropped to 400x400, or None on failure."""
    if not source_url:
        return None
    try:
        result = cloudinary.uploader.upload(source_url, folder="citylove/members")
    except Exception:
        return None
    photo_url = CloudinaryImage(result['public_id']).build_url(
        width=400, height=400, crop='thumb', gravity='face',
        quality='auto', format='webp', flags='awebp',
        secure=True,
    )
    return photo_url, result['public_id']
