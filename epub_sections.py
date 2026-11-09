"""Remove sections that ended up empty from a Calibre-generated EPUB.

Calibre creates section index pages, NCX entries and OPF manifest/spine
entries *before* it downloads the articles. When every article in a section
fails to download, the recipe removes the failed articles, but the section
shells remain in the final EPUB (an empty topic in the table of contents).

``remove_empty_sections`` post-processes the EPUB in place: it deletes those
empty sections, updates the index, NCX and OPF, and rewires the
"Previous/Next section" navigation links to the nearest surviving section.
"""

import os
import posixpath
import shutil
import tempfile
import zipfile
from urllib.parse import unquote, urlsplit
from xml.dom import minidom

from bs4 import BeautifulSoup

FEED_LIST_CLASS = "calibre_feed_list"
FEED_LINK_CLASS = "feed"
ARTICLE_LINK_CLASS = "article"


def _clean_href(href):
    """Return the path part of *href* without query, fragment or %-encoding."""
    return unquote(urlsplit(href).path).replace("\\", "/")


def _resolve(base_rel, href):
    """Resolve *href* against the archive-relative directory *base_rel*."""
    path = _clean_href(href)
    if not path:
        return ""
    if path.startswith("/"):
        return posixpath.normpath(path.lstrip("/"))
    if base_rel:
        return posixpath.normpath(posixpath.join(base_rel, path))
    return posixpath.normpath(path)


def _abs_path(temp_dir, rel):
    """Return the filesystem path for an archive-relative path, safely."""
    if rel is None or rel == ".." or rel.startswith("../"):
        return None
    return os.path.join(temp_dir, *rel.split("/")) if rel else temp_dir


def _find_file(temp_dir, name):
    """Return the archive-relative path of the first file named *name*."""
    for root, _dirs, files in os.walk(temp_dir):
        if name in files:
            rel = os.path.relpath(os.path.join(root, name), temp_dir)
            return rel.replace(os.sep, "/")
    return None


def _read_html(path):
    with open(path, "r", encoding="utf-8") as handle:
        return BeautifulSoup(handle, "html.parser")


def _elements(root, name):
    """Find descendant elements whose local name is *name* (prefix-safe)."""
    found = []
    for node in root.getElementsByTagName("*"):
        if node.nodeType == node.ELEMENT_NODE and node.nodeName.split(":")[-1] == name:
            found.append(node)
    return found


def _direct_children(parent, name):
    found = []
    for node in parent.childNodes:
        if node.nodeType == node.ELEMENT_NODE and node.nodeName.split(":")[-1] == name:
            found.append(node)
    return found


def _write_xml(document, path):
    with open(path, "wb") as handle:
        handle.write(document.toxml(encoding="utf-8"))


def _section_is_empty(temp_dir, section_rel):
    """A section is empty if its page is missing or has no resolvable article."""
    path = _abs_path(temp_dir, section_rel)
    if path is None or not os.path.isfile(path):
        return True

    soup = _read_html(path)
    feed_list = soup.find("ul", class_=FEED_LIST_CLASS)
    if feed_list is None:
        return True

    base_rel = posixpath.dirname(section_rel)
    for link in feed_list.find_all("a", class_=ARTICLE_LINK_CLASS, href=True):
        article_rel = _resolve(base_rel, link["href"])
        article_path = _abs_path(temp_dir, article_rel)
        if article_path is not None and os.path.isfile(article_path):
            return False
    return True


def _prune_empty_dirs(temp_dir, rel_dir):
    """Remove *rel_dir* and its parents while they are empty."""
    while rel_dir and rel_dir not in (".", ""):
        path = _abs_path(temp_dir, rel_dir)
        if path is None:
            return
        try:
            os.rmdir(path)
        except OSError:
            return
        rel_dir = posixpath.dirname(rel_dir)


def _update_toc(temp_dir, empty_hrefs):
    rel = _find_file(temp_dir, "toc.ncx")
    if rel is None:
        return

    path = _abs_path(temp_dir, rel)
    document = minidom.parse(path)
    base_rel = posixpath.dirname(rel)

    for nav_point in list(_elements(document, "navPoint")):
        contents = _direct_children(nav_point, "content")
        if not contents:
            continue
        src = contents[0].getAttribute("src")
        if _resolve(base_rel, src) in empty_hrefs:
            nav_point.parentNode.removeChild(nav_point)

    for order, nav_point in enumerate(_elements(document, "navPoint"), start=1):
        nav_point.setAttribute("playOrder", str(order))

    _write_xml(document, path)


def _update_opf(temp_dir, empty_hrefs):
    rel = _find_file(temp_dir, "content.opf")
    if rel is None:
        return

    path = _abs_path(temp_dir, rel)
    document = minidom.parse(path)
    base_rel = posixpath.dirname(rel)

    manifests = _elements(document, "manifest")
    if not manifests:
        return
    manifest = manifests[0]

    removed_ids = set()
    for item in _direct_children(manifest, "item"):
        item_rel = _resolve(base_rel, item.getAttribute("href"))
        item_path = _abs_path(temp_dir, item_rel)
        if item_rel in empty_hrefs or item_path is None or not os.path.isfile(item_path):
            item_id = item.getAttribute("id")
            if item_id:
                removed_ids.add(item_id)
            manifest.removeChild(item)

    if removed_ids:
        for spine in _elements(document, "spine"):
            for itemref in _direct_children(spine, "itemref"):
                if itemref.getAttribute("idref") in removed_ids:
                    spine.removeChild(itemref)

    _write_xml(document, path)


def _rewire_navbars(temp_dir, sections):
    """Point Previous/Next section links at the nearest surviving section."""
    for index, section in enumerate(sections):
        path = _abs_path(temp_dir, section["href"])
        if path is None or not os.path.isfile(path):
            continue

        soup = _read_html(path)
        base_rel = posixpath.dirname(section["href"])
        previous = sections[index - 1] if index > 0 else None
        following = sections[index + 1] if index + 1 < len(sections) else None

        changed = False
        for link in soup.find_all("a", href=True):
            label = " ".join(link.get_text(" ", strip=True).lower().split())
            if "previous section" in label:
                target = previous
            elif "next section" in label:
                target = following
            else:
                continue

            changed = True
            if target is None:
                link.decompose()
            else:
                link["href"] = posixpath.relpath(target["href"], base_rel or ".")

        if changed:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(str(soup))


def _repack(temp_dir, epub_path):
    temp_epub = epub_path + ".tmp"
    try:
        with zipfile.ZipFile(temp_epub, "w") as archive:
            mimetype = os.path.join(temp_dir, "mimetype")
            if os.path.isfile(mimetype):
                archive.write(mimetype, "mimetype", compress_type=zipfile.ZIP_STORED)

            for root, dirs, files in os.walk(temp_dir):
                dirs.sort()
                files.sort()
                for filename in files:
                    full_path = os.path.join(root, filename)
                    arcname = os.path.relpath(full_path, temp_dir).replace(os.sep, "/")
                    if arcname == "mimetype":
                        continue
                    archive.write(full_path, arcname)

        os.replace(temp_epub, epub_path)
    except Exception:
        if os.path.exists(temp_epub):
            os.remove(temp_epub)
        raise


def remove_empty_sections(epub_path):
    """Remove empty sections from *epub_path* in place.

    Returns the number of removed sections. A section is considered empty when
    its index page is missing or its article list has no article whose target
    file exists in the EPUB.
    """
    temp_dir = tempfile.mkdtemp(prefix="epub_sections_")
    try:
        with zipfile.ZipFile(epub_path, "r") as archive:
            archive.extractall(temp_dir)

        index_rel = _find_file(temp_dir, "index.html")
        if index_rel is None:
            return 0

        index_path = _abs_path(temp_dir, index_rel)
        index_soup = _read_html(index_path)
        feed_list = index_soup.find("ul", class_=FEED_LIST_CLASS)
        if feed_list is None:
            return 0

        index_base = posixpath.dirname(index_rel)
        sections = []
        for item in feed_list.find_all("li", recursive=False):
            link = item.find("a", class_=FEED_LINK_CLASS, href=True)
            if link is None:
                continue
            sections.append(
                {"href": _resolve(index_base, link["href"]), "li": item}
            )

        empty_sections = [
            section
            for section in sections
            if _section_is_empty(temp_dir, section["href"])
        ]
        if not empty_sections:
            return 0

        empty_hrefs = {section["href"] for section in empty_sections}

        for section in empty_sections:
            section["li"].decompose()
            path = _abs_path(temp_dir, section["href"])
            if path is not None and os.path.isfile(path):
                os.remove(path)
            _prune_empty_dirs(temp_dir, posixpath.dirname(section["href"]))

        with open(index_path, "w", encoding="utf-8") as handle:
            handle.write(str(index_soup))

        _update_toc(temp_dir, empty_hrefs)
        _update_opf(temp_dir, empty_hrefs)

        surviving = [
            section for section in sections if section["href"] not in empty_hrefs
        ]
        _rewire_navbars(temp_dir, surviving)

        _repack(temp_dir, epub_path)
        return len(empty_sections)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
