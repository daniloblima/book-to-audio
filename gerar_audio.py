#!/usr/bin/env python3
"""book-to-audio 0.2.0 — PDF para MP3 com capítulos, figuras e tabelas.

Fluxo: PDF -> Docling (texto estruturado em JSON) -> roteiro (o que se fala, por
capítulo) -> voz do Kokoro (ou do `say` do macOS) -> MP3 com capítulos ID3v2.

Figuras e tabelas não são lidas. O áudio anuncia cada uma ("Figure 3, in the
figures folder"), lê a legenda e segue; a imagem, recortada do PDF, vai para a
pasta figuras/ ao lado do MP3 e também para dentro do capítulo do MP3, onde o
tocador de podcast pode mostrá-la no momento do anúncio.

Uso:
    uv run gerar_audio.py documento.pdf --lingua en
    uv run gerar_audio.py documento.pdf --lingua pt --titulo "..." --autor "..."

Também aceita o .json ou o .md já extraídos pelo Docling no lugar do PDF (sem
recorte de figuras, que precisa do PDF).
"""
import argparse
import html
import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Seções em que a leitura para. Tudo que vem depois fica fora do áudio.
FIM_DE_LEITURA = re.compile(
    r"^(references|referências|referencias|bibliography|bibliografia|notes|notas|"
    r"disclosure statement|disclosure|funding|orcid|acknowledg(e)?ments?|agradecimentos|"
    r"declaration of interest|conflict of interest)\b",
    re.IGNORECASE,
)
# Seção de primeiro nível ("1 Introdução", "2. Literature review") abre capítulo.
SECAO_PRINCIPAL = re.compile(r"^\d+\.?\s+\S")
# Subseção numerada ("7.1. Distribution") é lida como subtítulo.
SUBSECAO = re.compile(r"^\d+(\.\d+)+\.?\s*")
RESUMO = re.compile(r"^(abstract|resumo|summary)$", re.IGNORECASE)
# Afiliação do autor solta no corpo: linha curta, sem ponto final, com nome de instituição.
AFILIACAO = re.compile(r"^(?=.{0,120}$)(?!.*\.$).*\b(University|Universidade|Universidad|Université|Institute|Instituto|Department|Departamento|School of|Faculdade)\b", re.IGNORECASE)
# Linhas de capa, contato e metadados editoriais que não se leem.
RUIDO = re.compile(
    r"^(CONTACT\b|Correspondence|E-?mail\b|©|To cite this article|To link to this article|"
    r"Published online|Article views|View Crossmark|Supplemental data|∂ OPEN ACCESS|"
    r"JEL\b|HISTORY\b|Received\b|ISSN\b|This is an Open Access article)", re.IGNORECASE)
# Citação autor-ano entre parênteses: "(Martin & Sunley, 2022; Zhu et al., 2019)".
CITACAO_PARENTESES = re.compile(r"\s*\([^()]*\b(1[89]|20)\d{2}[a-z]?\b[^()]*\)")
# Ano solto depois do nome: "Schumpeter (1934)" vira "Schumpeter".
ANO_ENTRE_PARENTESES = re.compile(r"\s*\((1[89]|20)\d{2}[a-z]?(,\s*p+\.\s*[\d–-]+)?\)")
# Legenda: "Figure 1. ...", "Tabela 2: ...".
LEGENDA = re.compile(r"^(Figure|Fig\.?|Figura|Gráfico|Table|Tabela|Quadro)\s*(\d+)\s*[.:]?\s*(.*)$",
                     re.IGNORECASE | re.DOTALL)
# Menção no texto: "Figure 3", "Figures 4 and 5", "Tables 1–2", "Figura 2".
MENCAO = re.compile(r"\b(Figures?|Figs?\.|Figuras?|Gráficos?|Tables?|Tabelas?|Quadros?)\s+"
                    r"(\d+(?:\s*(?:,|and|e|&|–|-|to|a)\s*\d+)*)", re.IGNORECASE)

PAUSA_SUBTITULO = "[[slnc 700]]"
PAUSA_CAPITULO = "[[slnc 1200]]"
PAUSA_FIGURA = "[[slnc 500]]"

ROTULOS = {
    "en": {"figura": "Figure", "tabela": "Table", "anuncio": "in the figures folder"},
    "pt": {"figura": "Figura", "tabela": "Tabela", "anuncio": "na pasta de figuras"},
}


def log(msg):
    print(f"[gerar_audio] {msg}", flush=True)


def limpar(texto):
    texto = html.unescape(texto)
    texto = CITACAO_PARENTESES.sub("", texto)
    texto = ANO_ENTRE_PARENTESES.sub("", texto)
    texto = re.sub(r"\s+([,.;:])", r"\1", texto)
    texto = re.sub(r"\s{2,}", " ", texto)
    return texto.strip()


def tipo_do_rotulo(palavra):
    p = palavra.lower()
    return "tabela" if p.startswith(("tab", "quadro")) else "figura"


def numeros_citados(trecho):
    """'4 and 5' -> [4, 5]; '1–3' -> [1, 2, 3]."""
    nums, partes = [], re.split(r"(\d+)", trecho)
    for i in range(1, len(partes), 2):
        n = int(partes[i])
        sep = partes[i - 1] if i > 1 else ""
        if nums and re.search(r"[–-]|\bto\b|\ba\b", sep) and n > nums[-1]:
            nums += list(range(nums[-1] + 1, n + 1))
        else:
            nums.append(n)
    return nums


# ---------------------------------------------------------------- blocos
# O roteiro trabalha sobre uma lista de blocos: {"tipo": titulo|texto|legenda|nota|formula,
# "texto": ..., e para legenda: "chave": ("figura", 3), "pagina", "caixa"}.

def blocos_do_json(caminho):
    d = json.loads(Path(caminho).read_text(encoding="utf-8"))
    indice = {}
    for k in ("texts", "pictures", "tables", "groups"):
        for item in d.get(k, []):
            indice[item["self_ref"]] = item

    def caixa(item):
        prov = item.get("prov") or []
        if not prov:
            return None, None
        b = prov[0]["bbox"]
        return prov[0]["page_no"], (b["l"], b["t"], b["r"], b["b"], b.get("coord_origin", "BOTTOMLEFT"))

    blocos, contagem = [], {"cabecalho/rodapé": 0, "imagem sem legenda": 0, "nota": 0, "fórmula": 0}

    def visitar(ref):
        item = indice.get(ref)
        if item is None:
            return
        if ref.startswith("#/groups"):
            for c in item.get("children", []):
                visitar(c["$ref"])
            return
        rotulo = item.get("label")
        if rotulo in ("page_header", "page_footer"):
            contagem["cabecalho/rodapé"] += 1
        elif rotulo in ("picture", "table", "chart"):
            legendas = [indice[c["$ref"]] for c in item.get("captions", []) if c["$ref"] in indice]
            texto = " ".join(l.get("text", "") for l in legendas).strip()
            m = LEGENDA.match(texto)
            if not m:
                contagem["imagem sem legenda"] += 1
                return
            pagina, cx = caixa(item)
            caixas = [cx] + [caixa(l)[1] for l in legendas if caixa(l)[0] == pagina]
            blocos.append({"tipo": "legenda", "texto": m.group(3).strip(),
                           "chave": (tipo_do_rotulo(m.group(1)), int(m.group(2))),
                           "pagina": pagina, "caixas": [c for c in caixas if c]})
        elif rotulo == "section_header":
            blocos.append({"tipo": "titulo", "texto": item.get("text", "")})
        elif rotulo == "footnote":
            contagem["nota"] += 1
            blocos.append({"tipo": "nota", "texto": item.get("text", "")})
        elif rotulo == "formula":
            contagem["fórmula"] += 1
            blocos.append({"tipo": "formula", "texto": item.get("text", "")})
        elif rotulo == "caption":
            return  # lida junto com a figura ou tabela a que pertence
        elif item.get("text", "").strip():
            blocos.append({"tipo": "texto", "texto": item["text"]})

    for c in d["body"]["children"]:
        visitar(c["$ref"])
    log("descartados do JSON: " + ", ".join(f"{v} {k}" for k, v in contagem.items()))
    return blocos


def blocos_do_md(md):
    blocos = []
    for linha in md.splitlines():
        linha = linha.strip()
        if not linha or linha.startswith(("![", "<!--", "|")):
            continue
        if linha.startswith("#"):
            blocos.append({"tipo": "titulo", "texto": linha.lstrip("#").strip()})
            continue
        m = LEGENDA.match(linha)
        if m and len(linha) < 600:
            blocos.append({"tipo": "legenda", "texto": m.group(3).strip(),
                           "chave": (tipo_do_rotulo(m.group(1)), int(m.group(2)))})
            continue
        blocos.append({"tipo": "texto", "texto": linha})
    return blocos


# ---------------------------------------------------------------- roteiro

def normalizar_titulo(t):
    """'1. INTRODUCTION' -> '1. Introduction'."""
    t = limpar(t)
    if t.isupper():
        t = re.sub(r"[A-ZÀ-Ý]", lambda m: m.group(0).lower(), t)
        t = re.sub(r"^([\d.\s]*)(\w)", lambda m: m.group(1) + m.group(2).upper(), t)
    return t


def montar_roteiro(blocos, titulo, autor, lingua):
    """Devolve (capítulos, legendas). Capítulo = (nome, texto falado)."""
    rot = ROTULOS[lingua]
    abertura = f"{titulo}. {autor}." if autor else f"{titulo}."
    capitulos = [["Abertura", [abertura, PAUSA_CAPITULO]]]
    legendas = {b["chave"]: b for b in blocos if b["tipo"] == "legenda"}
    citadas = set()
    for b in blocos:
        if b["tipo"] == "texto":
            for m in MENCAO.finditer(b["texto"]):
                for n in numeros_citados(m.group(2)):
                    citadas.add((tipo_do_rotulo(m.group(1)), n))
    anunciadas, pendentes = set(), []

    def anunciar(chave):
        """Guarda o anúncio para o fim do parágrafo (que pode continuar na página seguinte)."""
        if chave in anunciadas or chave not in legendas:
            return
        anunciadas.add(chave)
        pendentes.append(chave)

    def descarregar():
        for tipo, n in pendentes:
            rotulo = f"{rot[tipo]} {n}"
            capitulos[-1][1] += [PAUSA_FIGURA, f"[[fig {tipo}-{n}]]",
                                 f"{rotulo}, {rot['anuncio']}. {limpar(legendas[(tipo, n)]['texto'])}",
                                 PAUSA_FIGURA]
        pendentes.clear()

    # Cabeçalho corrido que o Docling não marcou ("354 M. P. Feldman"): linha curta
    # que se repete pelo documento mudando só o número.
    repeticoes = {}
    for b in blocos:
        if b["tipo"] == "texto" and len(b["texto"].split()) < 12:
            chave = re.sub(r"\d+", "#", b["texto"].strip())
            repeticoes[chave] = repeticoes.get(chave, 0) + 1
    corridos = {k for k, v in repeticoes.items() if v >= 3 and "#" in k}

    tem_secoes = any(b["tipo"] == "titulo" and SECAO_PRINCIPAL.match(limpar(b["texto"]))
                     for b in blocos)
    no_corpo = False       # já passou da capa e do resumo
    no_resumo = False
    primeiro_titulo = False
    descartadas = 0

    for b in blocos:
        tipo, texto = b["tipo"], b["texto"].strip()
        if tipo == "titulo":
            cab = normalizar_titulo(texto)
            if FIM_DE_LEITURA.match(cab):
                log(f"fim da leitura na seção '{cab}'")
                break
            if not no_corpo:
                if tem_secoes and SECAO_PRINCIPAL.match(cab):
                    no_corpo = True
                elif not tem_secoes and primeiro_titulo:
                    no_corpo = True
                else:
                    primeiro_titulo = True
                    no_resumo = bool(RESUMO.match(cab))
                    continue
            descarregar()
            if SECAO_PRINCIPAL.match(cab) and not SUBSECAO.match(cab):
                nome = re.sub(r"^\d+\.?\s+", "", cab)
                capitulos.append([nome, [f"{nome}.", PAUSA_CAPITULO]])
            else:
                sub = SUBSECAO.sub("", cab)
                capitulos[-1][1] += [PAUSA_SUBTITULO, f"{sub}.", PAUSA_SUBTITULO]
            continue

        # Texto sem palavra nenhuma ("1.00") costuma ser rótulo de eixo solto de um gráfico.
        if tipo == "texto" and (RUIDO.match(texto) or AFILIACAO.match(texto)
                                or re.sub(r"\d+", "#", texto) in corridos
                                or not re.search(r"[A-Za-zÀ-ÿ]{2,}", texto)):
            descartadas += 1
            continue
        if not no_corpo:
            # Da capa só se lê o resumo.
            if no_resumo and tipo == "texto":
                capitulos[0][1].insert(-1, limpar(texto))
            elif tipo == "texto" and re.match(r"^Abstract\s+", texto):
                capitulos[0][1].insert(-1, "Abstract. " + limpar(texto[9:]))
            else:
                descartadas += 1
            continue

        if tipo == "texto":
            partes = capitulos[-1][1]
            anterior = partes[-1] if partes else ""
            # Parágrafo partido na virada de página: o trecho anterior não fecha a frase
            # e este começa em minúscula. Emenda os dois.
            if (anterior and not anterior.startswith("[[") and not re.search(r"[.!?:;\"”)]$", anterior)
                    and texto[:1].islower()):
                partes[-1] = anterior + " " + limpar(texto)
            else:
                partes.append(limpar(texto))
            for m in MENCAO.finditer(texto):
                for n in numeros_citados(m.group(2)):
                    anunciar((tipo_do_rotulo(m.group(1)), n))
            if re.search(r"[.!?:\"”)]$", partes[-1]):
                descarregar()
        elif tipo == "legenda" and b["chave"] not in citadas:
            anunciar(b["chave"])   # figura que o texto nunca cita: anuncia onde está
        # notas e fórmulas: fora do áudio nesta versão

    descarregar()
    log(f"{descartadas} trechos de capa, resumo editorial ou contato descartados")
    log(f"{len(anunciadas)} de {len(legendas)} figuras e tabelas anunciadas")
    return [(nome, "\n".join(partes)) for nome, partes in capitulos], legendas


# ---------------------------------------------------------------- figuras

def recortar_figuras(pdf, legendas, pasta):
    """Recorta cada figura/tabela (com a legenda) do PDF. Devolve {chave: jpeg em bytes}."""
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(str(pdf))
    pasta.mkdir(parents=True, exist_ok=True)
    escala, folga, jpegs, linhas = 3, 6, {}, []
    paginas = {}
    for chave, b in sorted(legendas.items()):
        tipo, n = chave
        nome = f"{'Figura' if tipo == 'figura' else 'Tabela'} {n:02d}"
        linhas.append(f"{nome}: {html.unescape(b['texto'])}")
        if not b.get("caixas"):
            continue
        pg = b["pagina"]
        if pg not in paginas:
            pagina = doc[pg - 1]
            paginas[pg] = (pagina.render(scale=escala).to_pil(), pagina.get_size()[1])
        img, altura = paginas[pg]
        l = min(c[0] for c in b["caixas"]) - folga
        r = max(c[2] for c in b["caixas"]) + folga
        # origem no canto inferior esquerdo: t é o maior y, b o menor
        topo = max(max(c[1], c[3]) for c in b["caixas"]) + folga
        base = min(min(c[1], c[3]) for c in b["caixas"]) - folga
        recorte = img.crop((max(0, int(l * escala)), max(0, int((altura - topo) * escala)),
                            min(img.width, int(r * escala)), min(img.height, int((altura - base) * escala))))
        recorte.save(pasta / f"{nome}.png")
        miniatura = recorte.copy()
        miniatura.thumbnail((1000, 1000))
        buf = io.BytesIO()
        miniatura.convert("RGB").save(buf, "JPEG", quality=80)
        jpegs[chave] = buf.getvalue()
    (pasta / "legendas.txt").write_text("\n\n".join(linhas) + "\n", encoding="utf-8")
    log(f"{len(jpegs)} imagens recortadas em {pasta}")
    return jpegs


# ---------------------------------------------------------------- voz

def rodar(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        log(f"ERRO em: {' '.join(map(str, cmd))}\nstdout: {r.stdout}\nstderr: {r.stderr}")
        sys.exit(1)
    return r.stdout


def duracao_ms(arquivo):
    s = rodar(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "csv=p=0", str(arquivo)])
    return int(float(s.strip()) * 1000)


_kokoro = None


def sintetizar_kokoro(texto, wav, voz, lingua, modelos):
    """Kokoro por parágrafo, com silêncio entre parágrafos e nas marcas de pausa.

    Devolve as marcas de figura [(id, início_ms, fim_ms)] dentro do WAV.
    O espeak-ng vem do Homebrew: o que acompanha o pacote espeakng-loader traz
    gravado o caminho da máquina onde foi compilado e não acha os próprios dados.
    """
    global _kokoro
    import numpy as np
    import soundfile as sf
    from kokoro_onnx import Kokoro
    from kokoro_onnx.config import EspeakConfig

    if _kokoro is None:
        brew_lib = Path("/opt/homebrew/lib/libespeak-ng.dylib")
        brew_dados = Path("/opt/homebrew/share/espeak-ng-data")
        if brew_lib.exists() and brew_dados.exists():
            config = EspeakConfig(lib_path=str(brew_lib), data_path=str(brew_dados))
        else:
            log("espeak-ng do Homebrew não encontrado; usando o do pacote (pode falhar no macOS)")
            config = None
        _kokoro = Kokoro(str(Path(modelos) / "kokoro-v1.0.onnx"),
                         str(Path(modelos) / "voices-v1.0.bin"), espeak_config=config)
    sr = 24000
    blocos, total, marcas, figura = [], 0, [], None
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha:
            continue
        fig = re.fullmatch(r"\[\[fig (\S+)\]\]", linha)
        if fig:
            figura = (fig.group(1), total)
            continue
        pausa = re.fullmatch(r"\[\[slnc (\d+)\]\]", linha)
        if pausa:
            silencio = np.zeros(int(sr * int(pausa.group(1)) / 1000), dtype=np.float32)
            blocos.append(silencio)
            total += len(silencio)
            continue
        amostras, sr = _kokoro.create(linha, voice=voz, speed=1.0, lang=lingua)
        amostras = amostras.astype(np.float32)
        blocos.append(amostras)
        total += len(amostras)
        if figura:
            marcas.append((figura[0], figura[1] * 1000 // sr, total * 1000 // sr))
            figura = None
        silencio = np.zeros(int(sr * 0.35), dtype=np.float32)
        blocos.append(silencio)
        total += len(silencio)
    sf.write(str(wav), np.concatenate(blocos), sr)
    return marcas


def gravar_capitulos(mp3, capitulos):
    """capitulos: [(início_ms, fim_ms, título, jpeg ou None)] -> CTOC + CHAP (ID3v2.3)."""
    from mutagen.id3 import ID3, CTOC, CHAP, TIT2, APIC, CTOCFlags
    tags = ID3(str(mp3))
    tags.delall("CHAP")
    tags.delall("CTOC")
    ids = [f"ch{i:03d}" for i in range(len(capitulos))]  # zeros à esquerda: há leitor que ordena pelo id
    tags.add(CTOC(element_id="toc", flags=CTOCFlags.TOP_LEVEL | CTOCFlags.ORDERED,
                  child_element_ids=ids, sub_frames=[TIT2(text=["Capítulos"])]))
    for cid, (ini, fim, nome, jpeg) in zip(ids, capitulos):
        sub = [TIT2(text=[nome])]
        if jpeg:
            sub.append(APIC(encoding=3, mime="image/jpeg", type=0, desc=nome, data=jpeg))
        tags.add(CHAP(element_id=cid, start_time=int(ini), end_time=int(fim), sub_frames=sub))
    salvar_em_ordem(tags, mp3)


def salvar_em_ordem(tags, mp3):
    """Grava os quadros com os capítulos em ordem cronológica no arquivo.

    O mutagen ordena os quadros por tamanho, e capítulo com imagem é maior: eles
    iam para o fim, e o ffprobe (que lê na ordem do arquivo) listava fora de ordem.
    """
    from mutagen.id3._tags import save_frame

    def chave(f):
        return {"CTOC": (1, 0), "CHAP": (2, getattr(f, "start_time", 0)), "APIC": (3, 0)}.get(f.FrameID, (0, 0))

    tags._write = lambda config: bytearray().join(
        save_frame(f, config=config) for f in sorted(tags.values(), key=chave))
    tags.save(str(mp3), v2_version=3)


# ---------------------------------------------------------------- extração

def extrair_pdf(pdf, trab):
    """PDF -> JSON e Markdown pelo Docling, com o leitor pypdfium2.

    O leitor padrão do Docling corrompeu um artigo de revista com fontes Type 1C
    (letras sumidas, palavras grudadas); o pypdfium2 leu o mesmo arquivo sem erro.
    Caminho de saída absoluto: com caminho relativo o Docling aninha as pastas.
    """
    docling = Path(sys.executable).parent / "docling"
    if not docling.exists():
        docling = "docling"
    log(f"extraindo {pdf.name} com o Docling (pode levar alguns minutos)")
    rodar([str(docling), str(pdf.resolve()), "--pdf-backend", "pypdfium2", "--to", "json",
           "--to", "md", "--image-export-mode", "placeholder", "--output", str(trab.resolve())])
    return trab / f"{pdf.stem}.json", trab / f"{pdf.stem}.md"


def conferir_extracao(texto):
    """Palavras com 22 letras ou mais indicam espaços perdidos na extração."""
    suspeitas = re.findall(r"[A-Za-zÀ-ÿ]{22,}", texto)
    if len(suspeitas) > 5:
        log(f"ATENÇÃO: {len(suspeitas)} palavras anormalmente longas, a extração pode ter "
            f"perdido espaços. Exemplos: {', '.join(suspeitas[:3])}")
    else:
        log(f"conferência da extração: ok ({len(suspeitas)} palavras suspeitas)")


# ---------------------------------------------------------------- principal

def main():
    raiz = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description="PDF para MP3 com capítulos.")
    ap.add_argument("entrada", help="arquivo .pdf, ou .json/.md já extraído pelo Docling")
    ap.add_argument("--lingua", choices=["en", "pt"], default="en", help="língua do texto (padrão: en)")
    ap.add_argument("--titulo", help="padrão: nome do arquivo")
    ap.add_argument("--autor", default="")
    ap.add_argument("--motor", choices=["say", "kokoro"], default="kokoro")
    ap.add_argument("--voz", help="padrão: af_heart (en) ou pf_dora (pt) no Kokoro; Samantha ou Luciana no say")
    ap.add_argument("--modelos", default=str(raiz / "modelos"),
                    help="pasta com kokoro-v1.0.onnx e voices-v1.0.bin (padrão: modelos/)")
    ap.add_argument("--velocidade", type=int, default=185, help="palavras por minuto do say")
    ap.add_argument("--saida", default=os.environ.get("BOOK_TO_AUDIO_SAIDA", "saida"),
                    help="pasta onde cada obra ganha uma subpasta (padrão: $BOOK_TO_AUDIO_SAIDA ou saida/)")
    ap.add_argument("--nome", help="nome do MP3, sem extensão (padrão: nome do arquivo de entrada)")
    ap.add_argument("--sem-capitulos-de-figura", action="store_true",
                    help="não cria marca de capítulo com imagem em cada figura anunciada")
    a = ap.parse_args()

    entrada = Path(a.entrada)
    if not entrada.exists():
        ap.error(f"arquivo não encontrado: {entrada}")
    a.titulo = a.titulo or entrada.stem
    a.nome = a.nome or entrada.stem
    if not a.voz:
        a.voz = {("kokoro", "en"): "af_heart", ("kokoro", "pt"): "pf_dora",
                 ("say", "en"): "Samantha", ("say", "pt"): "Luciana"}[(a.motor, a.lingua)]
    if a.motor == "kokoro" and not (Path(a.modelos) / "kokoro-v1.0.onnx").exists():
        ap.error(f"modelos do Kokoro não encontrados em {a.modelos}. Rode ./baixar_modelos.sh")
    log(f"motor={a.motor} língua={a.lingua} voz={a.voz}")

    # Cada obra tem a própria pasta; os intermediários (WAV por capítulo) ficam
    # fora dela, em .trabalho/ no projeto, para não pesar numa pasta sincronizada.
    saida = Path(a.saida).expanduser() / a.nome
    saida.mkdir(parents=True, exist_ok=True)
    trab = raiz / ".trabalho" / a.nome
    trab.mkdir(parents=True, exist_ok=True)
    log(f"saída em {saida}")

    sufixo = entrada.suffix.lower()
    if sufixo == ".pdf":
        arq_json, arq_md = extrair_pdf(entrada, trab)
        conferir_extracao(arq_md.read_text(encoding="utf-8"))
        blocos = blocos_do_json(arq_json)
    elif sufixo == ".json":
        blocos = blocos_do_json(entrada)
    else:
        md = entrada.read_text(encoding="utf-8")
        conferir_extracao(md)
        blocos = blocos_do_md(md)

    capitulos, legendas = montar_roteiro(blocos, a.titulo, a.autor, a.lingua)
    jpegs = recortar_figuras(entrada, legendas, saida / "figuras") if sufixo == ".pdf" and legendas else {}

    # Roteiro legível, para conferir o que vai ser falado.
    roteiro = saida / "roteiro.txt"
    with roteiro.open("w", encoding="utf-8") as f:
        for i, (nome, texto) in enumerate(capitulos):
            falado = re.sub(r"\[\[.*?\]\]\n?", "", texto)
            f.write(f"===== Capítulo {i}: {nome} ({len(falado.split())} palavras)\n\n{falado}\n\n")
            log(f"capítulo {i}: {nome} — {len(falado.split())} palavras")
    log(f"roteiro gravado em {roteiro}")

    rot = ROTULOS[a.lingua]
    wavs, marcas_finais, inicio = [], [], 0
    for i, (nome, texto) in enumerate(capitulos):
        wav = trab / f"cap{i:02d}.wav"
        log(f"sintetizando capítulo {i} com a voz {a.voz}")
        if a.motor == "say":
            txt, aiff = trab / f"cap{i:02d}.txt", trab / f"cap{i:02d}.aiff"
            txt.write_text(re.sub(r"\[\[fig \S+\]\]\n?", "", texto), encoding="utf-8")
            rodar(["say", "-v", a.voz, "-r", str(a.velocidade), "-o", str(aiff), "-f", str(txt)])
            rodar(["ffmpeg", "-v", "error", "-y", "-i", str(aiff), "-ar", "24000", "-ac", "1", str(wav)])
            marcas = []
        else:
            marcas = sintetizar_kokoro(texto, wav, a.voz, "en-us" if a.lingua == "en" else "pt-br", a.modelos)
        d = duracao_ms(wav)
        # Cada figura anunciada abre um capítulo que vai até a próxima figura ou o fim
        # da seção: a imagem fica na tela enquanto o texto continua falando dela.
        pontos = [(0, nome, None)]
        for fid, ini, fim in ([] if a.sem_capitulos_de_figura else marcas):
            tipo, n = fid.split("-")
            pontos.append((ini, f"{nome} · {rot[tipo]} {n}", jpegs.get((tipo, int(n)))))
        for j, (ini, titulo, jpeg) in enumerate(pontos):
            fim = pontos[j + 1][0] if j + 1 < len(pontos) else d
            if fim > ini:
                marcas_finais.append((inicio + ini, inicio + fim, titulo, jpeg))
        inicio += d
        wavs.append(wav)

    lista = trab / "lista.txt"
    lista.write_text("".join(f"file '{w.resolve()}'\n" for w in wavs), encoding="utf-8")
    mp3 = saida / f"{a.nome}.mp3"
    rodar(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lista),
           "-c:a", "libmp3lame", "-b:a", "64k", "-id3v2_version", "3",
           "-metadata", f"title={a.titulo}", "-metadata", f"artist={a.autor}",
           "-metadata", f"album={a.titulo}", "-metadata", "genre=Audiobook", str(mp3)])
    gravar_capitulos(mp3, marcas_finais)
    caps = rodar(["ffprobe", "-v", "error", "-show_chapters", "-of", "csv=p=0", str(mp3)])
    com_imagem = sum(1 for m in marcas_finais if m[3])
    log(f"MP3 pronto: {mp3} — {inicio / 60000:.1f} min, {len(caps.strip().splitlines())} capítulos "
        f"({com_imagem} com imagem)")


if __name__ == "__main__":
    main()
