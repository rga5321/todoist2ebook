import os
import posixpath
import sys
import zipfile

from bs4 import BeautifulSoup
from xml.dom import minidom

# Add parent directory to path to import local modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epub_sections import remove_empty_sections


def _rel(target, from_file):
    return posixpath.relpath(target, posixpath.dirname(from_file) or ".")


def _feed_page(section, sections, index_name="index.html", labels=None):
    labels = labels or {
        "main": "Main menu",
        "previous": "Previous section",
        "next": "Next section",
    }
    index = sections.index(section)
    previous = sections[index - 1] if index > 0 else None
    following = sections[index + 1] if index + 1 < len(sections) else None

    nav = [f'| <a href="{_rel(index_name, section["href"])}">{labels["main"]}</a> |']
    if previous:
        nav.append(
            f'<a href="{_rel(previous["href"], section["href"])}">'
            f'{labels["previous"]}</a> |'
        )
    if following:
        nav.append(
            f'<a href="{_rel(following["href"], section["href"])}">'
            f'{labels["next"]}</a> |'
        )
    navbar = " ".join(nav)

    articles = "".join(
        f'<li id="article_{i}" class="calibre7">'
        f'<a href="{article["href"]}" class="article">{article["title"]}</a>'
        "</li>"
        for i, article in enumerate(section["articles"])
    )

    return f"""<?xml version='1.0' encoding='utf-8'?>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head><title>{section["title"]}</title></head>
  <body class="calibre">
    <div class="calibre_navbar">{navbar}</div>
    <div class="calibre1">
      <h2 class="calibre_feed_title">{section["title"]}</h2>
      <ul class="calibre_feed_list">{articles}</ul>
      <div class="calibre_navbar">{navbar}</div>
    </div>
  </body>
</html>"""


def _article_page(title):
    return f"""<?xml version='1.0' encoding='utf-8'?>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head><title>{title}</title></head>
  <body><h1>{title}</h1></body>
</html>"""


def _build_epub(
    path, sections, omit_files=None, index_name="index.html", nav_labels=None
):
    """Create a minimal Calibre-style EPUB.

    ``sections`` is a list of dicts with ``href``, ``title`` and ``articles``
    (each article also has ``href`` relative to the section directory).
    Files listed in ``omit_files`` are referenced but not written, which
    simulates a page that disappeared. ``index_name`` mirrors Calibre's habit
    of renaming duplicate output filenames, and ``nav_labels`` customizes the
    navbar text (Calibre localizes it).
    """
    omit_files = set(omit_files or ())

    feed_items = []
    manifest = [
        '<item id="titlepage" href="titlepage.xhtml" media-type="application/xhtml+xml"/>',
        f'<item id="id4" href="{index_name}" media-type="application/xhtml+xml"/>',
    ]
    spine = ['<itemref idref="titlepage"/>', '<itemref idref="id4"/>']
    nav_points = []
    files = {}

    order = 1
    for section_index, section in enumerate(sections):
        feed_items.append(
            f'<li id="feed_{section_index}" class="calibre5">'
            f'<a href="{section["href"]}" class="feed">{section["title"]}</a>'
            "</li>"
        )

        feed_id = f"id{section_index + 1}"
        manifest.append(
            f'<item id="{feed_id}" href="{section["href"]}" '
            'media-type="application/xhtml+xml"/>'
        )
        spine.append(f'<itemref idref="{feed_id}"/>')

        if section["href"] not in omit_files:
            files[section["href"]] = _feed_page(
                section, sections, index_name=index_name, labels=nav_labels
            )

        nav_points.append(
            f'<navPoint id="num_{order}" playOrder="{order}" class="chapter">'
            f'<navLabel><text>{section["title"]}</text></navLabel>'
            f'<content src="{section["href"]}"/>'
        )
        order += 1

        for article_index, article in enumerate(section["articles"]):
            article_href = posixpath.join(
                posixpath.dirname(section["href"]), article["href"]
            )
            article_id = f"art_{section_index}_{article_index}"
            manifest.append(
                f'<item id="{article_id}" href="{article_href}" '
                'media-type="application/xhtml+xml"/>'
            )
            spine.append(f'<itemref idref="{article_id}"/>')
            if article_href not in omit_files:
                files[article_href] = _article_page(article["title"])

            nav_points.append(
                f'<navPoint id="num_{order}" playOrder="{order}" class="chapter">'
                f'<navLabel><text>{article["title"]}</text></navLabel>'
                f'<content src="{article_href}"/></navPoint>'
            )
            order += 1

        nav_points.append("</navPoint>")

    files["mimetype"] = "application/epub+zip"
    files["titlepage.xhtml"] = _article_page("Cover")
    files[index_name] = (
        "<?xml version='1.0' encoding='utf-8'?>\n"
        '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Todoist</title></head>'
        '<body><ul class="calibre_feed_list">'
        + "".join(feed_items)
        + "</ul></body></html>"
    )
    files["toc.ncx"] = (
        "<?xml version='1.0' encoding='utf-8'?>\n"
        '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">'
        "<navMap>" + "".join(nav_points) + "</navMap></ncx>"
    )
    files["content.opf"] = (
        "<?xml version='1.0' encoding='utf-8'?>\n"
        '<package xmlns="http://www.idpf.org/2007/opf" version="2.0">'
        "<manifest>" + "".join(manifest) + "</manifest>"
        "<spine>" + "".join(spine) + "</spine></package>"
    )

    with zipfile.ZipFile(path, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)


def _codes(epub_path):
    with zipfile.ZipFile(epub_path, "r") as archive:
        return archive.namelist()


def _html(epub_path, name):
    with zipfile.ZipFile(epub_path, "r") as archive:
        return BeautifulSoup(archive.read(name), "html.parser")


def _xml(epub_path, name):
    with zipfile.ZipFile(epub_path, "r") as archive:
        return minidom.parseString(archive.read(name))


def test_removes_empty_section_and_updates_metadata(tmp_path):
    epub_path = str(tmp_path / "test.epub")
    sections = [
        {"href": "feed_0/index_u1.html", "title": "elpais.com", "articles": []},
        {
            "href": "feed_1/index_u3.html",
            "title": "sergeykuhne.com",
            "articles": [
                {"href": "article_0/index_u2.html", "title": "An article"}
            ],
        },
    ]
    _build_epub(epub_path, sections)

    assert remove_empty_sections(epub_path) == 1

    names = _codes(epub_path)
    assert "feed_0/index_u1.html" not in names
    assert "feed_1/index_u3.html" in names
    assert "feed_1/article_0/index_u2.html" in names

    index = _html(epub_path, "index.html")
    assert [link["href"] for link in index.select("a.feed")] == [
        "feed_1/index_u3.html"
    ]

    toc = _xml(epub_path, "toc.ncx")
    sources = [
        node.getAttribute("src") for node in toc.getElementsByTagName("content")
    ]
    assert "feed_0/index_u1.html" not in sources
    assert "feed_1/index_u3.html" in sources
    orders = [
        node.getAttribute("playOrder")
        for node in toc.getElementsByTagName("navPoint")
    ]
    assert orders == [str(i) for i in range(1, len(orders) + 1)]

    opf = _xml(epub_path, "content.opf")
    hrefs = [node.getAttribute("href") for node in opf.getElementsByTagName("item")]
    assert "feed_0/index_u1.html" not in hrefs
    assert "feed_1/index_u3.html" in hrefs
    idrefs = [
        node.getAttribute("idref") for node in opf.getElementsByTagName("itemref")
    ]
    assert "id1" not in idrefs
    assert "id2" in idrefs

    feed_page = _html(epub_path, "feed_1/index_u3.html")
    text = feed_page.get_text(" ", strip=True)
    assert "Previous section" not in text
    assert "Next section" not in text


def test_rewires_navigation_across_removed_section(tmp_path):
    epub_path = str(tmp_path / "test.epub")
    sections = [
        {
            "href": "feed_0/index_u1.html",
            "title": "first.com",
            "articles": [{"href": "article_0/a.html", "title": "First"}],
        },
        {"href": "feed_1/index_u2.html", "title": "empty.com", "articles": []},
        {
            "href": "feed_2/index_u3.html",
            "title": "third.com",
            "articles": [{"href": "article_0/c.html", "title": "Third"}],
        },
    ]
    _build_epub(epub_path, sections)

    assert remove_empty_sections(epub_path) == 1

    first_page = _html(epub_path, "feed_0/index_u1.html")
    next_link = first_page.find("a", string=lambda value: value and "Next section" in value)
    assert next_link is not None
    assert posixpath.normpath(
        posixpath.join(posixpath.dirname("feed_0/index_u1.html"), next_link["href"])
    ) == "feed_2/index_u3.html"

    third_page = _html(epub_path, "feed_2/index_u3.html")
    previous_link = third_page.find(
        "a", string=lambda value: value and "Previous section" in value
    )
    assert previous_link is not None
    assert posixpath.normpath(
        posixpath.join(
            posixpath.dirname("feed_2/index_u3.html"), previous_link["href"]
        )
    ) == "feed_0/index_u1.html"


def test_no_empty_sections_returns_zero(tmp_path):
    epub_path = str(tmp_path / "test.epub")
    sections = [
        {
            "href": "feed_0/index_u1.html",
            "title": "first.com",
            "articles": [{"href": "article_0/a.html", "title": "First"}],
        },
        {
            "href": "feed_1/index_u2.html",
            "title": "second.com",
            "articles": [{"href": "article_0/b.html", "title": "Second"}],
        },
    ]
    _build_epub(epub_path, sections)
    before = set(_codes(epub_path))

    assert remove_empty_sections(epub_path) == 0
    assert set(_codes(epub_path)) == before


def test_missing_section_page_is_removed(tmp_path):
    epub_path = str(tmp_path / "test.epub")
    sections = [
        {"href": "feed_0/index_u1.html", "title": "missing.com", "articles": []},
        {
            "href": "feed_1/index_u2.html",
            "title": "second.com",
            "articles": [{"href": "article_0/b.html", "title": "Second"}],
        },
    ]
    _build_epub(epub_path, sections, omit_files={"feed_0/index_u1.html"})

    assert remove_empty_sections(epub_path) == 1
    index = _html(epub_path, "index.html")
    assert [link["href"] for link in index.select("a.feed")] == [
        "feed_1/index_u2.html"
    ]


def test_missing_article_target_makes_section_empty(tmp_path):
    epub_path = str(tmp_path / "test.epub")
    sections = [
        {
            "href": "feed_0/index_u1.html",
            "title": "broken.com",
            "articles": [{"href": "article_0/a.html", "title": "Broken"}],
        },
        {
            "href": "feed_1/index_u2.html",
            "title": "second.com",
            "articles": [{"href": "article_0/b.html", "title": "Second"}],
        },
    ]
    _build_epub(
        epub_path, sections, omit_files={"feed_0/article_0/a.html"}
    )

    assert remove_empty_sections(epub_path) == 1
    names = _codes(epub_path)
    assert "feed_0/index_u1.html" not in names
    assert "feed_1/index_u2.html" in names

    opf = _xml(epub_path, "content.opf")
    hrefs = [node.getAttribute("href") for node in opf.getElementsByTagName("item")]
    assert "feed_0/index_u1.html" not in hrefs
    assert "feed_0/article_0/a.html" not in hrefs


def test_renamed_index_and_index_named_pages(tmp_path):
    """Calibre renames duplicate index.html files; find the real index anyway."""
    epub_path = str(tmp_path / "test.epub")
    sections = [
        {"href": "feed_0/index_u7.html", "title": "elpais.com", "articles": []},
        {
            "href": "feed_1/index_u2.html",
            "title": "eetimes.com",
            "articles": [
                # An article page can also end up being called index.html.
                {"href": "article_0/index.html", "title": "An article"}
            ],
        },
        {
            # A section page can keep the name index.html while the top-level
            # index is renamed to index_u6.html.
            "href": "feed_2/index.html",
            "title": "xataka.com",
            "articles": [{"href": "article_0/index_u3.html", "title": "Another"}],
        },
    ]
    _build_epub(epub_path, sections, index_name="index_u6.html")

    assert remove_empty_sections(epub_path) == 1

    names = _codes(epub_path)
    assert "feed_0/index_u7.html" not in names
    assert "feed_1/index_u2.html" in names
    assert "feed_1/article_0/index.html" in names
    assert "feed_2/index.html" in names

    index = _html(epub_path, "index_u6.html")
    assert [link["href"] for link in index.select("a.feed")] == [
        "feed_1/index_u2.html",
        "feed_2/index.html",
    ]

    toc = _xml(epub_path, "toc.ncx")
    sources = [
        node.getAttribute("src") for node in toc.getElementsByTagName("content")
    ]
    assert "feed_0/index_u7.html" not in sources
    assert "feed_1/index_u2.html" in sources
    assert "feed_2/index.html" in sources


def test_rewires_localized_navigation_across_removed_section(tmp_path):
    epub_path = str(tmp_path / "test.epub")
    sections = [
        {
            "href": "feed_0/index_u1.html",
            "title": "first.com",
            "articles": [{"href": "article_0/a.html", "title": "First"}],
        },
        {"href": "feed_1/index_u2.html", "title": "empty.com", "articles": []},
        {
            "href": "feed_2/index_u3.html",
            "title": "third.com",
            "articles": [{"href": "article_0/c.html", "title": "Third"}],
        },
    ]
    _build_epub(
        epub_path,
        sections,
        nav_labels={
            "main": "Menú principal",
            "previous": "Sección anterior",
            "next": "Siguiente sección",
        },
    )

    assert remove_empty_sections(epub_path) == 1

    first_page = _html(epub_path, "feed_0/index_u1.html")
    next_link = first_page.find(
        "a", string=lambda value: value and "Siguiente sección" in value
    )
    assert next_link is not None
    assert posixpath.normpath(
        posixpath.join(posixpath.dirname("feed_0/index_u1.html"), next_link["href"])
    ) == "feed_2/index_u3.html"

    third_page = _html(epub_path, "feed_2/index_u3.html")
    previous_link = third_page.find(
        "a", string=lambda value: value and "Sección anterior" in value
    )
    assert previous_link is not None
    assert posixpath.normpath(
        posixpath.join(
            posixpath.dirname("feed_2/index_u3.html"), previous_link["href"]
        )
    ) == "feed_0/index_u1.html"
