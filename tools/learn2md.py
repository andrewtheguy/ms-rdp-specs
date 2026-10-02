#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["beautifulsoup4", "lxml"]
# ///
"""Build MS-XXX.md from the edition of a specification Microsoft Learn serves.

Learn publishes each specification as one HTML page per section, generated from
the same source as the PDF. This fetches every page of a spec in table-of-contents
order and writes one Markdown file, with the figures under images/MS-XXX/.

    uv run tools/learn2md.py                # every spec with a PDF in the repo
    uv run tools/learn2md.py MS-RDPEGFX     # one spec
    uv run tools/learn2md.py --refresh --pdf MS-RDPEGFX   # new revision published

Pages are cached under .cache/learn/, so a rerun only converts; --refresh
downloads them again.
"""

import argparse
import concurrent.futures
import json
import re
import shutil
import sys
import textwrap
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://learn.microsoft.com/en-us/openspecs/windows_protocols/"
GUID = r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}"

# Private-use markers for emphasis, resolved once a paragraph's text is whole.
B0, B1, I0, I1, BR = "", "", "", "", ""

# Landing-page sections worth keeping; the rest (previous revisions, preview
# notice, developer resources) is navigation around the document, not part of it.
LANDING_KEEP = ("Published Version", "Intellectual Property Rights Notice")


def fetch(url, path, refresh):
    if path.exists() and path.stat().st_size and not refresh:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(6):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (ms-rdp-specs learn2md)"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            tmp = path.with_name(path.name + ".tmp")
            tmp.write_bytes(data)
            tmp.replace(path)
            return
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise
            err = e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            err = e
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"{url}: {err}")


def fetch_all(jobs, refresh):
    with concurrent.futures.ThreadPoolExecutor(8) as pool:
        for f in [pool.submit(fetch, url, path, refresh) for url, path in jobs]:
            f.result()


class Spec:
    """A specification's table of contents: its landing page and numbered sections."""

    def __init__(self, name, cache, refresh):
        self.name = name
        self.slug = name.lower()
        self.cache = cache / self.slug
        toc = self.cache / "toc.json"
        fetch(f"{BASE}{self.slug}/toc.json", toc, refresh)
        root = self._find(json.loads(toc.read_text(encoding="utf-8"))["items"])
        if root is None:
            raise RuntimeError(f"{name}: no landing page in toc.json")
        self.landing = root["href"]
        self.title = root["toc_title"]
        self.sections = []  # (guid, number, title)
        self._walk(root.get("children", []))
        self.number = {guid: number for guid, number, _ in self.sections}

    def _find(self, items):
        for item in items:
            if re.fullmatch(GUID, item.get("href", "")) and item["toc_title"].startswith("[MS-"):
                return item
            if found := self._find(item.get("children", [])):
                return found
        return None

    def _walk(self, items):
        for item in items:
            m = re.match(r"(\d+(?:\.\d+)*)\s+(.*)", item["toc_title"])
            if not m or not re.fullmatch(GUID, item.get("href", "")):
                raise RuntimeError(f"{self.name}: unexpected TOC entry {item!r}")
            self.sections.append((item["href"], m.group(1), m.group(2)))
            self._walk(item.get("children", []))

    def page(self, guid):
        return self.cache / f"{guid}.html"

    def url(self, guid):
        return f"{BASE}{self.slug}/{guid}"


def escape(text, table=False):
    """Escape what Markdown would otherwise read as markup, and nothing else.

    Intraword underscores are left alone (CommonMark does not treat them as
    emphasis), so identifiers such as RDPGFX_HEADER stay greppable.
    """
    text = re.sub(r"[\\*`]", r"\\\g<0>", text)
    text = re.sub(r"<(?=[A-Za-z/!?])", r"\\<", text)
    text = re.sub(r"(?<![A-Za-z0-9])_|_(?![A-Za-z0-9])", r"\\_", text)
    text = re.sub(r"&(?=#?\w+;)", r"\\&", text)
    text = text.replace("~~", r"\~\~").replace("](", r"]\(")
    if table:
        text = text.replace("|", r"\|")
    return text


class Converter:
    def __init__(self, spec, specs):
        self.spec = spec
        self.specs = specs  # slug -> Spec, for links into the other local copies
        self.images = set()
        self.warnings = []

    # -- links ---------------------------------------------------------------

    def target(self, href):
        """Map a Learn href to a link target here, or None to drop the link."""
        if re.match(r"[a-z]+:", href):
            return href
        m = re.fullmatch(rf"(?:\.\./([\w-]+)/)?({GUID})?(?:#(.*))?", href)
        if not m:
            self.warnings.append(f"unrecognised href {href!r}")
            return urllib.parse.urljoin(self.spec.url(""), href)
        slug, guid, frag = m.groups()
        if frag and frag.startswith("gt_"):
            return None  # glossary term: every use of a term links to it
        spec = self.specs.get(slug.lower()) if slug else self.spec
        if spec is None:
            return f"{BASE}{slug}/{guid}" + (f"#{frag}" if frag else "")
        prefix = "" if spec is self.spec else f"{spec.name}.md"
        if frag and spec is self.spec:
            return f"#{frag}"
        if guid in spec.number:
            return f"{prefix}#Section_{spec.number[guid]}"
        if guid == spec.landing or guid is None:
            return prefix or f"{spec.name}.md"
        self.warnings.append(f"link to unknown page {href!r}")
        return spec.url(guid)

    # -- inline --------------------------------------------------------------

    def _inl(self, node, table, bold, italic):
        if isinstance(node, NavigableString):
            return escape(str(node), table)
        name = node.name
        inner = lambda b=bold, i=italic: "".join(self._inl(c, table, b, i) for c in node.children)
        if name in ("b", "strong"):
            return inner() if bold else B0 + inner(b=True) + B1
        if name in ("i", "em"):
            return inner() if italic else I0 + inner(i=True) + I1
        if name == "br":
            return BR
        if name in ("sub", "sup"):
            return f"<{name}>{inner()}</{name}>"
        if name == "img":
            src = node["src"]
            file = src.rsplit("/", 1)[-1]
            self.images.add((src, file))
            alt = escape(node.get("alt") or "").replace("[", r"\[").replace("]", r"\]")
            return f"![{alt}](images/{self.spec.name}/{file})"
        if name == "a":
            text = inner()
            if node.get("id") and not node.get("href"):
                anchor = node["id"]
                # Only the product-behaviour notes are ever linked to by anchor.
                return f'<a id="{anchor}"></a>{text}' if anchor.startswith("Appendix_A_") else text
            href = self.target(node.get("href", ""))
            if href is None or not text.strip():
                return text
            if re.search(r"[\s()<>]", href):
                href = f"<{href}>"
            return f"[{text}]({href})"
        if name in ("span", "p", "li", "u", "font"):
            return inner()
        self.warnings.append(f"unexpected inline <{name}>")
        return inner()

    def inline(self, node, table=False):
        s = self._inl(node, table, False, False)
        s = re.sub(r"[ \t\r\n\xa0]+", " ", s)
        s = re.sub(rf" ?{BR} ?", BR, s)
        for o, c in ((B0, B1), (I0, I1)):
            s = re.sub(rf"{c}( ?){o}", r"\1", s)  # adjacent runs are one run
            prev = None
            while prev != s:  # whitespace belongs outside the delimiters
                prev = s
                s = re.sub(rf"{o}([ {BR}]+)", rf"\1{o}", s)
                s = re.sub(rf"([ {BR}]+){c}", rf"{c}\1", s)
                s = s.replace(o + c, "")
        s = self._emphasis(s, B0, B1, "**", "b")
        s = self._emphasis(s, I0, I1, "*", "i")
        s = re.sub(r" {2,}", " ", s).strip(" " + BR)
        return s.replace(BR, "<br>" if table else "\\\n")

    @staticmethod
    def _emphasis(s, o, c, mark, tag):
        """Use Markdown delimiters where they will parse, an HTML tag where not."""

        def sub(m):
            before = s[m.start() - 1] if m.start() else " "
            after = s[m.end()] if m.end() < len(s) else " "
            body = m.group(1)
            punct = lambda ch: not ch.isalnum() and not ch.isspace()
            # CommonMark flanking: a delimiter run between punctuation and a
            # letter does not open/close emphasis.
            opens = not (punct(body[0]) and before.isalnum())
            closes = not (punct(body[-1]) and after.isalnum())
            if opens and closes and after not in "*_" and before not in "*_":
                return f"{mark}{body}{mark}"
            return f"<{tag}>{body}</{tag}>"

        return re.sub(rf"{o}([^{o}{c}]+){c}", sub, s)

    # -- blocks --------------------------------------------------------------

    def blocks(self, node):
        out, run = [], []

        def flush():
            if run:
                holder = BeautifulSoup("", "lxml").new_tag("span")
                for n in run:
                    holder.append(n.__copy__())
                if text := self.inline(holder):
                    out.append(self.paragraph(text))
                run.clear()

        for child in node.children:
            if isinstance(child, NavigableString):
                if child.strip():
                    run.append(child)
                continue
            name = child.name
            if name not in ("p", "ul", "ol", "dl", "dd", "dt", "div", "pre", "table", "h2", "h3", "h4"):
                run.append(child)
                continue
            flush()
            if name == "p":
                if text := self.inline(child):
                    out.append(self.paragraph(text))
            elif name in ("ul", "ol"):
                out.append(self.list(child))
            elif name == "pre":
                out.append(self.code(child))
            elif name == "table":
                out.append(self.table(child))
            elif name in ("h2", "h3", "h4"):
                out.append("#" * int(name[1]) + " " + self.inline(child))
            else:  # dl/dd/div only carry indentation
                out.extend(self.blocks(child))
        flush()
        return [b for b in out if b]

    @staticmethod
    def paragraph(text):
        # A paragraph must not start like a heading, quote, or list item.
        return re.sub(r"^(#|>|[-+](?= )|\d+(?=[.)] ))", lambda m: m.group(1)[:-1] + "\\" + m.group(1)[-1], text)

    def list(self, el):
        ordered = el.name == "ol"
        n = int(re.sub(r"\D", "", el.get("start", "")) or 1)
        items = []
        for li in el.find_all("li", recursive=False):
            marker = f"{n}. " if ordered else "- "
            n += 1
            body = "\n\n".join(self.blocks(li)) or ""
            pad = " " * len(marker)
            lines = body.split("\n")
            items.append(marker + "\n".join([lines[0]] + [pad + l if l else l for l in lines[1:]]))
        loose = any("\n\n" in i for i in items)
        return ("\n\n" if loose else "\n").join(items)

    @staticmethod
    def code(pre):
        lines = [l.rstrip() for l in pre.get_text().replace("\xa0", " ").expandtabs(8).split("\n")]
        text = textwrap.dedent("\n".join(lines)).strip("\n")
        fence = "```"
        while fence in text:
            fence += "`"
        return f"{fence}\n{text}\n{fence}"

    # -- tables --------------------------------------------------------------

    def table(self, tb, merge_extra=False):
        rows = [
            [c for c in tr.find_all(["th", "td"], recursive=False)]
            for tr in tb.find_all("tr")
            if tr.find_parent("table") is tb
        ]
        rows = [r for r in rows if r]
        if not rows:
            return ""
        if len(rows[0]) == 32 and all(c.name == "th" for c in rows[0]):
            return self.packet(rows[1:])
        if any(c.get("rowspan") for r in rows for c in r):
            self.warnings.append("table with rowspan flattened")
        grid = []
        for r in rows:
            line = []
            for c in r:
                line.append(self.cell(c))
                line.extend([""] * (int(c.get("colspan", 1)) - 1))
            grid.append(line)
        header = grid[0] if all(c.name == "th" for c in rows[0]) else None
        body = grid[1:] if header else grid
        width = len(header) if header and merge_extra else max(len(r) for r in grid)
        if merge_extra:
            body = [r[: width - 1] + [", ".join(x for x in r[width - 1 :] if x)] for r in body]
        fmt = lambda r: "| " + " | ".join(r + [""] * (width - len(r))) + " |"
        lines = [fmt(header or [""] * width), "|" + " --- |" * width]
        lines += [fmt(r) for r in body]
        return "\n".join(lines)

    def cell(self, cell):
        parts = []
        for child in cell.children:
            if isinstance(child, NavigableString):
                if child.strip():
                    parts.append(escape(" ".join(child.split()), True))
            elif child.name in ("ul", "ol"):
                for n, li in enumerate(child.find_all("li"), int(re.sub(r"\D", "", child.get("start", "")) or 1)):
                    mark = f"{n}." if child.name == "ol" else "•"
                    parts.append(f"{mark} {self.inline(li, True)}")
            elif child.name == "pre":
                parts.extend(f"`{l}`" for l in child.get_text().strip("\n").split("\n") if l.strip())
            elif child.name in ("table", "dl", "div"):
                self.warnings.append(f"<{child.name}> inside a table cell flattened")
                parts.append(self.inline(child, True))
            elif text := self.inline(child, True):
                parts.append(text)
        return "<br>".join(parts)

    def packet(self, rows):
        """Draw a bit-field diagram the way RFCs do.

        A bit is two columns wide, or up to four where a field name would not
        otherwise fit its cell; a name too long even for that wraps.
        """
        layout = []
        for r in rows:
            cells, bit = [], 0
            for c in r:
                span = int(c.get("colspan", 1))
                text = " ".join(c.get_text(" ").replace("\xa0", " ").split())
                cells.append((bit, span, text))
                bit += span
            if bit > 32:
                self.warnings.append(f"packet row {bit} bits wide")
            layout.append(cells)

        k = 2
        for cells in layout:
            for _, s, t in cells:
                longest = max(map(len, t.split()), default=0)
                while k < 4 and k * s - 1 < longest:
                    k += 1

        def border(*rowsets):
            width = max((b + s for cells in rowsets for b, s, _ in cells), default=0)
            line = ["-"] * (k * width + 1)
            for cells in rowsets:
                for b, s, _ in cells:
                    line[k * b] = line[k * (b + s)] = "+"
            return "".join(line)

        ruler = lambda digit: "".join(" " + digit(i).center(k - 1) for i in range(32)).rstrip()
        out = [ruler(lambda i: str(i // 10) if i % 10 == 0 else ""), ruler(lambda i: str(i % 10))]
        prev = []
        for cells in layout:
            out.append(border(prev, cells))
            wrapped = [textwrap.wrap(t, k * s - 1) or [""] for _, s, t in cells]
            for i in range(max(len(w) for w in wrapped)):
                line = "|"
                for (_, s, _), w in zip(cells, wrapped):
                    line += (w[i] if i < len(w) else "").center(k * s - 1) + "|"
                out.append(line)
            prev = cells
        out.append(border(prev))
        return "```\n" + "\n".join(out) + "\n```"

    def index(self, content):
        """The index: Learn marks a sub-entry only by leading no-break spaces."""
        out = []
        for p in content.find_all("p"):
            raw = p.get_text()
            text = self.inline(p)
            if not text:
                continue
            if re.fullmatch(r"[A-Z]", text):
                out.append(f"\n**{text}**\n")
            else:
                out.append(("  - " if raw.startswith("\xa0") else "- ") + text)
        return "\n".join(out).strip("\n")

    # -- pages ---------------------------------------------------------------

    def content(self, guid):
        html = self.spec.page(guid).read_text(encoding="utf-8")
        divs = BeautifulSoup(html, "lxml").select("main div.content")
        if len(divs) != 2:
            raise RuntimeError(f"{self.spec.name}/{guid}: page layout not recognised")
        return divs[1]

    def landing(self):
        """The title page: abstract, published revision, and the IP notice."""
        content = self.content(self.spec.landing)
        groups = [("", [])]
        for child in content.children:
            if isinstance(child, Tag) and child.name == "h2":
                groups.append((child.get_text(" ", strip=True), []))
            elif isinstance(child, Tag):
                groups[-1][1].append(child)
        release = downloads = None
        out = []
        for heading, nodes in groups:
            if heading and not heading.startswith(LANDING_KEEP):
                continue
            if heading:
                out.append(f"## {escape(heading)}")
            for node in nodes:
                if node.name == "table":
                    out.append(self.table(node, merge_extra=True))
                    cells = node.find_all("tr")[1].find_all("td")
                    release = [c.get_text(" ", strip=True) for c in cells[:3]]
                    downloads = {a.get_text(strip=True): a["href"] for c in cells[3:] for a in c.find_all("a")}
                else:
                    holder = BeautifulSoup("", "lxml").new_tag("div")
                    holder.append(node.__copy__())
                    out.extend(self.blocks(holder))
        if release is None:
            raise RuntimeError(f"{self.spec.name}: no Published Version table on the landing page")
        return out, release, downloads

    def document(self):
        spec = self.spec
        landing, (date, revision, _), downloads = self.landing()
        out = [
            f"# {escape(spec.title)}",
            f"> Markdown conversion of [the edition on Microsoft Learn]({spec.url(spec.landing)}), "
            f"protocol revision {revision} published {date}. Generated by `tools/learn2md.py`; "
            f"regenerate rather than edit. [{spec.name}.pdf]({spec.name}.pdf) is the copy to cite.",
            *landing,
            "## Contents",
            "\n".join(
                f"{'  ' * number.count('.')}- [{number} {escape(title)}](#Section_{number})"
                for _, number, title in spec.sections
            ),
        ]
        for guid, number, title in spec.sections:
            level = min(number.count(".") + 2, 6)
            out.append(f'<a id="Section_{number}"></a>\n{"#" * level} {number} {escape(title)}')
            if title == "Index":
                out.append(self.index(self.content(guid)))
            else:
                out.extend(self.blocks(self.content(guid)))
        return "\n\n".join(out) + "\n", date, revision, downloads


def build(spec, specs, refresh, pdf):
    fetch_all([(spec.url(g), spec.page(g)) for g in [spec.landing] + [s[0] for s in spec.sections]], refresh)
    conv = Converter(spec, specs)
    text, date, revision, downloads = conv.document()
    (ROOT / f"{spec.name}.md").write_text(text, encoding="utf-8")

    images = ROOT / "images" / spec.name
    if images.exists():
        keep = {file for _, file in conv.images}
        for old in images.iterdir():
            if old.name not in keep or refresh:
                old.unlink()
    fetch_all([(f"{BASE}{spec.slug}/{src}", images / file) for src, file in sorted(conv.images)], False)
    if images.exists() and not conv.images:
        shutil.rmtree(images)

    if pdf:
        fetch(downloads["PDF"], ROOT / f"{spec.name}.pdf", True)
    for w in sorted(set(conv.warnings)):
        print(f"  warning: {w} (x{conv.warnings.count(w)})", file=sys.stderr)
    print(f"{spec.name}: revision {revision}, {date}; {len(spec.sections)} sections, {len(conv.images)} figures")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("specs", nargs="*", metavar="MS-XXX", help="specs to build (default: every MS-*.pdf in the repo)")
    ap.add_argument("--refresh", action="store_true", help="download pages and figures again instead of using the cache")
    ap.add_argument("--pdf", action="store_true", help="also download the published PDF")
    ap.add_argument("--cache", type=Path, default=ROOT / ".cache" / "learn", help="page cache (default: .cache/learn)")
    args = ap.parse_args()

    local = sorted(p.stem for p in ROOT.glob("MS-*.pdf"))
    names = [n.upper() for n in args.specs] or local
    # Tables of contents of every local spec, so cross-spec links resolve to
    # the Markdown copies here.
    specs = {}
    for name in sorted(set(local) | set(names)):
        specs[name.lower()] = Spec(name, args.cache, args.refresh and name in names)
    for name in names:
        build(specs[name.lower()], specs, args.refresh, args.pdf)


if __name__ == "__main__":
    main()
