#!/usr/bin/env python3
"""Fabrique un .docx OOXML mono-colonne, lisible par un extracteur, depuis un CV Markdown.

Usage :
    python3 construire_cv.py <source.md> <sortie.docx> [--profil N|N11] [--langue fr-FR|en-GB]
    python3 construire_cv.py --controler-pdf <fichier.pdf>

Toutes les valeurs de mise en page viennent de `dossier/ETAT_ART_FORME_CV.md` section 4.
Le profil N applique le reglage retenu en 4.0 (10,5 pt, interligne 1,10, marges 2,00 cm).
Le profil N11 applique la cible visee une fois le fond allege (11 pt, interligne 1,15).
Aucun autre profil n'est propose : sous le profil N on sort par le bas de la fourchette
typographique, et la densite se traite en coupant du contenu dans l'ordre declare au bloc
MISE EN PAGE du socle, pas en serrant la page.

Le script ne modifie jamais la source et retire tout commentaire HTML (bloc NOTES INTERNES).
Apres la fabrication il execute les onze controles de la section 4.12 qui portent sur le
.docx et refuse d'ecrire si l'un echoue. Le douzieme porte sur le PDF exporte : il s'appelle
avec --controler-pdf, apres l'export.
"""

import re
import os
import sys
import zipfile
from datetime import datetime, timezone

# --- Profils, section 4.1 a 4.5 de ETAT_ART_FORME_CV.md ------------------------------------
# corps et tailles en demi-points, marges et espacements en twips, interligne en 240emes.
PROFILS = {
    # Retenu (4.0) : 10,5 pt / interligne 1,10 / marges 2,00 cm. 1,93 page simule.
    "N": dict(
        corps=21, marge=1134, ligne=264,
        nom=36, ap_nom=40,
        accroche=22, av_accroche=20, ap_accroche=80,
        contact=20, ap_contact=160,
        h1=26, av_h1=200, ap_h1=60,
        h2=23, av_h2=120, ap_h2=40,
        ap_para=80, ap_puce=60,
    ),
    # Cible apres allegement du fond (4.0) : 11 pt / interligne 1,15. A n'employer que si le
    # volume a baisse d'environ 10 %, sinon la piece passe a trois pages.
    "N11": dict(
        corps=22, marge=1134, ligne=276,
        nom=36, ap_nom=40,
        accroche=23, av_accroche=20, ap_accroche=80,
        contact=21, ap_contact=160,
        h1=27, av_h1=200, ap_h1=60,
        h2=24, av_h2=120, ap_h2=40,
        ap_para=80, ap_puce=60,
    ),
}

# Premiers caracteres attendus au debut du texte extrait, controle 12.6.
# Surchargeable par la variable d'environnement NOM_ATTENDU.
NOM_ATTENDU = os.environ.get("NOM_ATTENDU", "")

POLICE = "Calibri"          # 4.2, et une seule famille plus Symbol pour les puces (4.11)
NOIR = "000000"             # corps, 21,00:1
BLEU = "1F3864"             # nom et titres de section, 11,62:1
GRIS = "404040"             # accroche et coordonnees, 10,37:1
FILET = "BFBFBF"            # bordure basse des titres de section, 4.9

LANGUES = ("fr-FR", "en-GB", "en-US")


def echapper(t: str) -> str:
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# --- Analyse du Markdown ------------------------------------------------------------------

def retirer_commentaires(md: str) -> str:
    """Supprime tout bloc <!-- ... --> (dont NOTES INTERNES), meme non ferme."""
    md = re.sub(r"<!--.*?-->", "", md, flags=re.DOTALL)
    md = re.sub(r"<!--.*\Z", "", md, flags=re.DOTALL)
    return md


def blocs(md: str):
    """Rend une liste de (type, texte). Types : nom, accroche, contact, h1, h2,
    para, puce, italique."""
    lignes = retirer_commentaires(md).split("\n")
    sortie = []
    en_tete = True          # zone avant le premier ---
    tampon = []
    type_tampon = None

    def vider():
        nonlocal tampon, type_tampon
        if tampon:
            sortie.append((type_tampon, " ".join(x.strip() for x in tampon).strip()))
        tampon, type_tampon = [], None

    for brute in lignes:
        ligne = brute.rstrip()
        nu = ligne.strip()

        if not nu:
            vider()
            continue

        if re.fullmatch(r"-{3,}", nu):
            vider()
            en_tete = False
            continue

        if nu.startswith("# "):
            vider()
            sortie.append(("nom", nu[2:].strip()))
            continue

        if nu.startswith("### "):
            vider()
            sortie.append(("h2", nu[4:].strip()))
            continue

        if nu.startswith("## "):
            vider()
            sortie.append(("accroche" if en_tete else "h1", nu[3:].strip()))
            continue

        if nu.startswith("- "):
            vider()
            tampon, type_tampon = [nu[2:].strip()], "puce"
            continue

        # continuation d'une puce : ligne indentee
        if type_tampon == "puce" and brute[:1] in (" ", "\t"):
            tampon.append(nu)
            continue

        if type_tampon in ("puce",):
            vider()

        if en_tete:
            # dans l'en-tete : **Titre** seul = ligne d'accroche, sinon = coordonnees
            if re.fullmatch(r"\*\*.+\*\*", nu):
                vider()
                sortie.append(("accroche", nu[2:-2].strip()))
                continue
            vider()
            sortie.append(("contact", nu))
            continue

        if type_tampon is None:
            type_tampon = "italique" if (nu.startswith("*") and not nu.startswith("**")) else "para"
        tampon.append(nu)

    vider()
    return sortie


# --- Rendu des runs (gras / italique) ------------------------------------------------------
# Le balisage `code` du Markdown est rendu en texte ordinaire : embarquer une troisieme
# famille de caracteres pour cinq mots contredit 4.11.

JETON = re.compile(r"(\*\*.+?\*\*|`[^`]+?`|\*[^*]+?\*)")


def runs(texte: str, taille: int, couleur: str = None,
         gras_global=False, ital_global=False) -> str:
    out = []
    for morceau in JETON.split(texte):
        if not morceau:
            continue
        gras, ital = gras_global, ital_global
        contenu = morceau
        if morceau.startswith("**") and morceau.endswith("**") and len(morceau) > 4:
            gras, contenu = True, morceau[2:-2]
        elif morceau.startswith("`") and morceau.endswith("`") and len(morceau) > 2:
            contenu = morceau[1:-1]
        elif morceau.startswith("*") and morceau.endswith("*") and len(morceau) > 2:
            ital, contenu = True, morceau[1:-1]
        props = []
        if gras:
            props.append("<w:b/>")
        if ital:
            props.append("<w:i/>")
        if couleur:
            props.append(f'<w:color w:val="{couleur}"/>')
        props.append(f'<w:sz w:val="{taille}"/><w:szCs w:val="{taille}"/>')
        out.append(
            f'<w:r><w:rPr>{"".join(props)}</w:rPr>'
            f'<w:t xml:space="preserve">{echapper(contenu)}</w:t></w:r>'
        )
    return "".join(out)


def corps_document(items, p) -> str:
    """Rend le corps. Aucun paragraphe vide : l'espace vient de before et after (4.5, regle 1).
    Aucune justification : drapeau a droite (4.2)."""
    xml = []
    for typ, texte in items:
        if typ == "nom":
            xml.append(
                f'<w:p><w:pPr><w:pStyle w:val="Title"/>'
                f'<w:spacing w:before="0" w:after="{p["ap_nom"]}" '
                f'w:line="{p["ligne"]}" w:lineRule="auto"/>'
                f"</w:pPr>{runs(texte, p['nom'], BLEU, gras_global=True)}</w:p>"
            )
        elif typ == "accroche":
            xml.append(
                f'<w:p><w:pPr><w:pStyle w:val="Subtitle"/>'
                f'<w:spacing w:before="{p["av_accroche"]}" w:after="{p["ap_accroche"]}" '
                f'w:line="{p["ligne"]}" w:lineRule="auto"/>'
                f"</w:pPr>{runs(texte, p['accroche'], GRIS)}</w:p>"
            )
        elif typ == "contact":
            xml.append(
                f'<w:p><w:pPr><w:spacing w:before="0" w:after="{p["ap_contact"]}" '
                f'w:line="{p["ligne"]}" w:lineRule="auto"/>'
                f"</w:pPr>{runs(texte, p['contact'], GRIS)}</w:p>"
            )
        elif typ == "h1":
            xml.append(
                f'<w:p><w:pPr><w:pStyle w:val="Heading1"/>'
                f'<w:spacing w:before="{p["av_h1"]}" w:after="{p["ap_h1"]}" '
                f'w:line="{p["ligne"]}" w:lineRule="auto"/><w:outlineLvl w:val="0"/>'
                f"</w:pPr>{runs(texte, p['h1'], BLEU, gras_global=True)}</w:p>"
            )
        elif typ == "h2":
            xml.append(
                f'<w:p><w:pPr><w:pStyle w:val="Heading2"/>'
                f'<w:spacing w:before="{p["av_h2"]}" w:after="{p["ap_h2"]}" '
                f'w:line="{p["ligne"]}" w:lineRule="auto"/><w:outlineLvl w:val="1"/>'
                f"</w:pPr>{runs(texte, p['h2'], NOIR, gras_global=True)}</w:p>"
            )
        elif typ == "puce":
            xml.append(
                f'<w:p><w:pPr><w:pStyle w:val="ListParagraph"/>'
                f'<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>'
                f'<w:ind w:left="284" w:hanging="284"/>'
                f'<w:spacing w:before="0" w:after="{p["ap_puce"]}" '
                f'w:line="{p["ligne"]}" w:lineRule="auto"/><w:contextualSpacing/>'
                f"</w:pPr>{runs(texte, p['corps'])}</w:p>"
            )
        elif typ == "italique":
            t = texte[1:-1] if texte.startswith("*") and texte.endswith("*") else texte
            xml.append(
                f'<w:p><w:pPr><w:spacing w:before="20" w:after="{p["ap_para"]}" '
                f'w:line="{p["ligne"]}" w:lineRule="auto"/>'
                f"</w:pPr>{runs(t, p['corps'], ital_global=True)}</w:p>"
            )
        else:  # para
            xml.append(
                f'<w:p><w:pPr><w:spacing w:before="0" w:after="{p["ap_para"]}" '
                f'w:line="{p["ligne"]}" w:lineRule="auto"/>'
                f"</w:pPr>{runs(texte, p['corps'])}</w:p>"
            )
    return "".join(xml)


# --- Pieces de l'archive ------------------------------------------------------------------

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>"""

RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""

DOC_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>
</Relationships>"""

# Pas de w:autoHyphenation : la cesure reste desactivee (4.2).
SETTINGS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:zoom w:percent="100"/><w:defaultTabStop w:val="708"/>
<w:characterSpacingControl w:val="doNotCompress"/>
<w:compat><w:compatSetting w:name="compatibilityMode" w:uri="http://schemas.microsoft.com/office/word" w:val="15"/></w:compat>
</w:settings>"""

# Liste native de Word : seule facon d'obtenir un ToUnicode correct (4.7). Rond plein.
NUMBERING = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:abstractNum w:abstractNumId="0">
<w:multiLevelType w:val="hybridMultilevel"/>
<w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="&#xF0B7;"/>
<w:lvlJc w:val="left"/><w:pPr><w:ind w:left="284" w:hanging="284"/></w:pPr>
<w:rPr><w:rFonts w:ascii="Symbol" w:hAnsi="Symbol" w:hint="default"/></w:rPr></w:lvl>
</w:abstractNum>
<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>
</w:numbering>"""


def styles_xml(p, langue: str) -> str:
    """Styles Word natifs. Heading1 et Heading2 produisent un balisage H1 et H2 dans le PDF,
    utile aux lecteurs d'ecran (4.4). keepNext sur tous les titres (4.5, regle 2)."""
    c = p["corps"]
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:docDefaults><w:rPrDefault><w:rPr>
<w:rFonts w:ascii="{POLICE}" w:hAnsi="{POLICE}" w:eastAsia="{POLICE}" w:cs="{POLICE}"/>
<w:sz w:val="{c}"/><w:szCs w:val="{c}"/><w:lang w:val="{langue}"/>
</w:rPr></w:rPrDefault>
<w:pPrDefault><w:pPr><w:spacing w:after="{p['ap_para']}" w:line="{p['ligne']}" w:lineRule="auto"/>
<w:widowControl/></w:pPr></w:pPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/>
<w:rPr><w:sz w:val="{c}"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/>
<w:qFormat/><w:pPr><w:keepNext/><w:outlineLvl w:val="0"/></w:pPr>
<w:rPr><w:b/><w:color w:val="{BLEU}"/><w:sz w:val="{p['nom']}"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Subtitle"/><w:basedOn w:val="Normal"/>
<w:qFormat/><w:pPr><w:keepNext/></w:pPr>
<w:rPr><w:color w:val="{GRIS}"/><w:sz w:val="{p['accroche']}"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/>
<w:next w:val="Normal"/><w:qFormat/>
<w:pPr><w:keepNext/><w:keepLines/><w:outlineLvl w:val="0"/>
<w:pBdr><w:bottom w:val="single" w:sz="4" w:space="3" w:color="{FILET}"/></w:pBdr></w:pPr>
<w:rPr><w:b/><w:color w:val="{BLEU}"/><w:sz w:val="{p['h1']}"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/>
<w:next w:val="Normal"/><w:qFormat/>
<w:pPr><w:keepNext/><w:keepLines/><w:outlineLvl w:val="1"/></w:pPr>
<w:rPr><w:b/><w:color w:val="{NOIR}"/><w:sz w:val="{p['h2']}"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="List Paragraph"/>
<w:basedOn w:val="Normal"/><w:qFormat/><w:pPr><w:contextualSpacing/></w:pPr></w:style>
</w:styles>"""


def core_xml(titre: str, auteur: str) -> str:
    maintenant = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
 xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<dc:title>{echapper(titre)}</dc:title><dc:creator>{echapper(auteur)}</dc:creator>
<cp:lastModifiedBy>{echapper(auteur)}</cp:lastModifiedBy>
<dcterms:created xsi:type="dcterms:W3CDTF">{maintenant}</dcterms:created>
<dcterms:modified xsi:type="dcterms:W3CDTF">{maintenant}</dcterms:modified>
</cp:coreProperties>"""

APP_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
 xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
<Application>Microsoft Office Word</Application><DocSecurity>0</DocSecurity>
</Properties>"""


# --- Les onze controles de la section 4.12 qui portent sur le .docx -------------------------

def _luminance(hexa: str) -> float:
    def canal(v):
        v = v / 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, v, b = (int(hexa[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * canal(r) + 0.7152 * canal(v) + 0.0722 * canal(b)


def contraste_sur_blanc(hexa: str) -> float:
    return round((1.0 + 0.05) / (_luminance(hexa) + 0.05), 2)


def controler_docx(doc: str, styles: str, core: str, parties: list, langue: str) -> list:
    """Rend une liste (numero, intitule, verdict, detail). Verdict : OK ou ECHEC."""
    r = []
    tout = doc + styles + core

    r.append((1, "aucun tableau", "OK" if "<w:tbl>" not in doc else "ECHEC",
              f"{doc.count('<w:tbl>')} occurrence(s) de w:tbl"))

    entetes = [n for n in parties if re.match(r"word/(header|footer)\d*\.xml", n)]
    r.append((2, "aucun en-tete ni pied de page", "OK" if not entetes else "ECHEC",
              f"{len(entetes)} partie(s) header ou footer"))

    r.append((3, "une seule colonne", "OK" if '<w:cols w:space="708" w:num="1"/>' in doc else "ECHEC",
              "w:cols w:num=1 present" if 'w:num="1"' in doc else "w:cols absent ou multiple"))

    objets = sum(doc.count(b) for b in ("<w:txbxContent", "<w:drawing", "<w:pict"))
    r.append((4, "aucune zone de texte, aucun objet graphique",
              "OK" if objets == 0 else "ECHEC", f"{objets} objet(s)"))

    tailles = [int(x) for x in re.findall(r'<w:sz w:val="(\d+)"/>', doc)]
    mini = min(tailles) if tailles else 0
    r.append((5, "corps au moins 10 pt", "OK" if mini >= 20 else "ECHEC",
              f"plus petite taille {mini / 2} pt"))

    interlignes = [int(x) for x in re.findall(r'w:line="(\d+)"', doc)]
    mini_l = min(interlignes) if interlignes else 0
    r.append((6, "interligne au moins 240, 264 recommande",
              "OK" if mini_l >= 264 else ("OK" if mini_l >= 240 else "ECHEC"),
              f"interligne minimal {mini_l} ({round(mini_l / 240, 2)} en multiple Word)"))

    r.append((7, "aucun texte justifie", "OK" if 'w:jc w:val="both"' not in doc else "ECHEC",
              f"{doc.count('w:jc w:val=\"both\"')} occurrence(s)"))

    cadratins = sum(t.count("—") + t.count("–") for t in (doc, core, styles))
    r.append((8, "aucun tiret cadratin ni demi-cadratin, dc:title compris",
              "OK" if cadratins == 0 else "ECHEC", f"{cadratins} occurrence(s)"))

    r.append((9, "langue du document declaree", "OK" if f'w:lang w:val="{langue}"' in styles else "ECHEC",
              f"w:lang = {langue}"))

    couleurs = sorted(set(re.findall(r'<w:color w:val="([0-9A-Fa-f]{6})"/>', doc + styles)))
    faibles = [c for c in couleurs if contraste_sur_blanc(c) < 4.5]
    r.append((10, "contraste de chaque couleur de texte au moins 4,5:1",
              "OK" if not faibles else "ECHEC",
              " ".join(f"#{c} {contraste_sur_blanc(c)}:1" for c in couleurs)))

    vides = len([p for p in re.findall(r"<w:p>.*?</w:p>", doc, flags=re.DOTALL)
                 if not re.search(r"<w:t[^>]*>[^<]", p)])
    r.append((11, "aucun paragraphe vide", "OK" if vides == 0 else "ECHEC",
              f"{vides} paragraphe(s) sans texte"))
    return r


def _flux_pdf(brut: bytes):
    """Rend les flux FlateDecode decompresses. Sert au controle du texte extrait."""
    import zlib
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", brut, flags=re.DOTALL):
        try:
            yield zlib.decompress(m.group(1))
        except zlib.error:
            continue


def _desechapper(s: bytes) -> bytes:
    """Rend une chaine litterale PDF : antislash suivi d'un caractere, ou de trois chiffres octaux."""
    sortie = bytearray()
    i = 0
    while i < len(s):
        if s[i:i + 1] != b"\\":
            sortie += s[i:i + 1]
            i += 1
            continue
        suite = s[i + 1:i + 4]
        octal = re.match(rb"[0-7]{1,3}", suite)
        if octal:
            sortie.append(int(octal.group(0), 8) & 0xFF)
            i += 1 + len(octal.group(0))
        else:
            sortie += s[i + 1:i + 2]
            i += 2
    return bytes(sortie)


def texte_pdf(brut: bytes) -> bytes:
    """Concatene les chaines montrees par les operateurs Tj et TJ des flux de contenu de page,
    dans l'ordre du flux. Les octets rendus sont ceux de l'encodage de la police, WinAnsi pour
    un export Word. Les flux d'objets et l'arbre de structure sont ecartes : ils portent des
    chaines qui ne sont pas du texte de page."""
    sortie = []
    for flux in _flux_pdf(brut):
        if b"BT" not in flux or b"Tf" not in flux:
            continue
        for m in re.finditer(rb"(\[(?:[^\[\]\\]|\\.)*\]\s*TJ)|((?:\((?:[^()\\]|\\.)*\))\s*Tj)", flux):
            for chaine in re.finditer(rb"\((?:[^()\\]|\\.)*\)", m.group(0)):
                sortie.append(_desechapper(chaine.group(0)[1:-1]))
    return b"".join(sortie)


def metadonnees_pdf(brut: bytes) -> str:
    """Rend le paquet XMP et les chaines du dictionnaire Info, decodes, en un seul texte."""
    morceaux = []
    xmp = re.search(rb"<\?xpacket begin.*?<\?xpacket end.*?\?>", brut, flags=re.DOTALL)
    if xmp:
        morceaux.append(xmp.group(0).decode("utf-8", "replace"))
    for m in re.finditer(rb"/(?:Title|Author|Subject|Keywords|Creator|Producer)\s*\((?:[^()\\]|\\.)*\)", brut):
        interieur = m.group(0)[m.group(0).index(b"(") + 1:-1]
        if interieur.startswith(b"\xfe\xff"):
            morceaux.append(interieur[2:].decode("utf-16-be", "replace"))
        else:
            morceaux.append(interieur.decode("latin-1"))
    return "\n".join(morceaux)


def controler_pdf(chemin: str) -> list:
    """Douzieme controle de la section 4.12, sur le PDF exporte.

    Le tiret cadratin ne se cherche pas dans le binaire entier : la paire d'octets qui le
    code en UTF-16 apparait au hasard dans les flux compresses et produit un faux positif.
    Il se cherche dans les metadonnees decodees et dans le texte extrait, separement.
    """
    brut = open(chemin, "rb").read()
    r = []
    images = brut.count(b"/Subtype /Image") + brut.count(b"/Subtype/Image")
    r.append((12.1, "aucune image dans le PDF", "OK" if images == 0 else "ECHEC",
              f"{images} objet(s) image"))
    r.append((12.2, "arbre de structure present",
              "OK" if b"/StructTreeRoot" in brut else "ECHEC",
              "StructTreeRoot present" if b"/StructTreeRoot" in brut else "absent"))
    pages = len(re.findall(rb"/Type\s*/Page[^s]", brut))
    r.append((12.3, "deux pages", "OK" if pages == 2 else "ECHEC", f"{pages} page(s)"))

    meta = metadonnees_pdf(brut)
    n_meta = meta.count("\u2014") + meta.count("\u2013")
    r.append((12.4, "aucun tiret cadratin dans les metadonnees decodees",
              "OK" if n_meta == 0 else "ECHEC",
              f"{n_meta} occurrence(s) sur {len(meta)} caracteres de metadonnees"))

    txt = texte_pdf(brut)
    # WinAnsi : 0x97 tiret cadratin, 0x96 tiret demi-cadratin.
    n_txt = txt.count(b"\x97") + txt.count(b"\x96")
    r.append((12.5, "aucun tiret cadratin dans le texte extrait",
              "OK" if n_txt == 0 else "ECHEC",
              f"{n_txt} occurrence(s) sur {len(txt)} octets de texte"))

    debut = txt[:70].decode("latin-1", "replace")
    r.append((12.6, "le texte extrait commence par le nom, donc se lit dans l'ordre logique",
              "OK" if txt[:15].decode("latin-1", "replace").startswith(NOM_ATTENDU) else "ECHEC",
              repr(debut)))

    r.append((12.7, "taille inferieure a 1 Mo",
              "OK" if len(brut) < 1_000_000 else "ECHEC", f"{len(brut) // 1024} ko"))
    return r


def afficher(resultats: list) -> bool:
    tout_ok = True
    for num, intitule, verdict, detail in resultats:
        if verdict != "OK":
            tout_ok = False
        print(f"  {verdict:6s} {num:>4} {intitule} : {detail}")
    return tout_ok


# --- Fabrication --------------------------------------------------------------------------

def construire(source: str, sortie: str, profil: str = "N", langue: str = "fr-FR") -> dict:
    p = PROFILS[profil]
    md = open(source, encoding="utf-8").read()
    items = blocs(md)
    nom = next((t for k, t in items if k == "nom"), "CV")
    titre = next((t for k, t in items if k == "accroche"), "CV")

    doc = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:body>{corps_document(items, p)}
<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>
<w:pgMar w:top="{p['marge']}" w:right="{p['marge']}" w:bottom="{p['marge']}" w:left="{p['marge']}"
 w:header="0" w:footer="0" w:gutter="0"/>
<w:cols w:space="708" w:num="1"/><w:docGrid w:linePitch="360"/></w:sectPr>
</w:body></w:document>"""

    styles = styles_xml(p, langue)
    core = core_xml(f"{nom}, {titre}", nom)
    parties = ["word/document.xml", "word/styles.xml", "word/numbering.xml",
               "word/settings.xml", "docProps/core.xml", "docProps/app.xml"]

    print(f"Controles section 4.12 sur {sortie} :")
    resultats = controler_docx(doc, styles, core, parties, langue)
    if not afficher(resultats):
        raise SystemExit("Un controle a echoue : le fichier n'est pas ecrit.")

    with zipfile.ZipFile(sortie, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", RELS)
        z.writestr("docProps/core.xml", core)
        z.writestr("docProps/app.xml", APP_XML)
        z.writestr("word/document.xml", doc)
        z.writestr("word/_rels/document.xml.rels", DOC_RELS)
        z.writestr("word/styles.xml", styles)
        z.writestr("word/numbering.xml", NUMBERING)
        z.writestr("word/settings.xml", SETTINGS)

    mots = len(re.findall(r"\S+", re.sub(r"<[^>]+>", " ", doc)))
    return dict(blocs=len(items), profil=profil, langue=langue, nom=nom,
                titre=titre, mots_visibles=mots)


if __name__ == "__main__":
    argv = sys.argv[1:]
    if argv and argv[0] == "--controler-pdf":
        if len(argv) < 2:
            sys.exit("usage: construire_cv.py --controler-pdf <fichier.pdf>")
        print(f"Controle 12 sur {argv[1]} :")
        sys.exit(0 if afficher(controler_pdf(argv[1])) else 1)

    prof, langue = "N", "fr-FR"
    args = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("--profil"):
            prof = a.split("=")[-1] if "=" in a else argv[i + 1]
            i += 1 if "=" in a else 2
        elif a.startswith("--langue"):
            langue = a.split("=")[-1] if "=" in a else argv[i + 1]
            i += 1 if "=" in a else 2
        else:
            args.append(a)
            i += 1
    if len(args) < 2:
        sys.exit("usage: construire_cv.py <source.md> <sortie.docx> [--profil N|N11] [--langue fr-FR|en-GB]")
    if prof not in PROFILS:
        sys.exit(f"profil inconnu: {prof} (attendus: {', '.join(PROFILS)})")
    if langue not in LANGUES:
        sys.exit(f"langue inconnue: {langue} (attendues: {', '.join(LANGUES)})")
    print(construire(args[0], args[1], prof, langue))
