#!/usr/bin/env python3
"""
One-time setup: reads current .files sections from each soutenance HTML,
saves custom display names to files.json, then replaces .files sections
with MANAGED markers (ready for sync_files.py).
"""

import re
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote

REPO_ROOT = Path(__file__).parent.parent

START = '<!-- MANAGED-FILES-START -->'
END   = '<!-- MANAGED-FILES-END -->'

# Detect group from files-head text
def detect_group(head_text):
    if '📦' in head_text:
        return 'res'
    if '🌐' in head_text:
        return 'web'
    return 'docs'

# Extract filename from href (last path segment, URL-decoded)
def href_to_filename(href):
    part = href.split('/')[-1]
    return unquote(part)  # %XX decoded, + stays literal


class FilesParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_files_div  = 0
        self.in_files_head = False
        self.in_fname      = False
        self.current_head  = ''
        self.current_group = 'docs'
        self.current_href  = ''
        self.in_file_link  = False
        self.entries       = {}   # {filename: {display, group}}
        self.depth         = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'div':
            cls = attrs.get('class', '')
            if cls == 'files':
                self.in_files_div += 1
            elif cls == 'files-head' and self.in_files_div:
                self.in_files_head = True
        elif tag == 'a' and self.in_files_div and attrs.get('class') == 'file':
            self.current_href = attrs.get('href', '')
            self.in_file_link = True
        elif tag == 'span' and self.in_file_link and attrs.get('class') == 'fname':
            self.in_fname = True

    def handle_endtag(self, tag):
        if tag == 'div':
            if self.in_files_head:
                self.in_files_head = False
                self.current_group = detect_group(self.current_head)
                self.current_head  = ''
            elif self.in_files_div:
                self.in_files_div -= 1
        elif tag == 'a' and self.in_file_link:
            self.in_file_link = False
            self.current_href = ''
        elif tag == 'span' and self.in_fname:
            self.in_fname = False

    def handle_data(self, data):
        if self.in_files_head:
            self.current_head += data
        elif self.in_fname and self.current_href:
            fname   = href_to_filename(self.current_href)
            display = data.strip()
            if fname:
                self.entries[fname] = {
                    'display': display,
                    'group':   self.current_group,
                }


# Regex to match one or more consecutive .files div blocks (2-space indent)
FILES_BLOCK_RE = re.compile(
    r'(\s*<div class="files">.*?</div>)+',
    re.DOTALL
)

def add_markers(content, files_html):
    """Replace existing .files section(s) with managed markers."""
    replacement = f'\n  {START}\n{files_html}\n  {END}\n'
    new = FILES_BLOCK_RE.sub(replacement, content, count=1)
    if new == content:
        print('    ⚠  Aucun bloc .files trouvé, marqueurs non insérés')
    return new


def setup_soutenance(num):
    html_path   = REPO_ROOT / f'soutenance-{num}.html'
    folder_path = REPO_ROOT / f'Soutenance {num}'
    meta_path   = folder_path / 'files.json'

    if not html_path.exists() or not folder_path.is_dir():
        return

    content = html_path.read_text(encoding='utf-8')

    # Skip if markers already present
    if START in content:
        print(f'  —  Soutenance {num} : marqueurs déjà présents')
        return

    # Parse file entries from HTML
    parser = FilesParser()
    parser.feed(content)
    entries = parser.entries

    if entries:
        # Save files.json (merge with existing if any)
        existing = {}
        if meta_path.exists():
            with open(meta_path, encoding='utf-8') as f:
                existing = json.load(f)
        existing.update(entries)
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        print(f'  ✓  Soutenance {num} : files.json créé ({len(entries)} entrée(s))')
    else:
        print(f'  ⚠  Soutenance {num} : aucune entrée trouvée dans le HTML')

    # Now generate fresh HTML from the folder (using the just-saved meta)
    # Import sync logic
    import importlib.util
    spec = importlib.util.spec_from_file_location('sync', REPO_ROOT / 'scripts' / 'sync_files.py')
    sync = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sync)

    files_html = sync.generate_files_html(num, folder_path)

    # Add markers to HTML
    new_content = add_markers(content, files_html)
    html_path.write_text(new_content, encoding='utf-8')
    print(f'  ✓  Soutenance {num} : marqueurs insérés dans le HTML')


def main():
    import re as _re
    soutenances = []
    for d in sorted(REPO_ROOT.iterdir()):
        m = _re.match(r'^Soutenance (\d+)$', d.name)
        if m and d.is_dir():
            soutenances.append(int(m.group(1)))

    print(f'Setup de {len(soutenances)} soutenance(s)…')
    for num in sorted(soutenances):
        setup_soutenance(num)
    print('\nSetup terminé.')


if __name__ == '__main__':
    main()
