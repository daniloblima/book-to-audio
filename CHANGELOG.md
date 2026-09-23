# CHANGELOG - book-to-audio

> Este arquivo registra todos os problemas, bugs, decisões técnicas e soluções encontradas durante o desenvolvimento. Consultado obrigatoriamente após cada compactação de contexto.

---

## Versões

O projeto segue versionamento semântico (MAIOR.MENOR.CORREÇÃO). As entradas datadas abaixo são o diário técnico de cada sessão, na ordem em que aconteceram. As entradas de versão resumem o que cada release entrega.

## [0.3.0] - 2026-09-23 (16:38)

Skill do Claude Code e instalação em um comando.

- Skill `/audiolivro` em `skill/SKILL.md`: pasta de saída perguntada no primeiro uso, busca do documento pelo nome (Spotlight) com escolha sempre do usuário, identificação de título, autor e língua, roteiro conferido antes da voz, confirmação acima de 60 minutos estimados, entrega só depois do MP3 pronto.
- `instalar.sh`: Homebrew (ffmpeg, espeak-ng, uv), modelos, ambiente e atalho da skill, pulando o que já está feito.
- Motor: `--identificar`, `--so-roteiro` (duração estimada a 110 palavras por minuto), `--mostrar-pasta` e `--definir-pasta` (`BOOK_TO_AUDIO_SAIDA` em `~/.claude/.env`), reaproveitamento da extração já feita.
- Correções: aviso de licença Creative Commons, inteiro ou em pedaço, sai do áudio; hífen de fim de linha solto ("so - ciais") é emendado.

## [0.2.0] - 2026-09-23 (12:30)

Figuras e tabelas, e limpeza de artigo de revista.

- O roteiro passa a ser montado a partir do JSON do Docling, que marca cabeçalho, rodapé, legenda, nota e fórmula. A capa de revista (nome do periódico, ISSN, "To cite this article", palavras-chave, JEL) fica de fora e só o resumo é lido. Subseção vira subtítulo.
- Figuras e tabelas: anúncio na língua do documento e legenda lida no fim do parágrafo que cita a figura pela primeira vez. Recorte de figura e legenda do PDF para `<obra>/figuras/`, com `legendas.txt`.
- Capítulo por figura anunciada ("Results · Figure 5"), com a imagem embutida (ID3 APIC). O Podcast Addict mostra o capítulo e não mostra a imagem de arquivo local.
- Cada documento ganha a sua pasta de saída, e os intermediários vão para `.trabalho/`. Destino padrão configurável por `BOOK_TO_AUDIO_SAIDA`.
- Capítulos gravados pelo mutagen em ordem cronológica no arquivo.
- Nova dependência: mutagen.

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

---

## [2026-09-23] - Saída por obra e diagnóstico para figuras (11:28)

### DECISÃO — onde ficam os áudios
Os áudios são do trabalho de leitura, não da ferramenta. Na máquina do autor, vão para uma pasta sincronizada com o celular, uma subpasta por obra: `<obra>/<obra>.mp3`, `<obra>/roteiro.txt` e, em breve, `<obra>/figuras/`. O gerador passa a criar a subpasta sozinho. O destino vem de `--saida`, ou da variável `BOOK_TO_AUDIO_SAIDA`, ou é `saida/`. Os intermediários (WAV por capítulo) foram para `.trabalho/<obra>/` no projeto (ignorado pelo git), para não pesar na pasta sincronizada.

### DESCOBERTAS no artigo de revista (duas colunas, Taylor & Francis)
- Com `--output` relativo, o Docling grava as imagens num caminho aninhado (`out/out/<nome>_artifacts/`), porque o link do Markdown e a pasta são ambos relativos. Usar caminho absoluto.
- A capa da editora vira 19 imagens de logotipo, o nome da revista como primeiro título (`## Regional Studies`), ISSN, "To cite this article", número de visualizações e o título repetido. A regra da v0.1.0 ("o primeiro título é o título do documento") trata o nome da revista como título e lê a capa inteira.
- Palavras-chave, JEL e histórico de submissão aparecem como seções antes da introdução.
- Subseção numerada ("7.1. Distribution of complexity") casa com a regra de seção numerada e viraria capítulo. Só o primeiro nível deve abrir capítulo.
- Títulos em maiúsculas ("1. INTRODUCTION").
- Rodapé de contato do autor ("CONTACT Ron Boschma ...") no meio do corpo.
- Legendas de figura e tabela saem como parágrafo próprio ("Figure 1. ..."), na posição física da figura, muitas vezes longe da primeira menção no texto. O Markdown põe a legenda antes da imagem. As tabelas saem como tabela Markdown de verdade.

---

## [2026-09-23] - Testes antes de codar: recorte de figura e imagem no capítulo (11:33)

- O JSON do Docling (`--to json`) traz, para cada figura e tabela, a página, a caixa delimitadora (origem no canto inferior esquerdo, em pontos) e as legendas ligadas a ela. Traz também o rótulo de cada trecho: `page_header`, `page_footer`, `footnote`, `formula`, `section_header`, `list_item`. O Markdown perde esses rótulos, e é por isso que o "CONTACT ..." apareceu no corpo. Decisão: o roteiro passa a ser montado a partir do JSON. O Markdown continua aceito como entrada alternativa, com as regras antigas.
- No artigo de teste: 26 imagens, das quais 7 com legenda (as figuras) e 19 sem (logotipos da capa). Mais 2 tabelas com legenda. Todos os títulos vêm com `level` 1, então a hierarquia sai da numeração ("7.1").
- Recorte com `pypdfium2` (já vem com o Docling): página renderizada em escala 3 (216 dpi), recortada na caixa convertida para pixels a partir do topo. A Figura 1 saiu certa, mas a caixa da figura não inclui a legenda, que ficou cortada na borda. Solução: unir a caixa da figura à da legenda, com folga.
- Imagem por capítulo: o ffmpeg não grava imagem dentro de CHAP. O `mutagen` 1.48 grava CTOC e CHAP com subframes TIT2 e APIC (JPEG de até 1000 px, cerca de 100 KB). O ffprobe lê os capítulos gravados pelo mutagen normalmente. Dependência nova: `uv add mutagen`.

---

## [2026-09-23] - Figuras e tabelas, roteiro a partir do JSON (11:46)

### SOLUÇÃO
`gerar_audio.py` reescrito em torno de uma lista de blocos (título, texto, legenda, nota, fórmula), montada a partir do JSON do Docling. O Markdown ficou como entrada alternativa.
- Descartados pelo rótulo do Docling: `page_header` e `page_footer`, imagem sem legenda (logotipos), fórmula e nota de rodapé. A nota ainda não entra no áudio, e é o próximo item.
- Capa: se o documento tem seções numeradas, tudo antes da primeira é capa, e dela só se lê o resumo (título "Abstract", "Resumo" ou "Summary", ou parágrafo que começa com "Abstract"). Sem seções numeradas, vale a regra antiga (o primeiro título é o título do documento).
- Só seção de primeiro nível abre capítulo. "7.1" vira subtítulo, sem o número. Título em maiúsculas vira "Primeira maiúscula".
- Ruído no corpo: linhas de contato, licença Open Access, ISSN, histórico de submissão e texto sem nenhuma palavra ("1.00", rótulo de eixo solto).
- Figuras e tabelas: o anúncio ("Figure 3, in the figures folder." ou "Figura 3, na pasta de figuras.") e a legenda entram no fim do parágrafo que cita a figura pela primeira vez, pela decisão do autor. Figura nunca citada é anunciada onde está. As menções reconhecem "Figures 4 and 5", "Tables 1–2" e as formas em português.
- Recorte: figura e legenda juntas, com 6 pt de folga, a 216 dpi, em `<obra>/figuras/Figura 01.png` e `Tabela 01.png`, mais `legendas.txt`.
- Capítulos: gravados pelo mutagen (CTOC + CHAP), não mais pelo ffmpeg. Cada figura anunciada abre um capítulo "<seção> · Figure N" com a imagem (APIC, JPEG até 1000 px), que dura até a próxima figura ou o fim da seção.

### PROBLEMAS
- Primeira versão dos capítulos de figura: cada figura cortava a seção em três pedaços ("Results", "Figure 1", "Results"). O artigo de teste ficou com 27 capítulos, dez deles chamados "Results". Trocado pelo capítulo que dura até a próxima figura, o que também deixa a imagem na tela enquanto o texto segue falando dela.
- Com ids "ch2" e "ch10", o ffprobe listou os capítulos fora da ordem (ordem alfabética do id). Corrigido com zeros à esquerda ("ch002").
- Nome de capítulo em minúsculas ("introduction"): `str.capitalize()` não sobe a primeira letra quando o título começa com número. Corrigido.

### RESULTADOS
- Artigo de teste (17 p., duas colunas): 49 cabeçalhos e rodapés, 19 logotipos e 8 fórmulas descartados; 9 de 9 figuras e tabelas anunciadas e recortadas certas (conferidas na imagem a Figura 1, a Figura 5 e a Tabela 1); leitura interrompida em "Disclosure statement"; 50,6 min.
- A Feldman passa pelo roteiro novo com os mesmos 9 capítulos e as mesmas contagens de palavras da 0.1.0 (57 cabeçalhos e rodapés e 1 selo descartados).
- Correção da correção: os zeros à esquerda no id não resolveram a ordem. Causa real: o mutagen grava os quadros ordenados por tamanho (`ID3Tags._write`, chave `(prioridade, len(data), HashKey)`), então capítulo com imagem, maior, ia para o fim do arquivo. Solução: `salvar_em_ordem()` substitui o `_write` da instância e grava metadados, CTOC e depois os CHAP por tempo de início. Conferido com o ffprobe: 18 capítulos em ordem, 9 com imagem. O MP3 do artigo foi regravado só nas marcas, sem sintetizar de novo.

---

## [2026-09-23] - Teste no celular do artigo com figuras

### RESULTADOS
- O autor ouviu o artigo no Podcast Addict. Os 18 capítulos aparecem e estão em ordem. A imagem embutida no capítulo (APIC dentro de CHAP) não aparece em arquivo local. A nota do changelog do app sobre arte de capítulo provavelmente vale só para episódios de feed.
- A pasta `figuras/` na nuvem funciona como anexo: ele ouve o anúncio e abre a figura no app do OneDrive.
- Fluxo real: o Podcast Addict não lê pasta do OneDrive, então o MP3 é copiado da pasta sincronizada para uma pasta local do celular. Ideia para depois: um app Android de sincronização de pasta para eliminar a cópia manual.

### DECISÃO
Manter os capítulos de figura, porque a navegação por figura funciona, e manter a imagem embutida, que custa cerca de 100 KB por figura e pode aparecer em outros tocadores. O README diz que o Podcast Addict não mostra a imagem.

---

## [2026-09-23] - Cabeçalho corrido e parágrafo partido com o leitor pypdfium2 (12:33)

### PROBLEMA
Teste rápido da Feldman com o código novo (voz `say`): o leitor pypdfium2 fez o Docling marcar só 17 cabeçalhos e rodapés, contra 57 com o leitor padrão. Vazaram para o texto falado 12 cabeçalhos "354 M. P. Feldman" (um por página par) e a afiliação da autora. Cada cabeçalho vazado partia um parágrafo em dois na virada de página, e foram 10 frases cortadas ao meio. Na 0.1.0 isso não aparecia porque a Feldman tinha sido extraída com o leitor padrão.

### SOLUÇÃO
- Cabeçalho corrido: linha de texto com menos de 12 palavras que aparece 3 vezes ou mais no documento, igual a menos dos números, é descartada. Regra genérica, sem nome de autor nem de revista.
- Afiliação: linha de até 120 caracteres, sem ponto final, com University, Universidade, Institute, Department e equivalentes.
- Parágrafo partido: se o trecho anterior não termina em pontuação final e o novo começa em minúscula, os dois são emendados.
- Anúncio de figura: fica pendente até o parágrafo fechar a frase (ou até o próximo título), para não cair no meio de uma frase partida entre páginas.

### RESULTADOS
Feldman: 0 quebras, 0 vazamentos, 8.453 palavras (as 8.618 anteriores menos o que vazava). Artigo de teste: 0 quebras, 9 de 9 anúncios, todos depois de ponto final. O MP3 do artigo foi gerado de novo com as correções.

### LIÇÃO
Trocar o leitor de PDF para consertar um documento pode piorar outro. Cada mudança de extração se testa nos dois documentos de referência, contando quebras de frase e linhas curtas repetidas.

---

## [2026-09-23] - Skill /audiolivro, testes pelo skill-creator e correções (16:38)

### OBJETIVO
Transformar o book-to-audio em skill do Claude Code seguindo o skill-creator da Anthropic, no mesmo desenho da pesquisa-orquestrada (motor no repositório, skill em `skill/`, atalho em `~/.claude/skills/audiolivro`).

### SOLUÇÃO
Motor ganhou as funções que a skill chama (identificar, parar no roteiro, pasta de saída). O trabalho repetitivo e determinístico ficou no script, e a interpretação (título limpo, autor em forma curta, qual arquivo) ficou com o Claude, porque os metadados de PDF vêm sujos: no artigo de teste, o campo Author traz os quatro nomes grudados com todas as afiliações.

### TESTES (iteração 1, três sessões `claude -p` separadas, saída numa pasta temporária)
Nota: 4 de 14 critérios. Sem comparação "sem skill", porque sem ela o Claude nem sabe que o motor existe.
- Pedido vago ("o artigo do Pinheiro e do Boschma"): achou o MP3 já gerado no OneDrive e descreveu esse áudio em vez de seguir o fluxo. Leu o roteiro e achou o aviso de licença Creative Commons ("nc-nd/4.0/, which permits non-commercial re-use...") no meio de uma frase da introdução.
- Caminho explícito em português (capítulo de Serra, Cunha e Laplane): língua, voz e as 3 tabelas certas. A síntese em segundo plano morreu quando a sessão não interativa terminou, o que é limite do teste. Achou hífen solto ("so - ciais", "Amé - rica", "edu - cação") e 3 ou 4 notas bibliográficas que o Docling não marcou como nota.
- Pedido ambíguo ("o Running Lean"): o Spotlight achou oito cópias (PDF, EPUB, AZW3, KFX). A skill escolheu sozinha um PDF de Downloads com nome de site de download e "cópia", disparou a extração de 370 páginas antes de confirmar e não avisou que EPUB e AZW3 não são aceitos.

### CAUSAS E CORREÇÕES
- Licença no meio da frase: a regra de parágrafo partido, criada hoje, emendou a continuação da licença (começa em minúscula) no parágrafo anterior, porque o RUIDO só pegava o começo do aviso. Correção: `LICENCA` descarta qualquer bloco com creativecommons.org, "nc-nd/", "which permits ... re-use" ou "distributed under the terms of the Creative Commons".
- Hífen solto: `HIFEN_SOLTO` emenda "até 6 letras + espaço-hífen-espaço + minúscula". Um travessão de verdade vem como "—" ou "–", e o hífen composto vem sem espaços, então os dois não são afetados.
- Skill: a instrução "confirme quando houver mais de um candidato" não dizia por quê, e o modelo trocou por critério técnico. Reescrita com a razão (só o usuário sabe qual edição quer, e cópia de origem duvidosa nunca é escolha feita em nome dele). Acrescentados o aviso de formatos não aceitos, o caso "o áudio já existe" e a espera pelo `MP3 pronto` antes de entregar.

### RESULTADOS
Conferência rápida pelo `--so-roteiro`: artigo de teste sem licença (0 ocorrências), capítulo em português sem hífen solto ("sociais" 5x, "educação" 2x, "América Latina"), Feldman idêntica (8.452 palavras). O MP3 do artigo foi gerado de novo com a correção.

### PENDENTE
- Segunda iteração dos testes da skill, com os mesmos três pedidos. Não rodada por falta de tempo do autor. O visualizador da primeira ficou na pasta temporária da sessão.
- Notas bibliográficas não marcadas pelo Docling: próximo item (notas de rodapé, separando nota de argumento de nota de referência).
- Otimização da descrição da skill (`run_loop` do skill-creator).

