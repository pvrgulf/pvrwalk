
from pathlib import Path
from html import escape
from urllib.parse import quote
import json
import re

from PIL import Image, ImageOps


# =========================================
# SETTINGS
# =========================================

GALLERY_ROOT = Path(__file__).resolve().parent

THUMBNAIL_FOLDER = "thumbnails"

THUMBNAIL_WIDTH = 480

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

GENERATED_MARKER = "<!-- CAMBO-WALKS-GENERATED-GALLERY -->"


# =========================================
# GENERAL HELPERS
# =========================================

def natural_sort_key(value):
    """Sort filenames naturally, so photo-2 comes before photo-10."""
    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", str(value))
    ]


def caption_from_filename(filename):
    """Create a readable caption from a photograph filename."""
    caption = Path(filename).stem

    caption = caption.replace("-", " ")
    caption = caption.replace("_", " ")

    caption = re.sub(r"\s+", " ", caption)

    return caption.strip().capitalize()


def display_title(folder_name):
    """Create a basic title from a folder name."""
    title = folder_name.replace("-", " ")
    title = title.replace("_", " ")

    return title.title()


def relative_url(path):
    """Return a browser-safe relative URL."""
    return quote(path.as_posix(), safe="/")


# =========================================
# READ GALLERY SETTINGS
# =========================================

def read_gallery_settings(folder):
    """
    Read optional title, description and cover from gallery.json.
    Use the folder name if the file or title is absent.
    """

    json_file = folder / "gallery.json"

    settings = {
        "title": display_title(folder.name),
        "description": "",
        "cover": ""
    }

    if not json_file.exists():
        return settings

    try:
        with json_file.open("r", encoding="utf-8-sig") as file:
            data = json.load(file)

    except (json.JSONDecodeError, OSError) as error:
        raise ValueError(
            f"Problem reading {json_file}:\n{error}"
        )

    if not isinstance(data, dict):
        raise ValueError(
            f"{json_file} must contain a JSON object."
        )

    if isinstance(data.get("title"), str) and data["title"].strip():
        settings["title"] = data["title"].strip()

    if isinstance(data.get("description"), str):
        settings["description"] = data["description"].strip()

    if isinstance(data.get("cover"), str):
        settings["cover"] = data["cover"].strip()

    return settings


# =========================================
# THUMBNAIL MANAGEMENT
# =========================================

def make_thumbnail(source, destination):
    """Create a proportionally sized thumbnail."""

    destination.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(source) as image:

        image = ImageOps.exif_transpose(image)

        image.thumbnail((THUMBNAIL_WIDTH, THUMBNAIL_WIDTH * 2))

        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGB")

        image.save(
            destination,
            quality=85,
            optimize=True
        )


def clean_old_thumbnails(folder, photos):
    """
    Remove thumbnails whose original photographs
    are no longer present in the gallery.
    """

    thumbnail_dir = folder / THUMBNAIL_FOLDER

    if not thumbnail_dir.exists():
        return

    current_names = {photo.name for photo in photos}

    for item in thumbnail_dir.iterdir():

        if item.is_file() and item.name not in current_names:

            print(f"  Removing old thumbnail: {item.name}")

            item.unlink()

        elif item.is_dir():

            print(f"  Removing unexpected thumbnail subfolder: {item.name}")

            import shutil
            shutil.rmtree(item)

    # Remove the thumbnail directory if it is now empty.
    if thumbnail_dir.exists() and not any(thumbnail_dir.iterdir()):
        thumbnail_dir.rmdir()


def update_thumbnails(folder, photos):
    """Create missing or outdated thumbnails."""

    thumbnail_dir = folder / THUMBNAIL_FOLDER

    thumbnail_dir.mkdir(exist_ok=True)

    for photo in photos:

        thumbnail = thumbnail_dir / photo.name

        needs_update = (
            not thumbnail.exists()
            or thumbnail.stat().st_mtime < photo.stat().st_mtime
        )

        if needs_update:

            print(f"  Creating thumbnail: {photo.name}")

            make_thumbnail(photo, thumbnail)


# =========================================
# CREATE INDIVIDUAL GALLERY PAGE
# =========================================

def gallery_page(folder, photos, settings):

    title = settings["title"]
    description = settings["description"]

    cards = []

    for photo in photos:

        thumbnail = Path(THUMBNAIL_FOLDER) / photo.name

        caption = caption_from_filename(photo.name)

        original_url = relative_url(Path(photo.name))

        thumbnail_url = relative_url(thumbnail)

        cards.append(f"""
        <a class="gallery-photo zoom"
           href="{original_url}"
           data-gallery="{escape(folder.name, quote=True)}"
           data-caption="{escape(caption, quote=True)}">

            <img src="{thumbnail_url}"
                 alt="{escape(caption, quote=True)}"
                 loading="lazy">

            <span class="photo-caption">{escape(caption)}</span>

        </a>
        """)

    description_html = (
        f'<p class="gallery-description">{escape(description)}</p>'
        if description else ""
    )

    page = f"""<!doctype html>
{GENERATED_MARKER}
<html lang="en">

<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">

    <title>{escape(title)} — Cambo Walks</title>

    <link rel="stylesheet" href="../gallery.css">
    <link rel="stylesheet" href="../../assets/css/lightbox.css">
</head>

<body>

    <main class="gallery-page">

        <header class="gallery-header">

            <h1>{escape(title)}</h1>

            <a href="../index.html" class="gallery-back">
                ← All galleries
            </a>

        </header>

        {description_html}

        <section class="photo-grid">

            {''.join(cards)}

        </section>

        <footer class="gallery-footer">
            <a href="../../home.html">Cambo Walks home</a>
        </footer>

    </main>

    <script src="../../assets/js/lightbox.js"></script>

</body>
</html>
"""

    (folder / "index.html").write_text(
        page,
        encoding="utf-8"
    )


# =========================================
# CREATE MAIN GALLERY LISTING
# =========================================

def main_gallery_page(galleries):

    cards = []

    for folder, photos, settings in galleries:

        title = settings["title"]

        description = settings["description"]

        # Use the nominated cover photograph if valid.
        # Otherwise retain the original first-photo behaviour.
        cover_name = settings.get("cover", "")

        cover_photo = next(
            (photo for photo in photos if photo.name == cover_name),
            photos[0]
        )

        thumbnail = (
            Path(folder.name)
            / THUMBNAIL_FOLDER
            / cover_photo.name
        )

        description_html = (
            f'<small>{escape(description)}</small>'
            if description else ""
        )

        cards.append(f"""
        <a class="gallery-card"
           href="{quote(folder.name)}/index.html">

            <img src="{relative_url(thumbnail)}"
                 alt="{escape(title, quote=True)}"
                 loading="lazy">

            <span>{escape(title)}</span>

            <small>{len(photos)} photographs</small>

            {description_html}

        </a>
        """)

    page = f"""<!doctype html>
{GENERATED_MARKER}
<html lang="en">

<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">

    <title>Garden Galleries — Cambo Walks</title>

    <link rel="stylesheet" href="gallery.css">
</head>

<body>

    <main class="gallery-page">

        <header class="gallery-header">

            <h1>Garden Galleries</h1>

            <a href="../home.html" class="gallery-back">
                ← Cambo Walks home
            </a>

        </header>

        <section class="gallery-list">

            {''.join(cards) if cards else '<p>No photographs found yet.</p>'}

        </section>

    </main>

</body>
</html>
"""

    (GALLERY_ROOT / "index.html").write_text(
        page,
        encoding="utf-8"
    )


# =========================================
# MAIN BUILDER
# =========================================

def main():

    galleries = []

    print()
    print("========================================")
    print("       CAMBO WALKS GALLERY BUILDER")
    print("========================================")
    print()

    for folder in sorted(
        GALLERY_ROOT.iterdir(),
        key=lambda item: natural_sort_key(item.name)
    ):

        if not folder.is_dir():
            continue

        if folder.name.startswith("_"):
            continue

        if folder.name == THUMBNAIL_FOLDER:
            continue

        photos = sorted(
            (
                item for item in folder.iterdir()
                if item.is_file()
                and item.suffix.lower() in IMAGE_EXTENSIONS
            ),
            key=lambda item: natural_sort_key(item.name)
        )

        print(f"Checking folder: {folder.name}")

        # Remove obsolete thumbnails even if no photographs remain.
        clean_old_thumbnails(folder, photos)

        if not photos:
            print("  No photographs found. Skipping gallery.")
            print()
            continue

        settings = read_gallery_settings(folder)

        # Check that a nominated cover photograph exists.
        cover = settings.get("cover", "")

        if cover and cover not in {photo.name for photo in photos}:
            print(
                f"  WARNING: Cover photograph '{cover}' was not found. "
                "Using the first photograph instead."
            )
            settings["cover"] = ""

        print(f"  Title: {settings['title']}")
        print(f"  Photographs: {len(photos)}")

        update_thumbnails(folder, photos)

        gallery_page(folder, photos, settings)

        galleries.append((folder, photos, settings))

        print()

    # Always rebuild the main gallery listing.
    main_gallery_page(galleries)

    print("========================================")
    print(f"Finished. {len(galleries)} gallery folder(s) processed.")
    print("========================================")
    print()


# =========================================
# RUN BUILDER
# =========================================

if __name__ == "__main__":

    try:
        main()

    except Exception as error:

        print()
        print("GALLERY BUILDER ERROR")
        print("---------------------")
        print(error)

        raise SystemExit(1)

