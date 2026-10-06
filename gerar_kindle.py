#!/usr/bin/env python3
"""book-to-audio 0.5.0 — PDF para EPUB, para ler no Kindle, com as figuras no ponto da citação.

Fluxo: PDF -> Docling (o mesmo JSON do gerar_audio.py, reaproveitado se já existe) ->
texto de leitura -> Markdown -> Pandoc -> EPUB.

O texto de leitura é o do PDF, sem as adaptações que o roteiro do áudio faz para a fala:
citação autor-ano, fórmula, nota de rodapé, "Fonte:" e referências ficam.

Regras:
- figura e tabela citadas entram logo depois do parágrafo que as cita pela primeira vez,
  com a legenda embaixo; as nunca citadas ficam onde estão no PDF;
- num livro (--livro), os capítulos vêm do sumário do próprio livro, e a numeração das
  figuras recomeça a cada capítulo;
- nota de rodapé vira nota do EPUB, que o Kindle abre numa janela a partir da chamada;
- fórmula e tabela entram como imagem recortada do PDF;
- arte decorativa (página inteira sem legenda, ou a mesma imagem repetida) sai.

Uso:
    uv run gerar_kindle.py artigo.pdf --lingua en --titulo "..." --autor "..."
    uv run gerar_kindle.py livro.pdf --livro --lingua pt --titulo "..." --autor "..."
    uv run gerar_kindle.py livro.pdf --paginas 33-54 --nome "..." --titulo "..."   (um capítulo)

Para mandar ao Kindle: e-mail para o endereço @kindle.com da conta, com o EPUB anexo e o
assunto em branco (a Amazon sempre converte EPUB; "convert" no assunto só vale para PDF),
ou o arquivo arrastado em amazon.com/sendtokindle. Limite de 50 MB por anexo.
"""
import argparse
import glob
import html
import io
import json
import re
import shutil
import subprocess
import sys
from collections import Counter, OrderedDict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
from gerar_audio import (FIM_DE_LEITURA, HIFEN_SOLTO, LEGENDA, LICENCA, MENCAO, SECAO_PRINCIPAL,  # noqa: E402
                         SUBSECAO, conferir_extracao, extrair_pdf, numeros_citados, resolver_pasta)

# Metadados editoriais de capa. Diferente do RUIDO do áudio, "Fonte:" e "Nota:" ficam.
RUIDO_LEITURA = re.compile(
    r"^(CONTACT\b|Correspondence|E-?mail\b|©|To cite this article|To link to this article|"
    r"Published online|Article views|View Crossmark|Supplemental data|∂ OPEN ACCESS|"
    r"Submit your article|View related articles|Full Terms & Conditions|JEL\b|HISTORY\b|Received\b|ISSN\b)",
    re.IGNORECASE)
FONTE = re.compile(r"^(Fonte|Fontes|Nota|Notas|Source|Sources|Note|Notes)\s*:", re.IGNORECASE)
PONTILHADO = re.compile(r"(\.\s?){5,}\s*\d+\s*$|…\s*\d+\s*$")  # linha de sumário
FECHA_FRASE = re.compile(r"[.!?:\"”)]$")
QUANTIDADE = {"de", "da", "do", "das", "dos", "em", "e", "a", "o", "as", "os", "até", "com", "por", "para", "entre",
               "são", "foram", "tabela", "tabelas", "figura", "figuras", "gráfico", "quadro", "seção", "capítulo",
               "art", "nº", "n", "p", "pp", "vol", "ano", "anos", "of", "in", "and", "to", "the", "table", "figure",
               "section", "chapter", "than", "from", "by"}
ESPECIAIS = re.compile(r"([\\`*_\[\]<>#$~^|{}@&])")


def log(msg):
    print(f"[gerar_kindle] {msg}", flush=True)


def ler(t):
    t = html.unescape(t or "").replace("\n", " ")
    t = HIFEN_SOLTO.sub(r"\1\2", t)
    t = re.sub(r"\s+([,.;:!?])", r"\1", t)
    t = re.sub(r"\s{2,}", " ", t)
    return t.strip()


def familia(palavra):
    p = palavra.lower()
    if p.startswith("fig"):
        return "figura"
    if p.startswith(("gráf", "graf")):
        return "grafico"
    if p.startswith("tab"):
        return "tabela"
    return "quadro"


def md(texto):
    """Escapa para o Markdown do Pandoc. As sentinelas de nota (\\x00id\\x00) passam."""
    t = ESPECIAIS.sub(r"\\\1", texto)
    t = re.sub(r"^(\d+)\.(\s)", r"\1\\.\2", t)
    t = re.sub(r"^([-+])(\s)", r"\\\1\2", t)
    return re.sub(r"\x00([^\x00]+)\x00", r"[^\1]", t)


def parecido(a, b):
    na = re.sub(r"[^a-zà-ÿ]", "", a.lower())[:25]
    nb = re.sub(r"[^a-zà-ÿ]", "", b.lower())[:25]
    return bool(na) and na == nb


# ---------------------------------------------------------------- leitura do JSON

def elementos_do_json(caminho, faixa=None, titulo=None):
    d = json.loads(Path(caminho).read_text(encoding="utf-8"))
    fora_da_faixa = []   # imagens sem legenda do resto do livro, para achar arte repetida
    # Cabeçalhos do livro inteiro: o do livro aparece em página par, o do capítulo em ímpar.
    cabecalhos = {ler(t["text"]) for t in d.get("texts", [])
                  if t.get("label") == "page_header" and len(t.get("text", "")) >= 15}
    if faixa:
        # Capítulo de um livro já extraído inteiro: fica só o que está nas páginas pedidas.
        def na_faixa(item):
            prov = item.get("prov") or []
            return bool(prov) and faixa[0] <= prov[0]["page_no"] <= faixa[1]
        for it in d.get("pictures", []):
            if not na_faixa(it) and not it.get("captions") and it.get("prov"):
                b = it["prov"][0]["bbox"]
                fora_da_faixa.append({"tipo": "imagem", "sub": "picture", "chave": None, "pagina": it["prov"][0]["page_no"],
                                      "caixa": (b["l"], b["t"], b["r"], b["b"], b.get("coord_origin", "BOTTOMLEFT"))})
        for k in ("texts", "pictures", "tables"):
            d[k] = [it for it in d.get(k, []) if na_faixa(it)]
    indice = {}
    for k in ("texts", "pictures", "tables", "groups"):
        for item in d.get(k, []):
            indice[item["self_ref"]] = item
    ligadas = {c["$ref"] for k in ("pictures", "tables") for it in d.get(k, [])
               for c in it.get("captions", [])}
    paginas = {k: (v["size"]["width"], v["size"]["height"]) for k, v in d.get("pages", {}).items()}
    chaves_cabecalho = {so_letras(c) for c in cabecalhos | ({titulo} if titulo else set()) if len(so_letras(c)) >= 12}
    els, cont = [], Counter()
    # Nota de rodapé que o Docling marcou como item de lista ("6." no marcador) ou como texto
    # ("40. Idem."): número na frente, no terço de baixo da página, e página com nota ou
    # número vizinho de uma nota conhecida. Num capítulo de teste foram 7 de 39.
    numeros_nota, paginas_com_nota = set(), set()
    for t in d.get("texts", []):
        if t.get("label") == "footnote":
            m = re.match(r"^(\d{1,3})\b", t.get("text", ""))
            if m:
                numeros_nota.add(int(m.group(1)))
            if t.get("prov"):
                paginas_com_nota.add(t["prov"][0]["page_no"])

    def parece_nota(item, numero):
        prov = item.get("prov") or []
        if not prov or numero is None or not numeros_nota:
            return False
        b, pg = prov[0]["bbox"], prov[0]["page_no"]
        h = paginas.get(str(pg), (595, 842))[1]
        topo = b["t"] if b.get("coord_origin", "BOTTOMLEFT") == "BOTTOMLEFT" else h - b["t"]
        vizinha = (numero - 1) in numeros_nota or (numero + 1) in numeros_nota
        return topo < 0.35 * h and (pg in paginas_com_nota or vizinha)

    def numero_na_frente(t):
        m = re.match(r"^(\d{1,3})\.?$", (t.get("marker") or "").strip()) if t.get("label") == "list_item" \
            else re.match(r"^(\d{1,3})\.\s", t.get("text", "")) if t.get("label") == "text" else None
        return int(m.group(1)) if m else None

    # As notas recuperadas também contam como vizinhas: a 39 era item de lista, e sem ela
    # o "40. Idem." ficava solto no meio do texto.
    for _ in range(5):
        novos = {n for t in d.get("texts", []) if (n := numero_na_frente(t)) is not None
                 and n not in numeros_nota and parece_nota(t, n)}
        if not novos:
            break
        numeros_nota |= novos

    def caixa(item):
        prov = item.get("prov") or []
        if not prov:
            return None, None
        b = prov[0]["bbox"]
        return prov[0]["page_no"], (b["l"], b["t"], b["r"], b["b"], b.get("coord_origin", "BOTTOMLEFT"))

    def visitar(ref):
        item = indice.get(ref)
        if item is None:
            return
        if ref.startswith("#/groups"):
            for c in item.get("children", []):
                visitar(c["$ref"])
            return
        rot = item.get("label")
        if rot in ("page_header", "page_footer", "document_index"):
            cont[rot] += 1
            return
        pag, cx = caixa(item)
        if rot in ("picture", "table", "chart"):
            if cx is None:
                cont["imagem sem posição"] += 1
                return
            legs = [indice[c["$ref"]] for c in item.get("captions", []) if c["$ref"] in indice]
            legenda = tirar_prefixos(ler(" ".join(l.get("text", "") for l in legs)), cabecalhos, 3)
            m = LEGENDA.match(legenda) if legenda else None
            largura, altura = abs(cx[2] - cx[0]), abs(cx[1] - cx[3])
            if not legenda and (largura < 60 or altura < 40):
                cont["imagem pequena sem legenda"] += 1
                return
            # Arte de página inteira sem legenda (capa, abertura de capítulo) é decoração.
            w_pag, h_pag = paginas.get(str(pag), (595, 842))
            if not legenda and largura * altura > 0.4 * w_pag * h_pag:
                cont["arte de página inteira"] += 1
                return
            els.append({"tipo": "imagem", "sub": rot, "legenda": legenda, "pagina": pag, "caixa": cx,
                        "chave": (familia(m.group(1)), int(m.group(2))) if m else None})
            return
        texto = ler(item.get("text", ""))
        if rot == "caption":
            if ref not in ligadas and texto:
                els.append({"tipo": "legenda_solta", "texto": texto})
            return
        if rot in ("section_header", "title"):
            if texto:
                els.append({"tipo": "titulo", "texto": texto, "pagina": pag})
            return
        if rot == "footnote":
            els.append({"tipo": "nota", "texto": texto, "pagina": pag})
            return
        if rot == "formula":
            if cx:
                els.append({"tipo": "imagem", "sub": "formula", "legenda": "", "pagina": pag,
                            "caixa": cx, "chave": None})
            return
        if not texto:
            return
        # Cabeçalho de página marcado como texto comum (o título do livro sozinho na página de
        # abertura de um capítulo). Sem ponto final, a regra do parágrafo partido o emendava
        # ao primeiro parágrafo do capítulo.
        # Fica guardado à parte: num livro, ainda pode ser o único registro do título de um
        # capítulo, e aí o sumário o promove; senão é ignorado na montagem.
        if rot == "text" and so_letras(texto) in chaves_cabecalho:
            cont["cabeçalho marcado como texto"] += 1
            els.append({"tipo": "cabecalho_solto", "texto": texto, "pagina": pag})
            return
        marcador = re.match(r"^(\d{1,3})\.?$", (item.get("marker") or "").strip())
        inicial = re.match(r"^(\d{1,3})\.\s", texto)
        if rot == "list_item" and marcador and parece_nota(item, int(marcador.group(1))):
            els.append({"tipo": "nota", "texto": f"{marcador.group(1)}. {texto}", "pagina": pag})
            cont["nota marcada como lista"] += 1
            return
        if rot == "text" and inicial and parece_nota(item, int(inicial.group(1))):
            els.append({"tipo": "nota", "texto": texto, "pagina": pag})
            cont["nota marcada como texto"] += 1
            return
        els.append({"tipo": "item" if rot == "list_item" else "texto", "texto": texto, "pagina": pag})

    for c in d["body"]["children"]:
        visitar(c["$ref"])
    log("descartados do JSON: " + ", ".join(f"{v} {k}" for k, v in cont.items()))
    # O sumário do livro (document_index) diz quais títulos são capítulos.
    # Só linhas com número de página, na mesma linha ou na seguinte (título que quebrou em
    # duas linhas); a linha só com o autor ("John Goddard") fica de fora.
    sumario = []
    for tb in d.get("tables", []):
        if tb.get("label") != "document_index":
            continue
        linhas = {}
        for c in tb["data"]["table_cells"]:
            linhas.setdefault(c["start_row_offset_idx"], {})[c["start_col_offset_idx"]] = c["text"].strip()
        for r, cols in linhas.items():
            prox = linhas.get(r + 1, {})
            if cols.get(0) and (re.search(r"\d", cols.get(1, "")) or (not prox.get(0) and re.search(r"\d", prox.get(1, "")))):
                sumario.append(ler(cols[0]))
    if sumario:
        log(f"sumário com {len(sumario)} linhas")
    # Cabeçalho corrido que o Docling colou no começo do parágrafo: "O papel da terceira
    # missão em regiões periféricas dinâmicas econômicas..." (cabeçalho + continuação), ou
    # título do livro e do capítulo antes de "Este livro é fruto..." (abertura do capítulo).
    colados = 0
    for e in els:
        if e["tipo"] == "texto":
            novo = tirar_prefixos(e["texto"], cabecalhos | ({titulo} if titulo else set()))
            if novo != e["texto"]:
                e["texto"] = novo
                colados += 1
    if colados:
        log(f"{colados} cabeçalhos corridos colados ao parágrafo retirados")
    return els, sumario, fora_da_faixa


def so_letras(t):
    return re.sub(r"[^a-zà-ÿ]", "", t.lower())


def tirar_prefixos(texto, prefixos, minimo=20):
    """Tira do começo do parágrafo cada prefixo conhecido, comparando só as letras (o PDF
    perde espaços: "visível"do). Repete enquanto achar, e só se sobrarem `minimo` palavras."""
    chaves = sorted({so_letras(p) for p in prefixos if len(so_letras(p)) >= 12}, key=len, reverse=True)
    mudou = True
    while mudou:
        mudou = False
        letras = so_letras(texto)
        for k in chaves:
            if letras.startswith(k):
                n, corte = 0, 0
                for i, ch in enumerate(texto):
                    if re.match(r"[a-zà-ÿ]", ch.lower()):
                        n += 1
                        if n == len(k):
                            corte = i + 1
                            break
                resto = texto[corte:].lstrip(" \"”’:;,.–-")
                if len(resto.split()) >= minimo:
                    texto, mudou = resto, True
                break
    return texto


def promover_capitulos(els, sumario):
    """Título de capítulo que o Docling marcou como texto comum vira título, se bate com o
    sumário. Dois títulos seguidos do mesmo capítulo (curto e completo) ficam no mais longo."""
    # Cada linha do sumário abre um capítulo uma vez só, e na ordem do sumário. Repetição
    # posterior do mesmo título é folha de rosto ou cabeçalho corrido e sai; se vem logo
    # depois do título e é mais completa, substitui o título curto.
    saida, capitulos, repetidos, usado, onde = [], 0, 0, -1, -1
    for e in els:
        if e["tipo"] in ("titulo", "texto", "cabecalho_solto") and (e["tipo"] == "titulo" or len(e["texto"].split()) <= 40):
            j = next((k for k, s in enumerate(sumario) if parecido(e["texto"], s)), None)
            if j is not None and j > usado:
                e = {"tipo": "titulo", "texto": e["texto"], "capitulo": True, "pagina": e.get("pagina")}
                usado, capitulos = j, capitulos + 1
                saida.append(e)
                onde = len(saida) - 1
                continue
            if j is not None:
                repetidos += 1
                if j == usado and len(saida) - onde <= 3 and len(e["texto"]) > len(saida[onde]["texto"]):
                    saida[onde]["texto"] = e["texto"]
                continue
        saida.append(e)
    log(f"sumário: {capitulos} capítulos, {repetidos} repetições de título retiradas")
    return saida


def filtrar(els):
    """Prende "Fonte:" à figura de cima e tira ruído de capa, cabeçalho corrido e sumário."""
    saida, cont = [], Counter()
    for e in els:
        if (e["tipo"] == "texto" and FONTE.match(e["texto"]) and len(e["texto"]) < 400
                and saida and saida[-1]["tipo"] == "imagem" and saida[-1]["sub"] != "formula"):
            saida[-1]["fonte"] = (saida[-1].get("fonte", "") + " " + e["texto"]).strip()
            cont["fonte presa à figura"] += 1
            continue
        saida.append(e)
    curtos = Counter(re.sub(r"\d+", "#", e["texto"]) for e in saida
                     if e["tipo"] == "texto" and len(e["texto"].split()) < 12 and not FONTE.match(e["texto"]))
    corridos = {k for k, v in curtos.items() if v >= 3 and ("#" in k or v >= 5)}
    titulos = Counter(e["texto"] for e in saida if e["tipo"] == "titulo" and len(e["texto"].split()) > 4)
    final = []
    for e in saida:
        t = e.get("texto", "")
        if e["tipo"] in ("texto", "item"):
            if RUIDO_LEITURA.match(t) or LICENCA.search(t):
                cont["metadado de capa ou licença"] += 1
                continue
            if PONTILHADO.search(t):
                cont["linha de sumário"] += 1
                continue
            if e["tipo"] == "texto" and re.sub(r"\d+", "#", t) in corridos:
                cont["cabeçalho corrido"] += 1
                continue
            if not re.search(r"[A-Za-zÀ-ÿ]{2,}", t):
                cont["texto sem palavra"] += 1
                continue
        if e["tipo"] == "titulo" and titulos[t] >= 3:
            cont["título repetido (cabeçalho corrido)"] += 1
            continue
        final.append(e)
    log("filtrados: " + ", ".join(f"{v} {k}" for k, v in cont.items()))
    return final


def cortar_capa(els, titulo):
    """Artigo baixado de revista vem com folha de rosto da editora antes da primeira página,
    e o título aparece duas vezes. Tudo antes da última repetição do título, no começo, sai."""
    idx = [i for i, e in enumerate(els[:40]) if e["tipo"] == "titulo" and parecido(e["texto"], titulo)]
    if not idx:
        return els
    # Só corta até uma repetição se não houver parágrafo de verdade antes dela; senão a
    # repetição é cabeçalho de página e o corte levaria o começo do texto junto.
    corte = idx[0]
    for i in idx[1:]:
        if any(e["tipo"] == "texto" and len(e["texto"].split()) >= 40 for e in els[corte:i]):
            break
        corte = i
    log(f"capa: {corte} elementos antes do título descartados")
    return els[corte + 1:]


# ---------------------------------------------------------------- montagem

def niveis(els, titulo, livro, sumario):
    """Nível de cada título e capítulo de cada elemento.

    Livro com sumário: capítulo é o título que bate com uma linha do sumário. Sem sumário,
    o primeiro título sem número depois de "Referências" abre capítulo."""
    cap, em_ref, tem_cap, primeiro = 0, False, False, True
    for e in els:
        if e["tipo"] == "titulo":
            t = e["texto"]
            if not livro and primeiro and parecido(t, titulo):
                e["descartar"] = True
            elif livro and sumario and re.match(r"^(sumário|índice|contents)$", t, re.IGNORECASE):
                e["descartar"] = True
            elif e.get("capitulo"):
                e["nivel"] = 1
            elif FIM_DE_LEITURA.match(t):
                e["nivel"] = 2
                em_ref = True
            elif SUBSECAO.match(t):
                e["nivel"] = 3
            elif livro and not sumario and (em_ref or not tem_cap):
                e["nivel"] = 1
            else:
                e["nivel"] = 2
            if e.get("nivel") == 1:
                cap, tem_cap, em_ref = cap + 1, True, False
            primeiro = False
        e["cap"] = cap
    return cap


def montar(els, titulo, livro, sumario):
    capitulos = niveis(els, titulo, livro, sumario)
    imagens, citadas = {}, set()
    for e in els:
        if e["tipo"] == "imagem" and e["chave"]:
            imagens.setdefault((e["cap"],) + e["chave"], []).append(e)
        if e["tipo"] in ("texto", "item"):
            for m in MENCAO.finditer(e["texto"]):
                for n in numeros_citados(m.group(2)):
                    citadas.add((e["cap"], familia(m.group(1)), n))

    out, notas, pend, colocadas, posicoes = [], [], [], set(), []

    def bloco(kind, cap, texto="", el=None):
        out.append({"kind": kind, "cap": cap, "text": texto, "el": el})

    def ultimo_aberto():
        return out and out[-1]["kind"] == "para" and not FECHA_FRASE.search(out[-1]["text"])

    def descarregar():
        for el in pend:
            bloco("img", el["cap"], el=el)
            ancora = next((o["text"] for o in reversed(out[:-1]) if o["kind"] in ("para", "item")), "")
            posicoes.append((el, ancora[-90:]))
        pend.clear()

    def anunciar(chave):
        if chave in colocadas or chave not in imagens:
            return
        colocadas.add(chave)
        pend.extend(imagens[chave])

    for e in els:
        if e.get("descartar"):
            continue
        tipo, cap = e["tipo"], e["cap"]
        if tipo == "titulo":
            descarregar()
            bloco("head", cap, e["texto"], e)
        elif tipo == "texto":
            t = e["texto"]
            # Parágrafo partido na virada de página. Além da continuação em minúscula, emenda
            # quando o anterior para numa palavra minúscula ("fundador e reitor da" | "Universidade de...").
            if ultimo_aberto() and (t[:1].islower() or re.search(r"\b[a-zà-ÿ]+$", out[-1]["text"])):
                out[-1]["text"] += " " + t
            else:
                bloco("para", cap, t)
            for m in MENCAO.finditer(t):
                for n in numeros_citados(m.group(2)):
                    anunciar((cap, familia(m.group(1)), n))
            if FECHA_FRASE.search(out[-1]["text"]):
                descarregar()
        elif tipo == "item":
            bloco("item", cap, e["texto"])
            for m in MENCAO.finditer(e["texto"]):
                for n in numeros_citados(m.group(2)):
                    anunciar((cap, familia(m.group(1)), n))
            descarregar()
        elif tipo == "legenda_solta":
            bloco("legenda", cap, e["texto"])
        elif tipo == "nota":
            m = re.match(r"^(\d{1,3})\s*[.)]?\s+(.*)$", e["texto"])
            notas.append({"cap": cap, "n": int(m.group(1)) if m else None,
                          "texto": m.group(2) if m else e["texto"], "ate": len(out)})
        elif tipo == "imagem":
            chave = (cap,) + e["chave"] if e["chave"] else None
            if e["sub"] == "formula":
                bloco("img", cap, el=e)       # fórmula fica no fluxo, entre parágrafos
            elif chave and chave in citadas:
                continue                      # entra no parágrafo que a cita
            else:
                pend.append(e)                # nunca citada: fica onde está
                if not ultimo_aberto():
                    descarregar()
    descarregar()
    sobras = [k for k in imagens if k not in colocadas and k in citadas]
    for k in sobras:
        pend.extend(imagens[k])
    descarregar()
    if sobras:
        log(f"AVISO: {len(sobras)} figuras citadas não colocadas, foram para o fim: {sobras}")

    casadas, soltas = casar_notas(out, notas)
    log(f"{capitulos} capítulos; {sum(1 for o in out if o['kind'] == 'para')} parágrafos; "
        f"{sum(1 for o in out if o['kind'] == 'img')} imagens; notas: {casadas} casadas, {soltas} no fim do parágrafo")
    return out, notas, posicoes


def casar_notas(out, notas):
    casadas = soltas = 0
    pos = {}   # capítulo -> (índice em out, deslocamento) da última nota casada
    usados = Counter()
    for nota in notas:
        cap = nota["cap"]
        base = f"c{cap}n{nota['n'] if nota['n'] is not None else 'x'}"
        usados[base] += 1
        nota["id"] = base if usados[base] == 1 else f"{base}-{usados[base]}"
        sentinela = f"\x00{nota['id']}\x00"
        paras = [i for i, o in enumerate(out) if o["cap"] == cap and o["kind"] in ("para", "item", "head")]
        ini, desl = pos.get(cap, (-1, 0))
        limite = [i for i in paras if i < nota["ate"]]
        teto = (limite[-1] if limite else -1)
        candidatos = [i for i in paras if i >= ini and (i <= teto or i in paras[len(limite):len(limite) + 2])]
        achou = False
        if nota["n"] is not None:
            n = nota["n"]
            # Primeiro o número colado ("Becker18"); depois o separado por espaço ("Mincer 16"),
            # que o PDF também produz, desde que a palavra anterior não indique quantidade
            # ("de 12 117 clientes") nem seja rótulo ("Tabela 1").
            # Número com milhar ou decimal ("2.890 turmas") e fim de intervalo ("entre 0 e 1",
            # "de 1 a 5") não são chamada de nota: falsos positivos de um livro de teste.
            colado = re.compile(rf"(?<=[A-Za-zÀ-ÿ.,;:)\"”’]){n}(?!\d|[.,]\d)")
            espaco = re.compile(rf"(?<=[A-Za-zÀ-ÿ.,;:)\"”’]) {n}(?=[\s,;:)]|\.(?!\d)|$)")
            for pat in (colado, espaco):
                for i in candidatos:
                    texto = out[i]["text"]
                    for m in pat.finditer(texto, desl if i == ini else 0):
                        if re.search(r"\d\s+(e|a|até|ou|and|to|or)\s?$", texto[:m.start()]):
                            continue
                        if pat is espaco:
                            antes = re.findall(r"[\wÀ-ÿ]+", texto[:m.start()])[-1:] or [""]
                            if antes[0].lower() in QUANTIDADE:
                                continue
                        out[i]["text"] = texto[:m.start()] + sentinela + texto[m.end():]
                        pos[cap] = (i, m.start() + len(sentinela))
                        achou = True
                        break
                    if achou:
                        break
                if achou:
                    break
        if achou:
            casadas += 1
        else:
            alvo = teto if teto >= 0 else (paras[0] if paras else None)
            if alvo is not None:
                out[alvo]["text"] += sentinela
            soltas += 1
    return casadas, soltas


# ---------------------------------------------------------------- recorte e saída

class Recortador:
    def __init__(self, pdf, pasta):
        import pypdfium2 as pdfium
        self.doc = pdfium.PdfDocument(str(pdf))
        self.pasta = pasta
        self.cache = OrderedDict()
        self.baixa = {}
        self.n = Counter()
        pasta.mkdir(parents=True, exist_ok=True)

    def pagina(self, pg):
        if pg not in self.cache:
            p = self.doc[pg - 1]
            self.cache[pg] = (p.render(scale=3).to_pil(), p.get_size())
            if len(self.cache) > 6:
                self.cache.popitem(last=False)
        return self.cache[pg]

    def recortar(self, el):
        img, (w, h) = self.pagina(el["pagina"])
        l, t, r, b, origem = el["caixa"]
        if origem == "BOTTOMLEFT":
            topo, base = h - max(t, b), h - min(t, b)
        else:
            topo, base = min(t, b), max(t, b)
        f = 4
        rec = img.crop((max(0, int((l - f) * 3)), max(0, int((topo - f) * 3)),
                        min(img.width, int((r + f) * 3)), min(img.height, int((base + f) * 3))))
        if rec.width > 1400:
            rec.thumbnail((1400, 10000))
        if el["chave"]:
            nome = f"c{el['cap']:02d}-{el['chave'][0]}-{el['chave'][1]:02d}"
        else:
            self.n[el["sub"]] += 1
            nome = f"c{el['cap']:02d}-{el['sub']}-{self.n[el['sub']]:03d}"
        # PNG com paleta de 256 cores para tabela, gráfico e fórmula (texto nítido); JPEG
        # quando sai bem menor, que é o caso de foto. O PNG cheio deixava o livro com 31 MB.
        rgb = rec.convert("RGB")
        png, jpg = io.BytesIO(), io.BytesIO()
        rgb.quantize(colors=256).save(png, "PNG", optimize=True)
        rgb.save(jpg, "JPEG", quality=82)
        ext, dados = ("png", png) if png.tell() <= 1.3 * jpg.tell() else ("jpg", jpg)
        arq = self.pasta / f"{nome}.{ext}"
        arq.write_bytes(dados.getvalue())
        pct = max(15, min(100, round(abs(r - l) / (w * 0.72) * 100)))
        return f"imagens/{arq.name}", pct

    def assinatura(self, el):
        """Hash médio 16x16 do recorte, para achar a mesma arte repetida pelo livro. Usa a
        página em escala 1, que basta para o hash e não pesa quando o livro inteiro entra."""
        pg = el["pagina"]
        if pg not in self.baixa:
            p = self.doc[pg - 1]
            self.baixa[pg] = (p.render(scale=1).to_pil(), p.get_size())
        img, (w, h) = self.baixa[pg]
        l, t, r, b, origem = el["caixa"]
        topo, base = (h - max(t, b), h - min(t, b)) if origem == "BOTTOMLEFT" else (min(t, b), max(t, b))
        rec = img.crop((int(l), int(topo), int(r), int(base))).convert("L").resize((16, 16))
        px = list(rec.tobytes())
        media = sum(px) / len(px)
        return [p > media for p in px]

    def capa(self, destino, pagina=1):
        self.doc[pagina - 1].render(scale=2).to_pil().convert("RGB").save(destino, "JPEG", quality=85)


def decorativas(out, recortador, extras=()):
    """Imagem sem legenda que se repete três vezes ou mais (arte de abertura de capítulo).
    Num capítulo tirado de um livro, compara também com as imagens do resto do livro."""
    soltas = [o["el"] for o in out if o["kind"] == "img" and o["el"]["sub"] == "picture" and not o["el"]["chave"]]
    hashes = [recortador.assinatura(el) for el in soltas]
    todas = hashes + [recortador.assinatura(el) for el in extras]
    fora = set()
    for i, hi in enumerate(hashes):
        iguais = [j for j, hj in enumerate(todas) if sum(a != b for a, b in zip(hi, hj)) <= 20]
        if len(iguais) >= 3:
            fora.add(id(soltas[i]))
    log(f"{len(fora)} imagens decorativas repetidas retiradas")
    return fora


def escrever_md(out, notas, recortador, extras=()):
    partes = []
    fora = decorativas(out, recortador, extras)
    for o in out:
        if o["kind"] == "img" and id(o["el"]) in fora:
            continue
        k = o["kind"]
        if k == "head":
            partes.append("#" * o["el"]["nivel"] + " " + md(o["text"]))
        elif k == "para":
            partes.append(md(o["text"]))
        elif k == "item":
            partes.append("- " + md(o["text"]))
        elif k == "legenda":
            partes.append("*" + md(o["text"]) + "*")
        elif k == "img":
            el = o["el"]
            caminho, pct = recortador.recortar(el)
            leg = " ".join(x for x in (el.get("legenda", ""), el.get("fonte", "")) if x)
            partes.append(f"![{md(leg)}]({caminho}){{width={pct}%}}")
    for nota in notas:
        partes.append(f"[^{nota['id']}]: {md(nota['texto'])}")
    return "\n\n".join(partes) + "\n"


def titular_notas(epub, titulo):
    """O Pandoc põe as notas no fim do capítulo separadas só por uma linha, sem título e sem
    número. No Kindle o bloco parecia a bibliografia continuando fora de ordem (leitura de
    05/10/2026). Aqui o bloco ganha título e cada nota mostra o número, com volta ao texto."""
    import zipfile
    tmp = epub.with_suffix(".tmp")
    tituladas = 0
    with zipfile.ZipFile(epub) as zin, zipfile.ZipFile(tmp, "w") as zout:
        for info in zin.infolist():
            dados = zin.read(info.filename)
            if info.filename.endswith(".xhtml") and b'epub:type="footnotes"' in dados:
                x = dados.decode("utf-8")
                x = re.sub(r'(<section id="footnotes"[^>]*>)\s*<hr\s*/>',
                           rf'\1\n<h2 class="titulo-notas">{titulo}</h2>', x)
                x = re.sub(r'(<aside epub:type="footnote"[^>]*id="fn(\d+)"[^>]*>\s*<p>)',
                           r'\1<a href="#fnref\2" class="volta-nota">\2.</a> ', x)
                dados = x.encode("utf-8")
                tituladas += 1
            # o mimetype vai primeiro e sem compressão, como pede o formato
            tipo = zipfile.ZIP_STORED if info.filename == "mimetype" else zipfile.ZIP_DEFLATED
            zout.writestr(info.filename, dados, compress_type=tipo)
    tmp.replace(epub)
    log(f"bloco de notas com título em {tituladas} arquivos do EPUB")


CSS = """.titulo-notas { margin-top: 2em; }
.volta-nota { font-weight: bold; text-decoration: none; }
figure { margin: 1.2em 0; text-align: center; page-break-inside: avoid; }
figure img { max-width: 100%; }
figcaption { font-size: 0.85em; font-style: italic; margin-top: 0.4em; text-align: left; }
"""


def listar_capitulos(arq_json):
    """Capítulos do livro, pelo sumário, com a faixa de páginas do PDF que --paginas usa."""
    els, sumario, _ = elementos_do_json(arq_json)
    if not sumario:
        print("o livro não tem sumário reconhecido; procure as páginas do capítulo no PDF")
        return
    caps = [e for e in promover_capitulos(filtrar(els), sumario) if e.get("capitulo")]
    total = len(json.loads(Path(arq_json).read_text(encoding="utf-8")).get("pages", {}))
    for i, e in enumerate(caps):
        ini = e.get("pagina") or 0
        fim = (caps[i + 1].get("pagina") or ini + 1) - 1 if i + 1 < len(caps) else total
        print(f"--paginas {ini}-{fim}\t{e['texto']}")


def achar_extracao(entrada, trab):
    """JSON do Docling para este PDF: o da própria obra ou o de outra obra feita do mesmo
    PDF (capítulo tirado de um livro já extraído inteiro). Só vale se for mais novo que o PDF."""
    candidatos = [trab / f"{entrada.stem}.json"]
    candidatos += sorted((RAIZ / ".trabalho").glob(f"*/{glob.escape(entrada.stem)}.json"))
    for c in candidatos:
        if c.exists() and c.stat().st_mtime >= entrada.stat().st_mtime:
            return c
    return None


def main():
    ap = argparse.ArgumentParser(description="PDF para EPUB, para ler no Kindle.")
    ap.add_argument("entrada", help="arquivo .pdf")
    ap.add_argument("--titulo", help="padrão: nome do arquivo")
    ap.add_argument("--autor", default="")
    ap.add_argument("--lingua", choices=["en", "pt"], default="en", help="língua do texto (padrão: en)")
    ap.add_argument("--saida", help="pasta onde cada obra ganha uma subpasta "
                    "(padrão: BOOK_TO_AUDIO_SAIDA no ambiente ou em ~/.claude/.env, senão saida/ no projeto)")
    ap.add_argument("--nome", help="nome do EPUB e da pasta da obra, sem extensão (padrão: nome do arquivo)")
    ap.add_argument("--livro", action="store_true",
                    help="livro inteiro: capítulos pelo sumário, figuras numeradas por capítulo")
    ap.add_argument("--paginas", help="faixa de páginas do PDF, por exemplo 33-54, para um capítulo de livro")
    ap.add_argument("--capitulos", action="store_true",
                    help="lista os capítulos do livro, pelo sumário, com a faixa de páginas do PDF, e sai")
    a = ap.parse_args()

    entrada = Path(a.entrada).expanduser()
    if not entrada.exists() or entrada.suffix.lower() != ".pdf":
        ap.error(f"informe um PDF que exista: {entrada}")
    if not shutil.which("pandoc"):
        ap.error("o Pandoc não está instalado (brew install pandoc)")
    faixa = tuple(int(x) for x in a.paginas.split("-")) if a.paginas else None
    if faixa and a.livro:
        ap.error("--paginas é para um capítulo; não combina com --livro")
    a.titulo = a.titulo or entrada.stem
    a.nome = a.nome or entrada.stem

    # Mesma convenção do gerar_audio.py: a obra na pasta de saída, o intermediário em .trabalho/.
    obra = RAIZ / ".trabalho" / a.nome
    obra.mkdir(parents=True, exist_ok=True)
    arq_json = achar_extracao(entrada, obra)
    if arq_json:
        log(f"extração já feita antes para este arquivo; reaproveitando ({arq_json.parent.name})")
    else:
        arq_json, arq_md = extrair_pdf(entrada, obra)
        conferir_extracao(arq_md.read_text(encoding="utf-8"))
    if a.capitulos:
        listar_capitulos(arq_json)
        return
    saida = (Path(a.saida).expanduser() if a.saida else resolver_pasta(RAIZ)[0]) / a.nome
    saida.mkdir(parents=True, exist_ok=True)
    trab = obra / (f"kindle-p{faixa[0]}-{faixa[1]}" if faixa else "kindle")
    trab.mkdir(exist_ok=True)
    a.pdf = entrada
    log(f"saída em {saida}")

    els, sumario, fora_da_faixa = elementos_do_json(arq_json, faixa, a.titulo)
    els = filtrar(els)
    if not a.livro:
        els = cortar_capa(els, a.titulo)
    elif sumario:
        els = promover_capitulos(els, sumario)
    out, notas, posicoes = montar(els, a.titulo, a.livro, sumario)
    if (trab / "imagens").exists():
        for f in (trab / "imagens").iterdir():
            f.unlink()
    recortador = Recortador(a.pdf, trab / "imagens")
    recortador.capa(trab / "capa.jpg", faixa[0] if faixa else 1)
    texto = escrever_md(out, notas, recortador, fora_da_faixa)
    (trab / "texto.md").write_text(texto, encoding="utf-8")
    (trab / "estilo.css").write_text(CSS, encoding="utf-8")
    linhas = []
    for el, ancora in posicoes:
        rotulo = f"{el['chave'][0]} {el['chave'][1]}" if el["chave"] else f"{el['sub']} sem legenda"
        linhas.append(f"cap {el['cap']:>2} | p. {el['pagina']:>3} | {rotulo:<16} | depois de: ...{ancora}")
    (trab / "posicoes.txt").write_text("\n".join(linhas) + "\n", encoding="utf-8")

    saida = saida / f"{a.nome}.epub"
    cmd = ["pandoc", "texto.md", "-f", "markdown-citations-tex_math_dollars-raw_tex-raw_html-superscript-subscript-smart",
           "-o", str(saida.resolve()), "--metadata", f"title={a.titulo}", "--metadata",
           f"lang={'pt-BR' if a.lingua == 'pt' else 'en'}", "--toc", "--toc-depth=2", "--split-level=1",
           "--css", "estilo.css", "--epub-cover-image", "capa.jpg"]
    if a.autor:
        cmd += ["--metadata", f"author={a.autor}"]
    r = subprocess.run(cmd, cwd=trab, capture_output=True, text=True)
    if r.returncode != 0:
        log(f"ERRO no pandoc: {r.stderr}")
        sys.exit(1)
    if r.stderr.strip():
        log(f"pandoc avisou: {r.stderr.strip()[:800]}")
    titular_notas(saida, "Notas" if a.lingua == "pt" else "Notes")
    log(f"EPUB: {saida} ({saida.stat().st_size / 1e6:.1f} MB); posições em {trab / 'posicoes.txt'}")


if __name__ == "__main__":
    main()
