#!/usr/bin/env python3
"""Turn a captured terminal transcript into an animated GIF, line by line.

The transcript is real output (see tools/demo_harness.py); this script only draws it. Each
frame is an HTML page screenshotted by headless Chromium, then ffmpeg assembles the frames.

    python3 tools/demo_harness.py > /tmp/harness.txt
    python3 tools/render_terminal_gif.py /tmp/harness.txt assets/demos/harness.gif ["window title"]

Needs Chromium (any recent build) and ffmpeg on the PATH or CHROME set in the environment.
"""
from __future__ import annotations

import html
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

LARGEUR, HAUTEUR, VISIBLES = 1000, 600, 23


def chrome() -> str:
    if os.environ.get("CHROME"):
        return os.environ["CHROME"]
    candidats = sorted(Path.home().glob(".cache/ms-playwright/chromium-*/chrome-linux64/chrome"))
    if candidats:
        return str(candidats[-1])
    for nom in ("chromium", "chromium-browser", "google-chrome"):
        if shutil.which(nom):
            return nom
    sys.exit("Chromium introuvable : definir CHROME")


def colorer(ligne: str) -> str:
    """Couleur par nature de ligne : commentaire, commande, refus, succes."""
    t = html.escape(ligne) or "&nbsp;"
    if ligne.startswith("# "):
        return f'<span class="c">{t}</span>'
    if ligne.startswith("$ "):
        return f'<span class="p">$</span> <span class="cmd">{t[2:]}</span>'
    if any(m in ligne for m in ("REFUSE", "Error", "flagged", "exit 1", "no longer", "broken")):
        return f'<span class="ko">{t}</span>'
    if any(m in ligne for m in ("OK", "intact", "exit 0", "created: no")):
        return f'<span class="ok">{t}</span>'
    return t


def page(lignes: list[str], curseur: bool, titre: str = "harness demo, real output") -> str:
    corps = "\n".join(colorer(l) for l in lignes[-VISIBLES:])
    fin = '<span class="cur">&#9608;</span>' if curseur else ""
    return f"""<!doctype html><meta charset="utf-8"><style>
body{{margin:0;background:#1c1d22;width:{LARGEUR}px;height:{HAUTEUR}px;overflow:hidden}}
.bar{{height:30px;background:#26272e;display:flex;align-items:center;gap:8px;padding:0 14px}}
.bar i{{width:12px;height:12px;border-radius:50%;display:inline-block}}
.bar b{{color:#9ca3af;font:500 13px sans-serif;margin-left:12px}}
pre{{margin:0;padding:14px 18px;color:#e5e7eb;font:14px/20px "DejaVu Sans Mono",monospace;white-space:pre-wrap}}
.c{{color:#a5b4fc}} .p{{color:#c7d2fe}} .cmd{{color:#ffffff}} .ok{{color:#86efac}} .ko{{color:#fca5a5}}
.cur{{color:#c7d2fe}}
</style><div class="bar"><i style="background:#ef4444"></i><i style="background:#eab308"></i><i style="background:#22c55e"></i><b>{html.escape(titre)}</b></div>
<pre>{corps}{fin}</pre>"""


def main(source: str, cible: str, titre: str = "harness demo, real output") -> int:
    lignes = Path(source).read_text(encoding="utf-8").rstrip("\n").split("\n")
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        liste = []
        for i in range(1, len(lignes) + 1):
            html_page = d / f"f{i:03d}.html"
            png = d / f"f{i:03d}.png"
            html_page.write_text(page(lignes[:i], True, titre), encoding="utf-8")
            subprocess.run([chrome(), "--headless", "--disable-gpu", "--hide-scrollbars",
                            f"--window-size={LARGEUR},{HAUTEUR}", f"--screenshot={png}",
                            html_page.as_uri()], capture_output=True, timeout=60)
            # Pause plus longue apres un resultat ou une ligne vide, pour laisser lire.
            courante = lignes[i - 1]
            duree = 1.4 if (courante == "" or courante.startswith("(exit")) else 0.35
            if courante.startswith("# "):
                duree = 0.9
            liste.append(f"file '{png}'\nduration {duree}")
        liste.append(f"file '{d / f'f{len(lignes):03d}.png'}'\nduration 4")
        (d / "liste.txt").write_text("\n".join(liste) + "\n", encoding="utf-8")
        palette = d / "palette.png"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                        "-i", str(d / "liste.txt"), "-vf", "fps=10,scale=860:-1:flags=lanczos,palettegen",
                        str(palette)], check=True)
        Path(cible).parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                        "-i", str(d / "liste.txt"), "-i", str(palette), "-lavfi",
                        "fps=10,scale=860:-1:flags=lanczos[x];[x][1:v]paletteuse", str(cible)],
                       check=True)
    print(f"{cible} : {len(lignes)} lignes, {Path(cible).stat().st_size // 1024} Ko")
    return 0


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        sys.exit(__doc__)
    sys.exit(main(*sys.argv[1:]))
