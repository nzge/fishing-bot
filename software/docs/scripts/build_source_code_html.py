#!/usr/bin/env python3
"""Assemble all ROS 2 workspace source files into one printable HTML page."""

from __future__ import annotations

import argparse
import html
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import TextLexer, get_lexer_by_name
from pygments.util import ClassNotFound

TEXT_EXTENSIONS = {
    '.py',
    '.yaml',
    '.yml',
    '.xml',
    '.xacro',
    '.urdf',
    '.msg',
    '.cfg',
    '.launch',
    '.sh',
    '.md',
}
SKIP_DIR_NAMES = {'__pycache__', '.pytest_cache', 'node_modules', '.git'}
BINARY_EXTENSIONS = {'.stl', '.dae', '.obj', '.png', '.jpg', '.jpeg', '.gif', '.pdf', '.npz'}

LEXER_BY_SUFFIX = {
    '.py': 'python',
    '.yaml': 'yaml',
    '.yml': 'yaml',
    '.xml': 'xml',
    '.xacro': 'xml',
    '.urdf': 'xml',
    '.msg': 'yaml',
    '.cfg': 'ini',
    '.sh': 'bash',
    '.md': 'markdown',
}


def git_info(repo_root: Path) -> str:
    try:
        commit = subprocess.check_output(
            ['git', '-C', str(repo_root), 'rev-parse', '--short', 'HEAD'],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        dirty = subprocess.call(
            ['git', '-C', str(repo_root), 'diff', '--quiet', '--', 'software/'],
            stderr=subprocess.DEVNULL,
        )
        suffix = ' (dirty)' if dirty else ''
        return f'{commit}{suffix}'
    except (subprocess.CalledProcessError, FileNotFoundError):
        return 'unknown'


def collect_files(roots: list[Path]) -> list[tuple[Path, Path]]:
    """Return (absolute_path, path_relative_to_repo) pairs, sorted."""
    files: list[tuple[Path, Path]] = []
    for root in roots:
        root = root.resolve()
        if not root.is_dir():
            continue
        repo_root = root
        while repo_root.name != 'software' and repo_root.parent != repo_root:
            repo_root = repo_root.parent
        for path in sorted(root.rglob('*')):
            if not path.is_file():
                continue
            if any(part in SKIP_DIR_NAMES for part in path.parts):
                continue
            if path.suffix.lower() in BINARY_EXTENSIONS:
                continue
            if path.suffix not in TEXT_EXTENSIONS and path.name not in {'package.xml', 'CMakeLists.txt'}:
                continue
            try:
                rel = path.relative_to(repo_root.parent if repo_root.name == 'software' else root.parent.parent)
            except ValueError:
                rel = path.relative_to(root.parent)
            files.append((path, rel))
    return sorted(files, key=lambda item: str(item[1]).lower())


def lexer_for(path: Path) -> object:
    if path.name == 'CMakeLists.txt':
        try:
            return get_lexer_by_name('cmake')
        except ClassNotFound:
            return TextLexer()
    lexer_name = LEXER_BY_SUFFIX.get(path.suffix)
    if lexer_name:
        try:
            return get_lexer_by_name(lexer_name)
        except ClassNotFound:
            pass
    return TextLexer()


def highlight_file(path: Path, formatter: HtmlFormatter) -> str:
    source = path.read_text(encoding='utf-8', errors='replace')
    return highlight(source, lexer_for(path), formatter)


def package_name(rel: Path) -> str:
    parts = rel.parts
    if len(parts) >= 3 and parts[0] == 'software' and parts[1] == 'src':
        return parts[2]
    if len(parts) >= 2 and parts[0] == 'software' and parts[1] == 'sim':
        return 'sim'
    if parts and parts[0] == 'src' and len(parts) >= 2:
        return parts[1]
    return parts[0] if parts else 'root'


def render_html(
    files: list[tuple[Path, Path]],
    repo_root: Path,
    title: str,
) -> str:
    formatter = HtmlFormatter(
        linenos=True,
        cssclass='source-code',
        wrapcode=True,
    )
    pygments_css = formatter.get_style_defs('.highlight')

    generated = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    commit = git_info(repo_root)

    toc_lines = []
    body_lines = []
    current_pkg: str | None = None

    for abs_path, rel in files:
        rel_posix = rel.as_posix()
        line_count = abs_path.read_text(encoding='utf-8', errors='replace').count('\n') + 1
        pkg = package_name(rel)

        toc_lines.append(
            f'<li><a href="#{html.escape(rel_posix, quote=True)}">'
            f'{html.escape(rel_posix)}</a> <span class="meta">({line_count} lines)</span></li>'
        )

        if pkg != current_pkg:
            current_pkg = pkg
            body_lines.append(f'<h1 class="package-heading" id="pkg-{html.escape(pkg, quote=True)}">'
                            f'Package: {html.escape(pkg)}</h1>')

        body_lines.append(
            f'<section class="source-file" id="{html.escape(rel_posix, quote=True)}">'
            f'<h2 class="file-heading">{html.escape(rel_posix)}'
            f' <span class="meta">({line_count} lines)</span></h2>'
            f'{highlight_file(abs_path, formatter)}'
            f'</section>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <style>
    {pygments_css}
    :root {{
      --text: #1a1a1a;
      --muted: #666;
      --border: #ddd;
      --code-bg: #f6f8fa;
    }}
    body {{
      font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
      color: var(--text);
      line-height: 1.45;
      max-width: 7.5in;
      margin: 0 auto;
      padding: 0.5in 0.65in 1in;
    }}
    h1.title {{
      font-size: 1.6rem;
      margin: 0 0 0.25rem;
    }}
    .subtitle {{
      color: var(--muted);
      font-size: 0.85rem;
      margin: 0 0 1.25rem;
    }}
    h1.package-heading {{
      font-size: 1.25rem;
      margin: 2rem 0 0.75rem;
      padding-top: 0.5rem;
      border-top: 2px solid var(--border);
      break-before: page;
      page-break-before: always;
    }}
    h1.package-heading:first-of-type {{
      break-before: auto;
      page-break-before: auto;
      border-top: none;
      padding-top: 0;
    }}
    h2.file-heading {{
      font-size: 0.95rem;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-weight: 600;
      margin: 1.25rem 0 0.35rem;
      break-after: avoid;
      page-break-after: avoid;
    }}
    .meta {{
      color: var(--muted);
      font-weight: 400;
      font-family: inherit;
      font-size: 0.85em;
    }}
    .toc {{
      margin: 1rem 0 1.5rem;
      padding: 0.75rem 1rem;
      border: 1px solid var(--border);
      border-radius: 0.35rem;
      background: #fafafa;
      break-after: page;
      page-break-after: always;
    }}
    .toc h2 {{
      margin: 0 0 0.5rem;
      font-size: 1rem;
    }}
    .toc ul {{
      margin: 0;
      padding-left: 1.2rem;
      columns: 2;
      column-gap: 1.5rem;
      font-size: 0.72rem;
    }}
    .toc li {{
      margin: 0.15rem 0;
      break-inside: avoid;
    }}
    .toc a {{
      color: #0b6e99;
      text-decoration: none;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    }}
    section.source-file {{
      margin-bottom: 1.5rem;
      break-inside: auto;
    }}
    .highlight {{
      background: var(--code-bg);
      border: 1px solid var(--border);
      border-radius: 0.25rem;
      padding: 0.35rem 0;
      overflow-x: auto;
      font-size: 0.62rem;
      line-height: 1.35;
    }}
    .highlight pre {{
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
    }}
    .linenos {{
      color: var(--muted);
      border-right: 1px solid var(--border);
      padding-right: 0.5rem;
      user-select: none;
    }}
    @media print {{
      body {{ max-width: none; padding: 0; }}
      .toc {{ break-after: page; }}
      section.source-file {{ break-inside: auto; }}
      .highlight {{ font-size: 0.58rem; }}
    }}
  </style>
</head>
<body>
  <h1 class="title">{html.escape(title)}</h1>
  <p class="subtitle">
    Generated {html.escape(generated)} · git {html.escape(commit)} ·
    {len(files)} file{'s' if len(files) != 1 else ''}
  </p>
  <nav class="toc">
    <h2>Table of contents</h2>
    <ul>
      {''.join(toc_lines)}
    </ul>
  </nav>
  {''.join(body_lines)}
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--src-root',
        type=Path,
        action='append',
        default=[],
        help='Source root to include (repeatable). Default: software/src',
    )
    parser.add_argument(
        '--include-sim',
        action='store_true',
        help='Also include software/sim/ (MuJoCo MJCF)',
    )
    parser.add_argument(
        '--output',
        type=Path,
        required=True,
        help='Output HTML path',
    )
    parser.add_argument(
        '--title',
        default='Fishing Robot — ROS 2 Source Code',
        help='Document title',
    )
    args = parser.parse_args()

    docs_dir = Path(__file__).resolve().parent.parent
    repo_root = docs_dir.parent.parent
    roots = args.src_root or [repo_root / 'software' / 'src']
    if args.include_sim:
        roots.append(repo_root / 'software' / 'sim')

    files = collect_files(roots)
    if not files:
        print('[build_source_code_html] No source files found.', file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_html(files, repo_root, args.title), encoding='utf-8')
    print(f'[build_source_code_html] {len(files)} files → {args.output}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
