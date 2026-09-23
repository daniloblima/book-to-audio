# CHANGELOG - book-to-audio

> Este arquivo registra todos os problemas, bugs, decisões técnicas e soluções encontradas durante o desenvolvimento. Consultado obrigatoriamente após cada compactação de contexto.

---

## Versões

O projeto segue versionamento semântico (MAIOR.MENOR.CORREÇÃO). As entradas datadas abaixo são o diário técnico de cada sessão, na ordem em que aconteceram. As entradas de versão resumem o que cada release entrega.

## [0.1.0] - 2026-09-23 (10:58)

Primeira versão utilizável. PDF para MP3 com capítulos, em um comando.

- Extração de PDF pelo Docling com o leitor pypdfium2, chamada pelo próprio `gerar_audio.py`. Conferência automática de palavras grudadas na saída.
- Roteiro: abertura com título, autor e resumo. Um capítulo por seção numerada, subtítulos com pausa, citações autor-ano removidas, imagens ignoradas e leitura interrompida na seção de referências.
- Voz: Kokoro-82M via kokoro-onnx, `af_heart` em inglês e `pf_dora` em português. O `say` do macOS fica como alternativa (`--motor say`).
- MP3 64 kbps mono com capítulos ID3v2 (CHAP/CTOC) pelo ffmpeg. Validado no Podcast Addict (Android): capítulos visíveis e posição de escuta mantida.
- Instalação reprodutível: `pyproject.toml` e `uv.lock` (Python 3.12), `baixar_modelos.sh` com conferência SHA-256, `README.md` com o passo a passo.
- Testada do zero num clone limpo: download dos modelos, `uv sync` e conversão do PDF até o MP3.

---

## [2026-09-23] - Abertura do projeto

### OBJETIVO
Converter documentos (PDF, DOCX, EPUB, AZW3 sem DRM) em MP3 para ouvir no Podcast Addict, na pasta de arquivos locais que o autor já usa para reuniões e áudios do YouTube. O player guarda onde ele parou, que é o motivo de usar um tocador de podcast em vez de um player comum. Capítulos, se o formato e o player permitirem.

### DECISÕES DE PARTIDA
- Formato de entrega: MP3, que é o que ele já usa no Podcast Addict. Outro formato só se a pesquisa mostrar ganho claro (capítulos, por exemplo).
- Dois motores de voz, um para português e um para inglês. Ele lê nas duas línguas.
- Tudo gratuito na primeira versão, de preferência local no Mac. Naturalidade da voz fica para depois: o motor é peça trocável e independente da preparação do texto. Hugging Face hospedado já se mostrou difícil de usar em experiência anterior dele (voz para texto), por isso a preferência é por modelo local não muito grande.
- O desafio central é a preparação do texto, não a síntese: tirar cabeçalho, rodapé e número de página, tratar notas, figuras, tabelas, caixas de texto e artigos em duas colunas.
- Figuras: ideia inicial dele é extrair as imagens para uma pasta acessível pelo celular (numa nuvem) e o áudio mencionar a figura, como artigos que deixam as figuras no anexo. A decidir depois da pesquisa.
- AZW3 da Amazon vem com DRM. O projeto trata só arquivos sem proteção.
- Pasta nomeada `book-to-audio` (sem espaços) em vez de "Book to Audio", porque espaço em caminho quebra comandos de terminal.

### PRÓXIMO PASSO
Pesquisa em cinco frentes antes de escrever código. Ver `00_INDICE_book-to-audio.md`.

---

## [2026-09-23] - Pesquisa de ferramentas e dois testes locais

### OBJETIVO
Levantar o que já existe antes de construir. Cinco frentes em sessões separadas (`claude -p`), das 09:36 às 09:47. Consolidação em `01-pesquisa-ferramentas.md`.

### RESULTADO DA PESQUISA
Nenhuma ferramenta pronta resolve PDF acadêmico: todas as ferramentas ponta a ponta usam PyMuPDF em extração simples (issue #16 do abogen aberta desde 05/2025). Arquitetura que emerge: extração (MinerU/Docling/GROBID para PDF; Calibre e pandoc para EPUB, AZW3, DOCX) → roteiro de leitura (trabalho original do projeto) → voz (Kokoro PT/EN, `say` como reserva) → MP3 com capítulos (ffmpeg).

### TESTE 1 — ffmpeg grava capítulos ID3v2 em MP3
Hipótese vinda da leitura do código-fonte do ffmpeg, não testada pela sessão de pesquisa. Teste: dois trechos com `say`, concatenados em MP3, metadados em formato FFMETADATA com dois blocos `[CHAPTER]` (TIMEBASE=1/1000), gravados com `ffmpeg -i entrada.mp3 -i meta.txt -map_metadata 1 -id3v2_version 3 -c copy saida.mp3`. Resultado: `ffprobe -show_chapters` devolveu os dois capítulos com título acentuado e tempos certos; leitura direta dos bytes encontrou CTOC e dois CHAP. Confirmado. Falta testar no Podcast Addict do celular.

### TESTE 2 — vozes do `say` instaladas
`say -v '?'` lista nove vozes pt_BR: Luciana, Eddy, Flo, Grandma, Grandpa, Reed, Rocko, Sandy, Shelley. Nenhuma Enhanced ou Premium baixada. Felipe, citado na pesquisa, não está instalado. Luciana gerou AIFF sem erro. `say` grava AIFF, então a saída passa pelo ffmpeg para virar MP3.

### LIÇÕES
- Sessões `claude -p` de pesquisa não conseguem rodar comando local nem acessar o Reddit. O que depende de execução na máquina precisa ser conferido depois, na sessão principal.
- A dica do Reddit sobre Acrobat PDF→HTML não se confirmou: a exportação depende de PDF marcado e a comunidade da Adobe a desaconselha para duas colunas. A peça útil da Adobe é a PDF Extract API (2.500 páginas/mês grátis), reserva para PDF que os extratores abertos estragarem.

---

## [2026-09-23] - Conjunto de teste e decisões de roteiro (10:09)

### DECISÕES DO DANILO
- Nota de rodapé lida no próximo ponto final após a chamada, como parêntese com pausa.
- MP3 único por documento; acima de 3h, partes de no máximo 3h (ele prefere menores, tamanho a definir).
- Pasta de figuras acompanha cada audiolivro gerado.
- Bibliografia sai. Regra do que entra e sai do roteiro (sumário, índices, listas) a desenhar na etapa 2.

### DESCOBERTAS
- Calibre está instalado como app (`/Applications/calibre.app`), mas o `ebook-convert` não está no PATH. Caminho: `/Applications/calibre.app/Contents/MacOS/ebook-convert`.
- AZW3 do Running Lean converte para EPUB sem erro, sem DRM.
- KFX, formato atual da Amazon e o mais comum numa biblioteca do Calibre alimentada pelo Kindle, fica fora do escopo.
- pandoc já instalado em `/opt/homebrew/bin/pandoc`.
- Os documentos de teste são lidos da pasta de origem e copiados para uma pasta temporária. O projeto nunca escreve na pasta de origem.

---

## [2026-09-23] - Instalação dos extratores (10:13)

### SOLUÇÃO
- `uv tool install --python 3.12 docling` e `uv tool install --python 3.12 mineru`. Ambientes isolados do uv (em `~/.local/share/uv/tools`), binários em `~/.local/bin`. Nada de pip no sistema.

### DESCOBERTAS
- MinerU instalou na versão 4.0.6, e a v4 mudou a arquitetura. Virou uma "biblioteca de documentos para agentes" com servidor local (`mineru server start`) e subcomandos `parse`, `scan`, `search`. O extra `[core]` da documentação antiga não existe mais. `mineru parse` processa só as 10 primeiras páginas por padrão, e `-p all` é obrigatório. O serviço remoto (mineru.net) só entra com `--remote`. O padrão é local.
- MinerU tem telemetria anônima ligada por padrão. Desligada com `mineru telemetry disable` antes do primeiro processamento. O status mostrou 0 métricas pendentes e nenhum envio anterior. O comando exige o servidor local em pé.
- Os pesquisadores da frente B descreveram a v2/v3 (backend `pipeline` com `lang="pt"`). As opções da v4 são outras (`--tier flash|basic|standard|advanced`). A recomendação da pesquisa precisa ser reconferida contra a v4.
- Capítulo da Feldman: uma coluna, oito seções numeradas, sem figura, tabela ou nota de rodapé. Referências nas páginas 374 a 377. O ruído que o `pdftotext` deixa no corpo: afiliação da autora, bloco de copyright da Springer, números de página (351 a 377), cabeçalho corrido "M. P. Feldman" e título do capítulo, e cerca de 226 parênteses (a maioria citações autor-ano).

---

## [2026-09-23] - Bancada de extração: Docling vence, MinerU v4 não rodou (10:17)

### EXPERIMENTO
Docling e MinerU sobre o capítulo da Feldman (27 p., uma coluna) e o artigo de Pinheiro et al. (17 p., duas colunas, 7 figuras, 2 tabelas). Saídas numa pasta temporária de teste.

### RESULTADOS — Docling
- Feldman: nenhum número de página, cabeçalho corrido, afiliação ou copyright no texto. Hifenização desfeita, parágrafos contínuos. As oito seções numeradas e as subseções foram detectadas (todas no mesmo nível `##`; as numeradas são as seções principais). Sobras: uma imagem avulsa na página 1 (provável selo da editora), travessão convertido em hífen, `&` como `&amp;`.
- Pinheiro, leitor padrão (docling-parse): figuras, tabelas e legendas detectadas corretamente, mas o texto veio corrompido. Falta a letra C em várias palavras ("ABSTRA T", "INTRODU TION") e os espaços somem em trechos ("Figures4and5showthe"): 138 palavras com 22 letras ou mais.
- Causa: o leitor interno do Docling, não o PDF. `pdftotext` lê o mesmo arquivo corretamente. O PDF usa fontes Type 1C com codificação própria (ACaslonPro, Humanist777).
- Solução: `--pdf-backend pypdfium2`. Texto íntegro, 0 palavras grudadas, títulos certos. 57 s para 17 páginas no M3 Pro.
- Sobra no Pinheiro: a capa da Taylor & Francis (logos, título repetido, link DOI) no início. Tratar no roteiro.

### RESULTADOS — MinerU 4.0.6
Falhou: "No basic, standard, or advanced engine available". A v4 separou o motor de análise, que precisa ser instalado e servido à parte (parse-server). Só o modo `--tier flash`, que é prévia de texto, roda sem ele. Não instalado o motor: o Docling já resolveu os dois casos, e o MinerU fica como alternativa se aparecer PDF que o Docling estrague.

### DECISÃO
Extrator de PDF do MVP: Docling com `--pdf-backend pypdfium2`. Diverge da recomendação da frente B (MinerU), que foi escrita sobre a v2/v3 e sem teste.

### LIÇÃO
O leitor padrão de uma ferramenta pode falhar num PDF que ferramentas mais simples leem bem. Um contador de palavras anormalmente longas detecta o defeito sem ler o texto e serve de verificação automática no pipeline.

---

## [2026-09-23] - Versão 0: primeiro MP3 de ponta a ponta (10:23)

### SOLUÇÃO
`gerar_audio.py` na raiz do projeto, só biblioteca padrão. Lê o Markdown do Docling, monta o roteiro por capítulo, sintetiza com `say` e grava MP3 com capítulos ID3v2 pelo ffmpeg. Grava também `<nome>-roteiro.txt` com o que vai ser falado, para conferência.

Regras de roteiro da v0:
- Capítulo 0 "Abertura": título, autor e o resumo.
- Título de seção numerada abre capítulo. Título sem número é lido como subtítulo, com pausa (`[[slnc 700]]` do `say`).
- A leitura para no primeiro título de References, Notes, Disclosure, Funding, ORCID, Acknowledgments e equivalentes em português.
- Citação autor-ano entre parênteses é removida. "Schumpeter (1934)" vira "Schumpeter".
- Linha de imagem é descartada, e entidades HTML (`&amp;`) são convertidas.

### RESULTADOS
Feldman (2026): 9 capítulos, 61,8 min, 28,3 MB (MP3 64 kbps mono), voz Samantha a 185 palavras por minuto. Gerado em 40 s no M3 Pro. `ffprobe` e leitura dos bytes confirmam CTOC e 9 CHAP. Nenhum parêntese restante no roteiro. O capítulo 4 do original tem só 98 palavras, e é assim no PDF.

### PROBLEMAS MENORES
- O travessão do original vira hífen no Docling ("insight-that"). Não tratado na v0.
- Título de capítulo com vírgula quebra a leitura em CSV do ffprobe. É só um problema de conferência, os metadados estão certos. Conferir sempre com `-of json`.

### PENDENTE
Teste no Podcast Addict do celular: se os capítulos aparecem e se a posição de escuta é guardada.

---

## [2026-09-23] - Instalação das vozes (10:23)

- `brew install espeak-ng` e `uv tool install piper-tts`: ok.
- `uv tool install kokoro-onnx` falha, porque o pacote é biblioteca, sem executável ("No executables are provided"). Para o teste de vozes: ambiente `uv venv` temporário.

---

## [2026-09-23] - Amostras de voz: Kokoro, Piper e say (10:27)

### EXPERIMENTO
O mesmo parágrafo em várias vozes. Em português, um trecho de Serra, Cunha e Laplane (2023) sobre a fundação da Unicamp, com data, sigla (CGU, IBGE) e número. Em inglês, o primeiro parágrafo da Feldman. Saída em dois MP3s, um capítulo por voz, cada um anunciado por locução. Ambiente de teste temporário, com `uv venv`.

### PROBLEMA — Kokoro não gerava áudio
Erro "Error processing file '/Users/runner/work/espeakng-loader/.../phontab': No such file or directory". O pacote `espeakng-loader`, que o `kokoro-onnx` usa para fonemizar, traz gravado na biblioteca o caminho de dados da máquina de CI onde foi compilado. Não resolveu: variável `ESPEAK_DATA_PATH` nem `EspeakConfig` apontando para os dados do próprio pacote.
Solução: usar o espeak-ng do Homebrew. `Kokoro(..., espeak_config=EspeakConfig(lib_path="/opt/homebrew/lib/libespeak-ng.dylib", data_path="/opt/homebrew/share/espeak-ng-data"))`.

### PROBLEMA — Piper descarta a nasalização
37 avisos "Missing phoneme from id map: ̃" nas vozes pt_BR. O til de nasalização produzido pelo espeak-ng não existe no mapa de fonemas do modelo e é descartado. É a provável causa da "dicção ruim em palavras acentuadas" relatada na pesquisa (frente C). Não corrigido. Registrado para a escuta.

### MÉTRICAS
- Kokoro (kokoro-onnx, só CPU, M3 Pro): cerca de 5x o tempo real nas seis vozes. O capítulo da Feldman (62 min) sairia em cerca de 12 min.
- Piper: de 1,8 a 2,9 s por amostra de cerca de 45 s, ou seja, mais de 15x o tempo real.
- say: o mais rápido. A Feldman inteira saiu em 40 s.
- Os modelos Piper têm cerca de 63 MB cada. O Kokoro tem 325 MB, mais 28 MB de vozes.

### PENDENTE
Escuta do Danilo para escolher uma voz por língua.

---

## [2026-09-23] - Caminho validado no celular e vozes escolhidas (10:36)

### RESULTADOS
- Danilo ouviu o MP3 v0 da Feldman no Podcast Addict, copiado para a pasta que ele já usa. Os capítulos ID3v2 aparecem, e a posição de escuta é mantida ao fechar e abrir o app. O caminho completo, do PDF ao celular, está validado.
- A voz Samantha do `say` foi reprovada, por ser robótica demais.

### DECISÃO
- Português: Kokoro `pf_dora` (voz 1 da amostra).
- Inglês: Kokoro `af_heart` (voz 1 da amostra).
- `gerar_audio.py` ganhou `--motor kokoro|say` (padrão kokoro), `--lingua en|pt` e `--modelos`. A voz padrão sai da combinação motor e língua. O Kokoro sintetiza por parágrafo, com 0,35 s de silêncio entre parágrafos. As marcas `[[slnc N]]` do roteiro viram silêncio de N ms. Com o Kokoro, o script roda com o Python do ambiente que tem `kokoro-onnx`.

### PENDENTE
O ambiente do Kokoro e os modelos (353 MB) ainda estão numa pasta temporária. Falta um lugar definitivo. (Resolvido na 0.1.0: `.venv/` e `modelos/` no projeto.)

---

## [2026-09-23] - Feldman com Kokoro af_heart (10:50)

### RESULTADOS
76,1 min, 9 capítulos, 34,8 MB. Gerado das 10:35 às 10:50, cerca de 5x o tempo real só em CPU. O Kokoro fala cerca de 23% mais devagar que o `say` a 185 palavras por minuto (76,1 contra 61,8 min), somando também os 0,35 s de silêncio entre parágrafos.

### PROBLEMA
O arquivo passou do limite de 30 MiB de um canal de envio usado no teste. Para livro longo o tamanho vai crescer: 3 h a 64 kbps dão cerca de 82 MB. Não é problema para o celular, só para esse canal de envio.

---

## [2026-09-23] - Publicação da 0.1.0 (11:11)

### RESULTADOS
- Teste do zero num clone limpo, seguindo o README: `./baixar_modelos.sh` baixou e conferiu os dois modelos pelo SHA-256, `uv sync` montou o ambiente, e `uv run gerar_audio.py feldman.pdf` extraiu, montou o roteiro (0 palavras suspeitas) e gerou 77,0 min em 9 capítulos. O `git status` do clone ficou vazio depois da execução, então PDF, modelos, ambiente e saída ficam todos ignorados.
- Repositório público criado com licença MIT, tag e release v0.1.0.

### LIÇÃO
Antes do primeiro envio, simular o repositório (`git init` numa cópia, `git add -A`, `git ls-files`) mostra exatamente o que o `.gitignore` deixa passar, sem risco de publicar nada.
