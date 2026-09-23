#!/usr/bin/env python3
"""book-to-audio 0.1.0 — PDF para MP3 com capítulos.

Fluxo: PDF -> Docling (texto limpo em Markdown) -> roteiro (o que se fala, por
capítulo) -> voz do Kokoro (ou do `say` do macOS) -> MP3 com capítulos ID3v2
gravados pelo ffmpeg.

Uso:
    uv run gerar_audio.py documento.pdf --lingua en
    uv run gerar_audio.py documento.pdf --lingua pt --titulo "..." --autor "..."

Também aceita um .md já extraído pelo Docling no lugar do PDF.
"""
import argparse
import html
import re
import subprocess
import sys
from pathlib import Path

# Seções em que a leitura para. Tudo que vem depois fica fora do áudio.
FIM_DE_LEITURA = re.compile(
    r"^(references|referências|referencias|bibliography|bibliografia|notes|notas|"
    r"disclosure statement|funding|orcid|acknowledg(e)?ments?|agradecimentos)\b",
    re.IGNORECASE,
)
# Título de seção numerada ("1 Introdução", "2. Literature review") abre capítulo novo.
SECAO_NUMERADA = re.compile(r"^\d+(\.\d+)*\.?\s+\S")
# Citação autor-ano entre parênteses: "(Martin & Sunley, 2022; Zhu et al., 2019)".
CITACAO_PARENTESES = re.compile(r"\s*\([^()]*\b(1[89]|20)\d{2}[a-z]?\b[^()]*\)")
# Ano solto depois do nome: "Schumpeter (1934)" vira "Schumpeter".
ANO_ENTRE_PARENTESES = re.compile(r"\s*\((1[89]|20)\d{2}[a-z]?(,\s*p+\.\s*[\d–-]+)?\)")

PAUSA_SUBTITULO = "[[slnc 700]]"
PAUSA_CAPITULO = "[[slnc 1200]]"


def log(msg):
    print(f"[gerar_audio] {msg}", flush=True)


def limpar(texto):
    texto = html.unescape(texto)
    texto = CITACAO_PARENTESES.sub("", texto)
    texto = ANO_ENTRE_PARENTESES.sub("", texto)
    texto = re.sub(r"\s+([,.;:])", r"\1", texto)
    texto = re.sub(r"\s{2,}", " ", texto)
    return texto.strip()


def montar_roteiro(md, titulo, autor):
    """Devolve lista de (título do capítulo, texto falado)."""
    abertura = f"{titulo}. {autor}." if autor else f"{titulo}."
    capitulos = [["Abertura", [abertura, PAUSA_CAPITULO]]]
    primeiro_titulo_visto = False
    descartadas = []

    for linha in md.splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("![") or linha.startswith("<!--"):
            continue
        if linha.startswith("#"):
            cabecalho = limpar(linha.lstrip("#").strip())
            if FIM_DE_LEITURA.match(cabecalho):
                log(f"fim da leitura na seção '{cabecalho}'")
                break
            if not primeiro_titulo_visto:
                # O primeiro título do Docling é o título do documento, já anunciado.
                primeiro_titulo_visto = True
                continue
            if SECAO_NUMERADA.match(cabecalho):
                nome = re.sub(r"^\d+(\.\d+)*\.?\s+", "", cabecalho)
                capitulos.append([nome, [f"{nome}.", PAUSA_CAPITULO]])
            else:
                capitulos[-1][1] += [PAUSA_SUBTITULO, f"{cabecalho}.", PAUSA_SUBTITULO]
            continue
        if not primeiro_titulo_visto:
            descartadas.append(linha)
            continue
        if linha == autor or linha.startswith("Abstract "):
            linha = re.sub(r"^Abstract\s+", "Abstract. ", linha)
        capitulos[-1][1].append(limpar(linha))

    if descartadas:
        log(f"{len(descartadas)} linhas antes do título descartadas")
    return [(nome, "\n".join(partes)) for nome, partes in capitulos]


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

    Precisa rodar com o Python do ambiente que tem kokoro-onnx e soundfile.
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
    blocos = []
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha:
            continue
        pausa = re.fullmatch(r"\[\[slnc (\d+)\]\]", linha)
        if pausa:
            blocos.append(np.zeros(int(sr * int(pausa.group(1)) / 1000), dtype=np.float32))
            continue
        amostras, sr = _kokoro.create(linha, voice=voz, speed=1.0, lang=lingua)
        blocos += [amostras.astype(np.float32), np.zeros(int(sr * 0.35), dtype=np.float32)]
    sf.write(str(wav), np.concatenate(blocos), sr)


def extrair_pdf(pdf, trab):
    """PDF -> Markdown pelo Docling, com o leitor pypdfium2.

    O leitor padrão do Docling corrompeu um artigo de revista com fontes Type 1C
    (letras sumidas, palavras grudadas); o pypdfium2 leu o mesmo arquivo sem erro.
    """
    docling = Path(sys.executable).parent / "docling"
    if not docling.exists():
        docling = "docling"
    log(f"extraindo {pdf.name} com o Docling (pode levar alguns minutos)")
    rodar([str(docling), str(pdf), "--pdf-backend", "pypdfium2", "--to", "md",
           "--image-export-mode", "placeholder", "--output", str(trab)])
    return trab / f"{pdf.stem}.md"


def conferir_extracao(md):
    """Palavras com 22 letras ou mais indicam espaços perdidos na extração."""
    suspeitas = re.findall(r"[A-Za-zÀ-ÿ]{22,}", md)
    if len(suspeitas) > 5:
        log(f"ATENÇÃO: {len(suspeitas)} palavras anormalmente longas, a extração pode ter "
            f"perdido espaços. Exemplos: {', '.join(suspeitas[:3])}")
    else:
        log(f"conferência da extração: ok ({len(suspeitas)} palavras suspeitas)")


def main():
    raiz = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description="PDF para MP3 com capítulos.")
    ap.add_argument("entrada", help="arquivo .pdf, ou .md já extraído pelo Docling")
    ap.add_argument("--lingua", choices=["en", "pt"], default="en", help="língua do texto (padrão: en)")
    ap.add_argument("--titulo", help="padrão: nome do arquivo")
    ap.add_argument("--autor", default="")
    ap.add_argument("--motor", choices=["say", "kokoro"], default="kokoro")
    ap.add_argument("--voz", help="padrão: af_heart (en) ou pf_dora (pt) no Kokoro; Samantha ou Luciana no say")
    ap.add_argument("--modelos", default=str(raiz / "modelos"),
                    help="pasta com kokoro-v1.0.onnx e voices-v1.0.bin (padrão: modelos/)")
    ap.add_argument("--velocidade", type=int, default=185, help="palavras por minuto do say")
    ap.add_argument("--saida", default="saida", help="pasta de saída (padrão: saida/)")
    ap.add_argument("--nome", help="nome do MP3, sem extensão (padrão: nome do arquivo de entrada)")
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

    saida = Path(a.saida)
    trab = saida / "trabalho" / a.nome
    trab.mkdir(parents=True, exist_ok=True)

    arquivo_md = extrair_pdf(entrada, trab) if entrada.suffix.lower() == ".pdf" else entrada
    md = arquivo_md.read_text(encoding="utf-8")
    conferir_extracao(md)
    capitulos = montar_roteiro(md, a.titulo, a.autor)

    # Roteiro legível, para conferir o que vai ser falado.
    roteiro = saida / f"{a.nome}-roteiro.txt"
    with roteiro.open("w", encoding="utf-8") as f:
        for i, (nome, texto) in enumerate(capitulos):
            palavras = len(re.sub(r"\[\[.*?\]\]", "", texto).split())
            f.write(f"===== Capítulo {i}: {nome} ({palavras} palavras)\n\n")
            f.write(re.sub(r"\[\[.*?\]\]\n?", "", texto) + "\n\n")
            log(f"capítulo {i}: {nome} — {palavras} palavras")
    log(f"roteiro gravado em {roteiro}")

    wavs, meta = [], [";FFMETADATA1", f"title={a.titulo}", f"artist={a.autor}",
                      f"album={a.titulo}", "genre=Audiobook"]
    inicio = 0
    for i, (nome, texto) in enumerate(capitulos):
        txt = trab / f"cap{i:02d}.txt"
        aiff = trab / f"cap{i:02d}.aiff"
        wav = trab / f"cap{i:02d}.wav"
        txt.write_text(texto, encoding="utf-8")
        log(f"sintetizando capítulo {i} com a voz {a.voz}")
        if a.motor == "say":
            rodar(["say", "-v", a.voz, "-r", str(a.velocidade), "-o", str(aiff), "-f", str(txt)])
            rodar(["ffmpeg", "-v", "error", "-y", "-i", str(aiff), "-ar", "44100", "-ac", "1", str(wav)])
        else:
            sintetizar_kokoro(texto, wav, a.voz, "en-us" if a.lingua == "en" else "pt-br", a.modelos)
        d = duracao_ms(wav)
        meta += ["[CHAPTER]", "TIMEBASE=1/1000", f"START={inicio}", f"END={inicio + d}",
                 f"title={nome}"]
        inicio += d
        wavs.append(wav)

    lista = trab / "lista.txt"
    lista.write_text("".join(f"file '{w.resolve()}'\n" for w in wavs), encoding="utf-8")
    metaf = trab / "capitulos.txt"
    metaf.write_text("\n".join(meta) + "\n", encoding="utf-8")

    mp3 = saida / f"{a.nome}.mp3"
    rodar(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lista),
           "-i", str(metaf), "-map_metadata", "1", "-map", "0:a", "-c:a", "libmp3lame",
           "-b:a", "64k", "-id3v2_version", "3", str(mp3)])
    caps = rodar(["ffprobe", "-v", "error", "-show_chapters", "-of", "csv=p=0", str(mp3)])
    log(f"MP3 pronto: {mp3} — {inicio / 60000:.1f} min, {len(caps.strip().splitlines())} capítulos")


if __name__ == "__main__":
    main()
