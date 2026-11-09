# Codebase Analysis: `todoist2ebook`

The `todoist2ebook` project is a Python-based utility that extracts saved articles and links from a specified Todoist project, converts them into an ebook (EPUB format), and optionally emails the resulting files to a Kindle or other e-reader.

## Key Components

1.  **`main.py` (Orchestrator)**
    *   Acts as the main entry point for the application.
    *   Loads environment variables for configuration (Todoist credentials, SMTP settings for emailing, etc.) using `python-dotenv`. Values are sanitized by `clean_env_var`, which strips inline `#` comments and surrounding quotes/spaces.
    *   Invokes the Calibre command-line tool (`ebook-convert`) to build the initial EPUB using the `Todoist.recipe` file, passing configuration through `--recipe-specific-option` flags (`URL_KEYWORD_EXCEPTIONS`, `ARCHIVE_DOWNLOADED`, `TODOIST_PROJECT_ID`, `TODOIST_API_KEY`, `TODOIST_FAILED_ARTICLES_LABEL`).
    *   The initial output is named `todoist-{timestamp}-original.epub`.
    *   Calls the `epub_qr` module to add QR codes to the generated EPUB.
    *   Aborts if the generated EPUB contains no downloaded articles: `add_qr_to_epub` returns the number of articles processed, and if it is `0`, the file is deleted and the run exits (the "empty ebook" guard).
    *   Sends the original EPUB via email **before** the format conversion round-trip, when `SEND_EMAIL` is enabled.
    *   Performs a format conversion round-trip: EPUB → MOBI → EPUB. This produces a "backup" EPUB (`-backup.epub`) alongside the original (`-original.epub`). This process is meant to normalize the ebook structure to improve compatibility with Amazon's "Send to Kindle" service.
    *   Sends the backup EPUB via email after the round-trip.

2.  **`Todoist.recipe` (Calibre Recipe)**
    *   A custom Calibre `BasicNewsRecipe` script that defines how to fetch and parse the content.
    *   Uses the Todoist API (v1) to fetch tasks from a specific `TODOIST_PROJECT_ID` via `GET {TODOIST_API_URL}/api/v1/tasks?project_id=...` with a Bearer token.
    *   Accepts either a raw task list or a `{"results": [...]}` response shape; aborts on any other format.
    *   Extracts URLs from the task content, handling both raw URLs and Markdown-formatted links (`[title](url)`), and uses the Markdown link text as the title when available.
    *   Filters out articles based on an exception list (`URL_KEYWORD_EXCEPTIONS`).
    *   Groups the extracted links by domain (using `urlparse().netloc`, with `www.` stripped) and returns them to Calibre, which then fetches the web content and compiles it into an ebook.
    *   Can optionally close (archive) the tasks in Todoist after successfully fetching them (`ARCHIVE_DOWNLOADED`).
    *   Tracks download failures via `error_in_article_download`: failed articles are removed from the feed (to avoid empty articles), are **not** closed even when archiving is enabled, and are optionally tagged with `TODOIST_FAILED_ARTICLES_LABEL`.
    *   `cleanup()` handles archiving and failed-article labeling. Note: it hardcodes `https://api.todoist.com` for the close/label endpoints, ignoring the configurable `TODOIST_API_URL` used by `parse_index`.
    *   `_postprocess_html` prepends the article title as an `<h1>` and removes duplicate title headers; `extra_css` hides the Calibre navbar.
    *   `recipe.py` in the repo root is empty; the actual recipe is `Todoist.recipe`.

3.  **`epub_qr.py` (Post-processing)**
    *   Provides the `add_qr_to_epub` function, which modifies the EPUB in place and returns the number of articles processed.
    *   Unzips the EPUB into a temporary directory.
    *   Iterates through the HTML/XHTML files to find the original article URL (looking for `rel="calibre-downloaded-from"`).
    *   Generates a QR code image for the URL using the `qrcode` library and saves it as `qr_<html-stem>.png` next to the article's HTML file.
    *   Injects an `<img>` tag containing the QR code at the end of the article's `<body>`. (The docstring mentions also adding a `Source: URL` paragraph and preferring `<a rel="alternate">`, but the implementation does neither.)
    *   Repacks the EPUB file with the new images and modified HTML. The repack preserves file paths but uses the default ZIP storage settings.

## Workflow Summary

1.  **Extract:** The script connects to the Todoist API, retrieves tasks from a specified project, and extracts web URLs from them. Excluded URLs are skipped.
2.  **Convert:** Calibre downloads the content from the URLs and packages it into an EPUB file (`-original.epub`). Failed downloads are excluded and can be labeled in Todoist.
3.  **Enhance:** A QR code pointing to the source URL is appended to each article in the EPUB.
4.  **Guard:** If no articles were downloaded, the run aborts before conversion or delivery.
5.  **Deliver original:** The original EPUB is emailed (if configured).
6.  **Normalize:** The EPUB is converted to MOBI and back to EPUB to ensure it is structurally sound for Amazon's Kindle delivery.
7.  **Deliver backup:** The normalized backup EPUB (`-backup.epub`) is emailed. The intermediate `.mobi` file is left on disk.
