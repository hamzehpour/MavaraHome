"""
The one place an uploaded image is processed.

Until now nothing resized anything: a file landed on disk exactly as it was
uploaded and was served back the same way. A 4000x3000 phone photo dropped
into the 38px logo slot shipped those 3MB to every visitor. Measured on a
realistic 4000x3000 JPEG (3.04MB): as a poster it becomes 59KB (-98%), as a
gallery image 276KB (-91%), as a member photo 5KB (-99.8%).

Honest split of where that comes from: the dimension cap is nearly all of
it, WebP adds another 10-14% over JPEG at these sizes. Both are worth
having, but WebP is the smaller half.

Deliberately DOWNSCALE-ONLY — never crops. The display frames crop with CSS
`object-fit: cover`, and keeping the whole image means a frame's
aspect-ratio can change later without every stored image becoming wrong.
The admin panel compensates by previewing uploads inside the real frame
shape, so the crop is visible before saving rather than a surprise after.

The box sizes in UPLOAD_PROFILES are the same numbers the panel's
`.upload-hint` texts promise the admin. That is not a coincidence and it is
enforced by a test (see test_bot.py, "upload hints match UPLOAD_PROFILES").
"""
import io
import logging

logger = logging.getLogger("mavara_bot")

# Refuse to even decode anything larger. Image.open() is lazy — it reads the
# header, not the pixels — so checking .size first is what keeps a
# decompression bomb from being expanded in memory. It stayed a guard rather
# than becoming the output size, which the profiles below now decide.
#
# Raised from the old 4000-per-side limit, which was a real-world blocker
# once these bytes started being downscaled anyway: a current iPhone photo
# is 4032x3024, so "take a photo of your receipt" hit the guard head-on.
# The pixel-count cap is the one that actually protects memory — 40MP is
# roughly 160MB decoded as RGBA, and covers every phone and DSLR — while
# the per-side cap catches long thin bombs that slip under it.
MAX_SOURCE_DIM = 8000
MAX_SOURCE_PIXELS = 40_000_000


class InvalidImage(Exception):
    """Bytes that Pillow can't decode as an image."""


class ImageTooLarge(Exception):
    """Real image, but larger than MAX_SOURCE_DIM on a side."""


class Profile:
    """Where an uploaded image ends up, and therefore how big it needs to be.

    box:     maximum (width, height). Aspect ratio is preserved and an image
             already smaller than the box is left at its own size.
    fmt:     Pillow format name to encode to.
    quality: lossy quality for WEBP/JPEG; ignored for PNG.
    """

    __slots__ = ("box", "fmt", "quality")

    def __init__(self, box, fmt="WEBP", quality=82):
        self.box, self.fmt, self.quality = box, fmt, quality


UPLOAD_PROFILES = {
    # --- admin uploads, served from bot/media/<kind>/ ---
    "poster":       Profile((900, 1000)),
    "portfolio":    Profile((900, 1200)),
    "gallery":      Profile((1600, 1600)),
    "team":         Profile((400, 400), quality=85),

    # PNG on purpose, not WebP. This one image leaves the website entirely
    # and is drawn into the ticket PDF by reportlab with mask="auto".
    # reportlab does read WebP (it delegates to Pillow — verified), but the
    # saving on a small logo is negligible and it is not worth introducing
    # an untested format into the path that generates customers' tickets.
    "ticket_logo":  Profile((400, 400), fmt="PNG"),

    # --- brand images: they OVERWRITE fixed static files whose paths and
    # formats the website's HTML hardcodes (<img src>, <link type>,
    # og:image), so the format is not ours to choose. ---
    "brand_logo":     Profile((512, 512), fmt="PNG"),
    "brand_favicon":  Profile((512, 512), fmt="WEBP", quality=90),
    "brand_og_image": Profile((1200, 1200), fmt="WEBP", quality=85),

    # --- customer payment receipts, stored in bot/private_media/ ---
    # Generous on purpose: nobody looks at a receipt for its beauty, but an
    # admin has to read the amount, date and reference number off it. Never
    # cropped. Re-encoding also strips EXIF, which on a phone photo means
    # the customer's GPS location stops being stored with it.
    "receipt":      Profile((2000, 2000), quality=80),
}

_EXT = {"WEBP": ".webp", "PNG": ".png", "JPEG": ".jpg", "GIF": ".gif"}


def _source_ext(pil_format: str | None) -> str:
    return _EXT.get((pil_format or "").upper(), ".bin")


def process_image(raw: bytes, kind: str) -> tuple[bytes, str]:
    """
    Returns (bytes_to_store, file_extension).

    Raises InvalidImage / ImageTooLarge — those are the caller's business,
    because they map to a 400 the admin needs to read. Anything else that
    goes wrong during the transform is swallowed and the ORIGINAL bytes are
    returned: an upload must never fail because the optimisation did.
    """
    from PIL import Image, ImageOps

    try:
        with Image.open(io.BytesIO(raw)) as probe:
            probe.verify()
    except Exception:
        raise InvalidImage()

    # verify() leaves the image unusable for anything else (Pillow's own
    # docs say so), so everything below reopens from the same bytes.
    try:
        with Image.open(io.BytesIO(raw)) as img:
            src_w, src_h = img.size
            src_format = img.format
            frames = getattr(img, "n_frames", 1)
    except Exception:
        raise InvalidImage()

    if src_w > MAX_SOURCE_DIM or src_h > MAX_SOURCE_DIM or src_w * src_h > MAX_SOURCE_PIXELS:
        raise ImageTooLarge()

    src_ext = _source_ext(src_format)

    # An animated GIF re-encoded as a still WebP loses its animation with no
    # error and no warning. Pass it through untouched instead.
    if frames > 1:
        return raw, src_ext

    profile = UPLOAD_PROFILES.get(kind)
    if profile is None:
        return raw, src_ext

    try:
        with Image.open(io.BytesIO(raw)) as img:
            # Phone cameras record orientation in EXIF rather than rotating
            # the pixels. Re-encoding without applying it first is how an
            # upload comes out sideways — this line is load-bearing, not
            # housekeeping.
            img = ImageOps.exif_transpose(img)

            needs_resize = img.size[0] > profile.box[0] or img.size[1] > profile.box[1]
            if needs_resize:
                # thumbnail(), not resize(): it preserves the aspect ratio
                # and never scales an image UP, so anything already under
                # the cap keeps its own size instead of being blown up.
                img.thumbnail(profile.box, Image.Resampling.LANCZOS)

            has_alpha = img.mode in ("RGBA", "LA") or (
                img.mode == "P" and "transparency" in img.info
            )
            img = img.convert("RGBA" if has_alpha else "RGB")

            out = io.BytesIO()
            if profile.fmt == "PNG":
                img.save(out, "PNG", optimize=True)
            else:
                img.save(out, profile.fmt, quality=profile.quality, method=4)
            processed = out.getvalue()
    except Exception:
        logger.exception("image processing failed for kind=%s — storing the original", kind)
        return raw, src_ext

    # A small already-optimised PNG icon is the real case here: re-encoding
    # it can cost bytes for nothing. If there was no resizing to justify the
    # rewrite and the result isn't smaller, keep what was uploaded.
    if not needs_resize and len(processed) >= len(raw):
        return raw, src_ext

    return processed, _EXT[profile.fmt]
