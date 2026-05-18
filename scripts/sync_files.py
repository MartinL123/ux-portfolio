#!/usr/bin/env python3
"""
Scans Soutenance N/ folders and regenerates the managed file sections
in each soutenance-N.html file.

Source of truth:
  - Soutenance N/          → which files exist
  - Soutenance N/files.json → custom display names and groups (optional)

If a file has no entry in files.json, its display name is auto-generated.
"""

import os
import re
import json
import sys
from pathlib import Path
from urllib.parse import quote, unquote

REPO_ROOT = Path(__file__).parent.parent

SKIP = {'.DS_Store', 'files.json', '.gitkeep', 'Thumbs.db'}

GROUP_LABELS = {
    'docs': '📄 Documents de la soutenance',
    'web':  '🌐 Livrables interactifs',
    'res':  '📦 Livrables du projet (ZIP)',
}

GROUP_ORDER = ['docs', 'web', 'res']

START_MARKER = '<!-- MANAGED-FILES-START -->'
END_MARKER   = '<!-- MANAGED-FILES-END -->'


def format_size(path):
    size = os.path.getsize(path)
    if size < 1024:
        return f'{size} B'
    if size < 1024 * 1024:
        return f'{round(size / 1024)} KB'
    return f'{size / 1024 / 1024:.1f} MB'


def auto_name(filename):
    stem = Path(filename).stem
    stem = unquote(stem.replace('+', ' '))
    stem = stem.replace('_', ' ')
    if re.match(r'^ML\s*P\d+', stem, re.I):
        m = re.search(r'P(\d+)', stem, re.I)
        num = m.group(1).zfill(2) if m else '??'
        return f'Livrable OpenClassrooms P{num}'
    return stem[0].upper() + stem[1:] if stem else filename


def auto_group(filename):
    ext = Path(filename).suffix.lstrip('.').lower()
    if ext == 'html':
        return 'web'
    if ext == 'zip':
        return 'res'
    return 'docs'


def generate_files_html(num, soutenance_dir):
    meta_path = soutenance_dir / 'files.json'
    meta = {}
    if meta_path.exists():
        with open(meta_path, encoding='utf-8') as f:
            meta = json.load(f)

    files_by_group = {g: [] for g in GROUP_ORDER}

    for fname in sorted(soutenance_dir.iterdir(), key=lambda p: p.name.lower()):
        if not fname.is_file():
            continue
        if fname.name in SKIP or fname.name.startswith('.'):
            continue

        entry = meta.get(fname.name, {})
        ext = fname.suffix.lstrip('.').lower()
        is_html = ext == 'html'

        display = entry.get('display', auto_name(fname.name) + (' ↗' if is_html else ''))
        group   = entry.get('group',   auto_group(fname.name))

        if group not in files_by_group:
            group = 'docs'

        files_by_group[group].append({
            'fname':   fname.name,
            'display': display,
            'ext':     ext,
            'size':    format_size(fname),
            'is_html': is_html,
        })

    folder_enc = quote(f'Soutenance {num}')
    lines = []

    for group in GROUP_ORDER:
        if not files_by_group[group]:
            continue
        lines.append(f'  <div class="files">')
        lines.append(f'    <div class="files-head">{GROUP_LABELS[group]}</div>')
        for f in files_by_group[group]:
            file_enc = quote(f['fname'])
            href     = f'{folder_enc}/{file_enc}'
            target   = ' target="_blank"' if f['is_html'] else ''
            lines.append(f'    <a href="{href}" class="file"{target}>')
            lines.append(f'      <span class="fext fext-{f["ext"]}">{f["ext"].upper()}</span>')
            lines.append(f'      <span class="fname">{f["display"]}</span>')
            lines.append(f'      <span class="fsize">{f["size"]}</span>')
            lines.append(f'    </a>')
        lines.append(f'  </div>')

    return '\n'.join(lines)


def sync_soutenance(num):
    html_path  = REPO_ROOT / f'soutenance-{num}.html'
    folder_dir = REPO_ROOT / f'Soutenance {num}'

    if not html_path.exists():
        print(f'  ⚠  soutenance-{num}.html introuvable — ignoré')
        return False
    if not folder_dir.is_dir():
        print(f'  ⚠  Soutenance {num}/ introuvable — ignoré')
        return False

    content = html_path.read_text(encoding='utf-8')

    if START_MARKER not in content or END_MARKER not in content:
        print(f'  ⚠  Marqueurs absents dans soutenance-{num}.html — ignoré')
        return False

    new_files_html = generate_files_html(num, folder_dir)

    pattern = re.compile(
        re.escape(START_MARKER) + r'.*?' + re.escape(END_MARKER),
        re.DOTALL
    )
    new_content = pattern.sub(
        f'{START_MARKER}\n{new_files_html}\n  {END_MARKER}',
        content
    )

    if new_content == content:
        print(f'  —  Soutenance {num} : aucun changement')
        return False

    html_path.write_text(new_content, encoding='utf-8')
    print(f'  ✓  Soutenance {num} : mis à jour')
    return True


def main():
    changed = []
    targets = []

    # Accept optional soutenance numbers as args (e.g. "10 11")
    if len(sys.argv) > 1:
        targets = [int(a) for a in sys.argv[1:] if a.isdigit()]

    if not targets:
        # Auto-detect all Soutenance N/ folders
        for d in sorted(REPO_ROOT.iterdir()):
            m = re.match(r'^Soutenance (\d+)$', d.name)
            if m and d.is_dir():
                targets.append(int(m.group(1)))

    print(f'Synchronisation de {len(targets)} soutenance(s)…')
    for num in sorted(targets):
        if sync_soutenance(num):
            changed.append(num)

    print(f'\nTerminé. {len(changed)} fichier(s) HTML modifié(s).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
