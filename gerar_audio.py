#!/usr/bin/env python3
"""book-to-audio 0.4.0 — PDF para MP3 com capítulos, figuras e tabelas.

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
import shutil
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
    r"JEL\b|HISTORY\b|Received\b|ISSN\b|This is an Open Access article|"
    r"(Fonte|Nota|Notas|Source|Note)\s*:(?=.{0,200}$))", re.IGNORECASE)
# Aviso de licença da editora, inteiro ou em pedaço (a continuação começa em minúscula e
# seria emendada no parágrafo anterior pela regra de parágrafo partido).
LICENCA = re.compile(r"creativecommons\.org|\bnc-nd/|which permits (unrestricted |non-commercial )?re-?use|"
                     r"distributed under the terms of the Creative Commons", re.IGNORECASE)
# Hífen de fim de linha que a extração deixou solto: "so - ciais", "Amé - rica".
HIFEN_SOLTO = re.compile(r"\b([A-Za-zÀ-ÿ]{1,6}) - ([a-zà-ÿ]{2,})")
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


# Barra entre palavras não tem som: "Nacional/Capes" saía emendado. Vira pausa curta.
# Unidades de uma letra (km/h, m/s) ficam de fora, porque o lado direito tem uma letra só.
BARRA = re.compile(r"(?<=[A-Za-zÀ-ÿ]{2})\s?/\s?(?=[A-Za-zÀ-ÿ]{2})")


def limpar(texto):
    texto = html.unescape(texto)
    texto = re.sub(r"\be/ou\b", "e ou", texto)
    texto = BARRA.sub(", ", texto)
    texto = HIFEN_SOLTO.sub(r"\1\2", texto)
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
    titulo_doc = titulo
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
                    if not primeiro_titulo:
                        titulo_doc = cab
                    primeiro_titulo = True
                    no_resumo = bool(RESUMO.match(cab))
                    continue
            descarregar()
            if SECAO_PRINCIPAL.match(cab) and not SUBSECAO.match(cab):
                nome = re.sub(r"^\d+\.?\s+", "", cab)
                capitulos.append([nome, [f"{nome}.", PAUSA_CAPITULO]])
            elif not tem_secoes and len(cab.split()) <= 6:
                # Documento sem numeração: título curto ("Introdução", "Base de dados") abre
                # capítulo. Título longo costuma ser de tabela ou figura mal marcado.
                capitulos.append([cab, [f"{cab}.", PAUSA_CAPITULO]])
            else:
                sub = SUBSECAO.sub("", cab)
                capitulos[-1][1] += [PAUSA_SUBTITULO, f"{sub}.", PAUSA_SUBTITULO]
            continue

        # Texto sem palavra nenhuma ("1.00") costuma ser rótulo de eixo solto de um gráfico.
        if tipo == "texto" and (RUIDO.match(texto) or AFILIACAO.match(texto) or LICENCA.search(texto)
                                or re.sub(r"\d+", "#", texto) in corridos
                                or not re.search(r"[A-Za-zÀ-ÿ]{2,}", texto)):
            descartadas += 1
            continue
        # Sem seção numerada, o corpo começava só no segundo título. Capítulo de livro com um
        # título só e nenhuma seção interna ficava inteiro como "capa" (15 palavras de roteiro,
        # BACKLOG de 25/09/2026). Agora o primeiro parágrafo longo depois do título abre o corpo.
        if (not no_corpo and not tem_secoes and primeiro_titulo and tipo == "texto"
                and not no_resumo and len(texto.split()) >= 40):
            no_corpo = True
            # Capítulo próprio com o título do documento, sem falar o título de novo.
            capitulos.append([titulo_doc, [PAUSA_CAPITULO]])
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


# ---------------------------------------------------------------- voz própria (OmniVoice)
# Clona a voz a partir de uma gravação curta (5 a 10 s) com a transcrição num .txt de
# mesmo nome. Modelo: ajuste pt-BR do OmniVoice (k2-fsa), pesos de uso não comercial.
# Medido em 28/09/2026 num M3 Pro: cerca de 0,8 do tempo real com referência de 7 a 10 s.
# O modelo pula palavras em frase longa, sobretudo com aparte entre travessões: por isso
# o texto vai em trechos curtos e cada trecho é conferido pelo Whisper.

OMNIVOICE_MODELO = "edwixx/omnivoice-brpt-v15"
# Pausas e cortes revistos em 28/09/2026 depois da escuta do capítulo inteiro: cortar na
# vírgula punha entonação de fim de frase e pausa longa no meio da frase, e 0,25 s entre
# frases soava corrido. Agora só frase muito longa é cortada na vírgula, o silêncio que o
# modelo deixa em cada ponta é aparado (com rampa, para não estalar) e as pausas seguem a
# narração humana: cerca de 0,5 s entre frases e 1 s entre parágrafos.
TRECHO_MAXIMO = 350          # caracteres; só acima disso a frase é cortada numa vírgula
PAUSA_TRECHO, PAUSA_FRASE, PAUSA_PARAGRAFO = 0.3, 0.5, 0.45   # a do parágrafo soma à da frase

_omni = None


def _cortar_longa(p, maximo):
    if len(p) <= maximo:
        return [p]
    virgulas = [m.end() for m in re.finditer(r",\s", p) if 40 <= m.end() <= len(p) - 40]
    if not virgulas:
        return [p]
    i = min(virgulas, key=lambda x: abs(x - len(p) / 2))
    return _cortar_longa(p[:i].strip(), maximo) + _cortar_longa(p[i:].strip(), maximo)


def encurtar_silencios(a, sr, limiar, maximo=0.30, alvo=0.22, janela=0.01):
    """Dentro de um trecho, silêncio acima de `maximo` vira `alvo` segundos. O modelo às
    vezes exagera a pausa numa vírgula (0,43 s antes de "tema", 28/09/2026), e no meio da
    frase isso quebra o sentido. As pausas entre frases são postas depois, fora daqui."""
    import numpy as np
    n = int(sr * janela)
    if len(a) < n * 3:
        return a
    quadros = np.abs(a[: len(a) // n * n]).reshape(-1, n).max(axis=1) <= limiar
    partes, i, ultimo = [], 0, 0
    while i < len(quadros):
        if quadros[i]:
            j = i
            while j < len(quadros) and quadros[j]:
                j += 1
            if (j - i) * janela > maximo:
                meio = int(sr * alvo / 2)
                partes.append(a[ultimo : i * n + meio])
                ultimo = j * n - meio
            i = j
        else:
            i += 1
    partes.append(a[ultimo:])
    return np.concatenate(partes)


def aparar(audio, sr=24000, limiar_db=-55, folga=0.03, folga_fim=0.15, rampa=0.02):
    """Tira o silêncio do começo e do fim e suaviza as pontas, para a pausa ser a nossa."""
    import numpy as np
    if not len(audio):
        return audio
    limiar = np.abs(audio).max() * 10 ** (limiar_db / 20)
    idx = np.where(np.abs(audio) > limiar)[0]
    if not len(idx):
        return audio
    ini = max(idx[0] - int(sr * folga), 0)
    # Folga maior no fim: a última sílaba costuma ser dita baixo. Com -40 dB e 30 ms,
    # "tema" saiu cortado ao meio (28/09/2026).
    fim = min(idx[-1] + int(sr * folga_fim), len(audio))
    a = audio[ini:fim].copy()
    a = encurtar_silencios(a, sr, limiar)
    n = min(int(sr * rampa), len(a) // 2)
    if n:
        a[:n] *= np.linspace(0, 1, n, dtype=a.dtype)
        a[-n:] *= np.linspace(1, 0, n, dtype=a.dtype)
    return a


def fragmentar(frase, maximo=TRECHO_MAXIMO):
    """Frase em trechos: corta nos travessões com espaço e nos ponto e vírgula, e depois
    corta numa vírgula perto do meio o que ainda passar de `maximo` caracteres."""
    trechos = []
    for parte in re.split(r"\s+[–—],?\s+|;\s+", frase):
        parte = parte.strip(" ,–—")
        if parte:
            trechos += _cortar_longa(parte, maximo)
    return trechos


def _palavras(t):
    return re.findall(r"[0-9a-zà-ÿ]+(?:[.,][0-9]+)*", t.lower().replace("/", " "))


def conferir_trecho(original, transcrito):
    """(cobertura, razão): parte das palavras do original reconhecida na transcrição, e
    tamanho da transcrição sobre o original (acima de 1,4 sugere repetição)."""
    import difflib
    a, b = _palavras(original), _palavras(transcrito)
    if not a:
        return 1.0, 1.0
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    return sum(m.size for m in sm.get_matching_blocks()) / len(a), len(b) / len(a)


class Conferente:
    """Mantém o whisper-server carregado e transcreve cada trecho gerado."""

    def __init__(self, modelo, lingua, trab):
        import socket
        import time
        import urllib.request
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        self.porta = s.getsockname()[1]
        s.close()
        self.tmp = trab / "conferencia.wav"
        self.proc = subprocess.Popen(["whisper-server", "-m", str(modelo), "-l", lingua,
                                      "--port", str(self.porta), "-t", "6"],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        limite = time.time() + 120
        while time.time() < limite:
            if self.proc.poll() is not None:
                raise RuntimeError("whisper-server encerrou ao iniciar")
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{self.porta}/", timeout=2)
                return
            except Exception:
                time.sleep(0.5)
        raise RuntimeError("whisper-server não respondeu em 120 s")

    def transcrever(self, audio, sr):
        import librosa
        import soundfile as sf
        sf.write(str(self.tmp), librosa.resample(audio, orig_sr=sr, target_sr=16000), 16000,
                 subtype="PCM_16")
        r = subprocess.run(["curl", "-s", "--max-time", "120", f"http://127.0.0.1:{self.porta}/inference",
                            "-F", f"file=@{self.tmp}", "-F", "response_format=json",
                            "-F", "temperature=0.0"], capture_output=True, text=True)
        try:
            return json.loads(r.stdout).get("text", "")
        except json.JSONDecodeError:
            log(f"conferência: resposta inválida do whisper-server: {r.stdout[:200]} {r.stderr[:200]}")
            return ""

    def fechar(self):
        self.proc.terminate()


def carregar_omnivoice(referencia):
    global _omni
    if _omni is None:
        import torch
        from omnivoice import OmniVoice
        disp = "mps" if torch.backends.mps.is_available() else "cpu"
        log(f"carregando o OmniVoice ({OMNIVOICE_MODELO}) em {disp}")
        modelo = OmniVoice.from_pretrained(OMNIVOICE_MODELO, device_map=disp,
                                           dtype=torch.float16 if disp == "mps" else torch.float32)
        texto_ref = referencia.with_suffix(".txt").read_text(encoding="utf-8").strip()
        _omni = (modelo, modelo.create_voice_clone_prompt(ref_audio=str(referencia), ref_text=texto_ref))
    return _omni


def gerar_conferido(texto, lingua, conferente, falhas, capitulo, contagem, tentativas=3):
    """Gera um trecho; se a conferência achar palavra faltando ou repetição, gera de novo
    (até `tentativas` vezes) e fica com a melhor versão."""
    import numpy as np
    modelo, prompt = _omni
    melhor = None
    for _ in range(tentativas):
        a = modelo.generate(text=texto, language=lingua, voice_clone_prompt=prompt)
        a = np.asarray(a[0] if isinstance(a, (list, tuple)) else a, dtype=np.float32).squeeze()
        if conferente is None:
            return a
        transcrito = conferente.transcrever(a, 24000)
        cob, raz = conferir_trecho(texto, transcrito)
        n = len(_palavras(texto))
        # Até 3 palavras o Whisper erra mais que o modelo: aceita sem conferir.
        ok = n <= 3 or (cob >= (0.5 if n < 6 else 0.8) and raz <= 1.4)
        nota = (ok, cob, -abs(raz - 1))
        if melhor is None or nota > melhor[0]:
            melhor = (nota, a, transcrito, cob, raz)
        if ok:
            break
        contagem["refeitos"] += 1
    contagem["trechos"] += 1
    if contagem["trechos"] % 50 == 0:
        log(f"  {contagem['trechos']} trechos gerados, {contagem['refeitos']} refeitos")
    if not melhor[0][0]:
        falhas.append((capitulo, texto, melhor[2].strip(), melhor[3], melhor[4]))
    return melhor[1]


def sintetizar_omnivoice(texto, wav, referencia, lingua, conferente, falhas, capitulo, contagem):
    """Mesmo contrato do sintetizar_kokoro: grava o WAV e devolve as marcas de figura."""
    import numpy as np
    import soundfile as sf
    carregar_omnivoice(referencia)
    sr = 24000
    blocos, total, marcas, figura = [], 0, [], None

    def por(a):
        nonlocal total
        blocos.append(a)
        total += len(a)

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
            por(np.zeros(int(sr * int(pausa.group(1)) / 1000), dtype=np.float32))
            continue
        for frase in [f for f in re.split(r"(?<=[.!?])\s+", linha) if f.strip()]:
            trechos = fragmentar(frase)
            for i, trecho in enumerate(trechos):
                por(aparar(gerar_conferido(trecho, lingua, conferente, falhas, capitulo, contagem)))
                por(np.zeros(int(sr * (PAUSA_TRECHO if i < len(trechos) - 1 else PAUSA_FRASE)), dtype=np.float32))
        if figura:
            marcas.append((figura[0], figura[1] * 1000 // sr, total * 1000 // sr))
            figura = None
        por(np.zeros(int(sr * PAUSA_PARAGRAFO), dtype=np.float32))
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


# ---------------------------------------------------------------- pasta de saída

ENV_CLAUDE = Path.home() / ".claude" / ".env"


def ler_config(chave):
    """(valor, origem) de uma chave: variável de ambiente, depois ~/.claude/.env."""
    valor = os.environ.get(chave, "").strip()
    if valor:
        return valor, "ambiente"
    if ENV_CLAUDE.exists():
        for linha in ENV_CLAUDE.read_text(encoding="utf-8").splitlines():
            if linha.strip().startswith(f"{chave}="):
                valor = linha.split("=", 1)[1].strip().strip('"').strip("'")
                if valor:
                    return valor, "env"
    return "", "padrão"


def gravar_config(chave, valor):
    """Grava chave=valor em ~/.claude/.env (permissão 600), preservando as outras linhas."""
    ENV_CLAUDE.parent.mkdir(parents=True, exist_ok=True)
    linhas = ENV_CLAUDE.read_text(encoding="utf-8").splitlines() if ENV_CLAUDE.exists() else []
    linhas = [l for l in linhas if not l.strip().startswith(f"{chave}=")]
    linhas.append(f"{chave}={valor}")
    ENV_CLAUDE.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    os.chmod(ENV_CLAUDE, 0o600)


def resolver_pasta(raiz):
    """(pasta, origem). Ordem: variável de ambiente, ~/.claude/.env, saida/ do projeto."""
    valor, origem = ler_config("BOOK_TO_AUDIO_SAIDA")
    if valor:
        return Path(valor).expanduser().resolve(), origem
    return raiz / "saida", "padrão"


def definir_pasta(caminho):
    pasta = Path(caminho).expanduser().resolve()
    pasta.mkdir(parents=True, exist_ok=True)
    gravar_config("BOOK_TO_AUDIO_SAIDA", pasta)
    return pasta


def resolver_caminho(chave):
    valor, _ = ler_config(chave)
    return Path(valor).expanduser().resolve() if valor else None


# ---------------------------------------------------------------- identificação

PALAVRAS_PT = {"de", "que", "não", "para", "com", "uma", "os", "as", "dos", "das", "se", "por", "mais", "como", "é", "são", "também", "pela", "pelo"}
PALAVRAS_EN = {"the", "of", "and", "to", "in", "is", "that", "for", "with", "as", "are", "this", "by", "which", "on", "be", "from", "it"}


def identificar(pdf):
    """Dados brutos para decidir título, autor e língua. A interpretação fica com quem chama."""
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(str(pdf))
    meta = {k: v for k, v in doc.get_metadata_dict().items() if k in ("Title", "Author", "Subject") and v}
    textos = []
    for i in range(min(len(doc), 3)):
        textos.append(doc[i].get_textpage().get_text_range())
    palavras = re.findall(r"[a-zà-ÿ]+", " ".join(textos).lower())
    pt = sum(1 for w in palavras if w in PALAVRAS_PT)
    en = sum(1 for w in palavras if w in PALAVRAS_EN)
    lingua = "pt" if pt > en else "en"
    print(f"arquivo: {pdf}")
    print(f"páginas: {len(doc)}")
    for k, v in meta.items():
        print(f"metadado {k}: {v[:300]}")
    print(f"língua provável: {lingua} (palavras frequentes: pt={pt}, en={en})")
    print("início da primeira página:")
    print(re.sub(r"\s+", " ", textos[0])[:1200] if textos else "(sem texto: PDF escaneado?)")


# ---------------------------------------------------------------- principal

def main():
    raiz = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description="PDF para MP3 com capítulos.")
    ap.add_argument("entrada", nargs="?", help="arquivo .pdf, ou .json/.md já extraído pelo Docling")
    ap.add_argument("--identificar", action="store_true",
                    help="só mostra páginas, metadados, língua provável e o início do texto")
    ap.add_argument("--so-roteiro", action="store_true",
                    help="para depois do roteiro: mostra capítulos e duração estimada, sem gerar voz")
    ap.add_argument("--mostrar-pasta", action="store_true", help="mostra a pasta de saída e de onde ela vem")
    ap.add_argument("--definir-pasta", metavar="CAMINHO", help="grava a pasta de saída em ~/.claude/.env")
    ap.add_argument("--lingua", choices=["en", "pt"], default="en", help="língua do texto (padrão: en)")
    ap.add_argument("--titulo", help="padrão: nome do arquivo")
    ap.add_argument("--autor", default="")
    ap.add_argument("--motor", choices=["auto", "omnivoice", "kokoro", "say"], default="auto",
                    help="auto: OmniVoice com a sua voz em português, se houver referência gravada; "
                         "senão Kokoro")
    ap.add_argument("--voz", help="Kokoro: af_heart (en) ou pf_dora (pt); say: Samantha ou Luciana")
    ap.add_argument("--referencia", help="OmniVoice: gravação de referência (5 a 10 s), com a transcrição "
                    "num .txt de mesmo nome (padrão: BOOK_TO_AUDIO_VOZ_PT)")
    ap.add_argument("--sem-conferencia", action="store_true",
                    help="OmniVoice: não confere cada trecho com o Whisper")
    ap.add_argument("--definir-voz-pt", metavar="WAV", help="grava a referência de voz em português em ~/.claude/.env")
    ap.add_argument("--definir-whisper", metavar="MODELO", help="grava o modelo ggml do Whisper usado na conferência")
    ap.add_argument("--modelos", default=str(raiz / "modelos"),
                    help="pasta com kokoro-v1.0.onnx e voices-v1.0.bin (padrão: modelos/)")
    ap.add_argument("--velocidade", type=int, default=185, help="palavras por minuto do say")
    ap.add_argument("--saida", help="pasta onde cada obra ganha uma subpasta "
                    "(padrão: BOOK_TO_AUDIO_SAIDA no ambiente ou em ~/.claude/.env, senão saida/ no projeto)")
    ap.add_argument("--nome", help="nome do MP3, sem extensão (padrão: nome do arquivo de entrada)")
    ap.add_argument("--sem-capitulos-de-figura", action="store_true",
                    help="não cria marca de capítulo com imagem em cada figura anunciada")
    a = ap.parse_args()

    if a.definir_pasta:
        print(f"pasta definida: {definir_pasta(a.definir_pasta)}")
        return
    if a.definir_voz_pt:
        ref = Path(a.definir_voz_pt).expanduser().resolve()
        if not ref.exists() or not ref.with_suffix(".txt").exists():
            ap.error(f"preciso do áudio e da transcrição num .txt de mesmo nome: {ref}")
        gravar_config("BOOK_TO_AUDIO_VOZ_PT", ref)
        print(f"voz em português definida: {ref}")
        return
    if a.definir_whisper:
        modelo = Path(a.definir_whisper).expanduser().resolve()
        if not modelo.exists():
            ap.error(f"modelo não encontrado: {modelo}")
        gravar_config("BOOK_TO_AUDIO_WHISPER", modelo)
        print(f"modelo do Whisper definido: {modelo}")
        return
    if a.mostrar_pasta:
        pasta, origem = resolver_pasta(raiz)
        print(f"pasta: {pasta}")
        print(f"escolhida pelo usuário: {'não' if origem == 'padrão' else 'sim'} (origem: {origem})")
        print(f"voz em português: {resolver_caminho('BOOK_TO_AUDIO_VOZ_PT') or 'nenhuma (usa a Dora do Kokoro)'}")
        print(f"Whisper para conferência: {resolver_caminho('BOOK_TO_AUDIO_WHISPER') or 'nenhum (sem conferência)'}")
        return
    if not a.entrada:
        ap.error("informe o arquivo de entrada")
    entrada = Path(a.entrada).expanduser()
    if not entrada.exists():
        ap.error(f"arquivo não encontrado: {entrada}")
    if a.identificar:
        identificar(entrada)
        return
    a.titulo = a.titulo or entrada.stem
    a.nome = a.nome or entrada.stem
    referencia = Path(a.referencia).expanduser().resolve() if a.referencia else resolver_caminho("BOOK_TO_AUDIO_VOZ_PT")
    if a.motor == "auto":
        a.motor = "omnivoice" if a.lingua == "pt" and referencia and referencia.exists() else "kokoro"
    if a.motor == "omnivoice":
        if not referencia or not referencia.exists() or not referencia.with_suffix(".txt").exists():
            ap.error("OmniVoice precisa de uma gravação de referência e da transcrição num .txt de mesmo "
                     "nome: use --referencia ou --definir-voz-pt")
        a.voz = referencia.stem
    elif not a.voz:
        a.voz = {("kokoro", "en"): "af_heart", ("kokoro", "pt"): "pf_dora",
                 ("say", "en"): "Samantha", ("say", "pt"): "Luciana"}[(a.motor, a.lingua)]
    if a.motor == "kokoro" and not (Path(a.modelos) / "kokoro-v1.0.onnx").exists():
        ap.error(f"modelos do Kokoro não encontrados em {a.modelos}. Rode ./baixar_modelos.sh")
    log(f"motor={a.motor} língua={a.lingua} voz={a.voz}")

    # Cada obra tem a própria pasta; os intermediários (WAV por capítulo) ficam
    # fora dela, em .trabalho/ no projeto, para não pesar numa pasta sincronizada.
    saida = (Path(a.saida).expanduser() if a.saida else resolver_pasta(raiz)[0]) / a.nome
    saida.mkdir(parents=True, exist_ok=True)
    trab = raiz / ".trabalho" / a.nome
    trab.mkdir(parents=True, exist_ok=True)
    log(f"saída em {saida}")

    sufixo = entrada.suffix.lower()
    if sufixo == ".pdf":
        arq_json, arq_md = trab / f"{entrada.stem}.json", trab / f"{entrada.stem}.md"
        if arq_json.exists() and arq_md.exists() and arq_json.stat().st_mtime >= entrada.stat().st_mtime:
            log("extração já feita antes para este arquivo; reaproveitando")
        else:
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

    if a.so_roteiro:
        # Kokoro, 23/09/2026: 113 e 138 palavras por minuto nos dois documentos de referência.
        # OmniVoice com a referência rápida, 28/09/2026: 144. Os valores abaixo erram para mais.
        # Velocidade de geração: Kokoro 5x o tempo real; OmniVoice 0,49x num capítulo inteiro
        # (28/09/2026, 40,2 min em 82 min, com trechos curtos e conferência).
        ppm = {"kokoro": 110, "omnivoice": 135}.get(a.motor, a.velocidade)
        palavras = sum(len(re.sub(r"\[\[.*?\]\]", "", t).split()) for _, t in capitulos)
        minutos = palavras / ppm
        geracao = minutos / {"kokoro": 5, "omnivoice": 0.45}.get(a.motor, 90)
        print(f"RESUMO capítulos={len(capitulos)} palavras={palavras} "
              f"duração_estimada_min={minutos:.0f} geração_estimada_min={geracao:.0f} "
              f"figuras_e_tabelas={len(legendas)} roteiro={roteiro} pasta={saida}")
        return

    rot = ROTULOS[a.lingua]
    wavs, marcas_finais, inicio = [], [], 0
    conferente, falhas, contagem = None, [], {"trechos": 0, "refeitos": 0}
    if a.motor == "omnivoice" and not a.sem_conferencia:
        modelo_whisper = resolver_caminho("BOOK_TO_AUDIO_WHISPER")
        if not modelo_whisper or not modelo_whisper.exists() or not shutil.which("whisper-server"):
            log("ATENÇÃO: sem whisper-server ou sem modelo (BOOK_TO_AUDIO_WHISPER): gerando sem conferência")
        else:
            conferente = Conferente(modelo_whisper, a.lingua, trab)
            log(f"conferência ligada: {modelo_whisper.name}")
    for i, (nome, texto) in enumerate(capitulos):
        wav = trab / f"cap{i:02d}.wav"
        log(f"sintetizando capítulo {i} com a voz {a.voz}")
        if a.motor == "say":
            txt, aiff = trab / f"cap{i:02d}.txt", trab / f"cap{i:02d}.aiff"
            txt.write_text(re.sub(r"\[\[fig \S+\]\]\n?", "", texto), encoding="utf-8")
            rodar(["say", "-v", a.voz, "-r", str(a.velocidade), "-o", str(aiff), "-f", str(txt)])
            rodar(["ffmpeg", "-v", "error", "-y", "-i", str(aiff), "-ar", "24000", "-ac", "1", str(wav)])
            marcas = []
        elif a.motor == "omnivoice":
            marcas = sintetizar_omnivoice(texto, wav, referencia, a.lingua, conferente, falhas, nome, contagem)
            log(f"  {contagem['trechos']} trechos até aqui, {contagem['refeitos']} refeitos, "
                f"{len(falhas)} ainda incompletos")
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

    if conferente:
        conferente.fechar()
        rel = saida / "conferencia.txt"
        linhas = [f"Conferência pelo Whisper: {contagem['trechos']} trechos, {contagem['refeitos']} gerações "
                  f"refeitas, {len(falhas)} trechos que continuaram incompletos depois de 3 tentativas.", ""]
        for cap, orig, transc, cob, raz in falhas:
            linhas += [f"[{cap}] cobertura {cob:.0%}, tamanho {raz:.2f}", f"  texto:   {orig}", f"  ouvido:  {transc}", ""]
        rel.write_text("\n".join(linhas), encoding="utf-8")
        log(f"conferência: {contagem['trechos']} trechos, {contagem['refeitos']} refeitos, "
            f"{len(falhas)} incompletos (detalhes em {rel})")

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
