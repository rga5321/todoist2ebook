# todoist2ebook

Simple python script and calibre recipe to build an epub with your saved articles in todoist and send it to an email address.


![Index](img/cover.png)

![Index](img/article.png)

## How to use it

You have three options:
- Run the script using python
- Launch it from calibre
- Launch it using Docker (experimental

### Usage (standalone, recommended)

- Clone the project
- Create a venv ```python3 -m venv .venv```
- Activate it ```source .venv/bin/activate```
- Install dependencies:  
  ```pip3 install -r requirements.txt```
- Copy the .env sample and populate it ```cp .env.sample .env```
- Run the script ```(.venv) ~/todoist2ebook$ python3 main.py```

#### Running Tests

This project uses `pytest` for automated testing.

1. Ensure dependencies are installed (including `pytest` and `pytest-mock` which are in `requirements.txt`).
2. Run tests:
   ```bash
   pytest tests/
   ```


#### Parameters (.env)

- `URL_KEYWORD_EXCEPTIONS` = keywords in an URL that will result in its exclusion (example: `['jotdown','gastronomia']`)
- `CALIBRE_BINARY` = Path to the calibre `ebook-convert` binary (default: `ebook-convert`). Useful if you need to use a specific version (e.g. an older version due to bugs in the latest one).
- `ARCHIVE_DOWNLOADED` = True | False => Should the script close the tasks after retrieving the urls
- `TODOIST_PROJECT_ID` => Todoist project where the URLs will be recovered
- `TODOIST_API_KEY` => Your api KEY
- `SEND_EMAIL`=True | False => Should the script send the email?
- `SMTP_*` => Your server credentials
- `DESTINATION_EMAIL` => Where should the script send the epub

#### Workflow and File Conversions

The script performs the following conversion steps:

1. **Task Retrieval (API v1)** - Fetches tasks using the modern Todoist unified API (v1), replacing the deprecated REST API.
2. **EPUB Generation** - Creates an initial EPUB file from your Todoist saved articles (`-original.epub`).
3. **QR Code Addition** - Adds QR codes and source links to each article.
4. **Backup Generation** - Creates a backup version by converting the original EPUB to MOBI and back to EPUB (`-backup.epub`).
5. **Dual Email Delivery** - Sends **both** the original and backup files to your Kindle email.

**Why send two files?**

*   **Original File (`-original.epub`)**: Preserves the best possible formatting and styling. However, Amazon's "Send to Kindle" service can be finicky and sometimes rejects complex EPUBs or processes them incorrectly.
*   **Backup File (`-backup.epub`)**: The round-trip conversion (EPUB → MOBI → EPUB) "normalizes" the file structure. While it might look slightly less polished, it is highly reliable and almost always accepted by Amazon's service. By sending both, you ensure you get at least one readable copy, and usually the best-looking one too.

**Generated Files**

All generated files are retained for testing and verification:
- `todoist-{timestamp}-original.epub` - High-quality original EPUB (sent to Kindle)
- `todoist-{timestamp}-original.mobi` - Intermediate MOBI conversion
- `todoist-{timestamp}-backup.epub` - Compatibility-focused backup EPUB (sent to Kindle)

#### Output
 
 You should see something like:
 
 ```
 2025-06-15 17:11:05,958 -  INFO-  Start
 2025-06-15 17:11:05,959 -  INFO-  File name: todoist-2025-06-15_1711-original.epub
 2025-06-15 17:11:06,100 -  INFO-  Calibre version: ebook-convert (calibre 7.0.0)
 Conversion options changed from defaults:
   test: None
 1% Converting input to HTML...
 ...
 34% Download finished
 ...
 EPUB output written to /home/xxxx/todoist2ebook/todoist-2025-06-15_1711-original.epub
 Output saved to   /home/xxxx/todoist2ebook/todoist-2025-06-15_1711-original.epub
 2025-06-15 17:11:11,500 -  INFO-  Adding QR codes to EPUB
 2025-06-15 17:11:11,600 -  INFO-  Converting EPUB to MOBI: todoist-2025-06-15_1711-original.mobi
 2025-06-15 17:11:15,000 -  INFO-  Successfully converted to MOBI: todoist-2025-06-15_1711-original.mobi
 2025-06-15 17:11:15,100 -  INFO-  Converting MOBI back to EPUB: todoist-2025-06-15_1711-backup.epub
 2025-06-15 17:11:18,200 -  INFO-  Successfully converted back to EPUB: todoist-2025-06-15_1711-backup.epub
 2025-06-15 17:11:18,300 -  INFO-  Sending email to: xxxxxxx@kindle.com
 2025-06-15 17:11:19,500 -  INFO-  Email sent successfully to xxxxxxx@kindle.com
 2025-06-15 17:11:19,600 -  INFO-  Sending email to: xxxxxxx@kindle.com
 2025-06-15 17:11:20,800 -  INFO-  Email sent successfully to xxxxxxx@kindle.com
 2025-06-15 17:11:21,000 -  INFO-  End
 ```



### Calibre

Since calibre v8.9, the recipe is avalaible on calibre. Just click "fetch news", search the "Todoist" recipe, and fill the parameters

### Usage with Docker (experimental)

- Download the docker/env.local.sample to env.local and populate values
- In the same folder where env.local is, run ```docker run --rm -v "$PWD/env.local:/home/appuser/env.local" rga5321/todoist2ebook-arm64:latest``` or ```docker run --rm -v "$PWD/env.local:/home/appuser/env.local" rga5321/todoist2ebook-amd64:latest``` depending on your architecture


