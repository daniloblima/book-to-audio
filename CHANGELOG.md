# CHANGELOG - book-to-audio

> Este arquivo registra todos os problemas, bugs, decisões técnicas e soluções encontradas durante o desenvolvimento. Consultado obrigatoriamente após cada compactação de contexto.

---

## Versões

O projeto segue versionamento semântico (MAIOR.MENOR.CORREÇÃO). As entradas datadas abaixo são o diário técnico de cada sessão, na ordem em que aconteceram. As entradas de versão resumem o que cada release entrega.

## [0.4.0] - 2026-09-28 (18:53)

Voz própria em português, com conferência automática.

- OmniVoice (ajuste pt-BR `edwixx/omnivoice-brpt-v15`) como segundo motor: clona a voz a partir de uma gravação de 5 a 10 s com a transcrição. `--motor auto` usa a voz própria em português quando há referência configurada e o Kokoro no resto. Opções `--referencia`, `--definir-voz-pt`, `--definir-whisper` e `--sem-conferencia`.
- Conferência: cada trecho gerado é transcrito pelo `whisper-server` e comparado com o texto; o incompleto é gerado de novo, até 3 vezes, e o que continuar incompleto vai para `conferencia.txt`.
- Pausas de narração: silêncio de cada trecho aparado com rampa (limiar de -55 dB, folga de 150 ms no fim), 0,5 s entre frases, cerca de 1 s entre parágrafos, silêncio acima de 0,3 s dentro da frase reduzido a 0,22 s. Frase só é cortada nos travessões, no ponto e vírgula e, acima de 350 caracteres, numa vírgula.
- Roteiro: barra entre palavras vira pausa; capítulo sem seção interna não vira mais capa; título curto abre capítulo em documento sem numeração; "Fonte:" e "Nota:" saem do áudio.
- Progresso no log a cada 50 trechos. Dependências: omnivoice 0.2.1, torch e torchaudio 2.11.
- Aprovado pelo autor, de ouvido, nos 5 min de teste com a voz dele.

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


---

## [2026-09-25] - Primeiro uso real da skill e pedido de voz mais natural (16:06)

### RESULTADOS
Numa sessão de outro projeto, a skill `/audiolivro` gerou três áudios em português, de ponta a ponta, entre 09:24 e 11:25 de 25/09: um capítulo de livro de 2018 sobre universidades e desenvolvimento regional (41,4 min), um capítulo sobre educação e crescimento (36,6 min, 8 capítulos, com figuras) e o capítulo de 2023 que serviu de teste. É a validação de uso que a segunda iteração de testes daria.

### PROBLEMAS
- O capítulo de 2018 saiu com só 2 capítulos (abertura e um de 6.097 palavras). Diagnóstico registrado pela própria sessão de uso no `BACKLOG.md` (25/09, 09:16), mais grave do que parecia pelo MP3: o capítulo não tem nenhuma seção interna, a regra atual só começa o corpo no segundo título, e o segundo título era "Referências". O roteiro saiu com 15 palavras. O áudio entregue veio de um contorno manual (título falso inserido numa cópia do JSON). O mesmo BACKLOG registra "Fonte: Elaborada pelos autores." lido sete vezes e linhas de definição de equação lidas em voz alta noutro capítulo. Os dois itens ficam para a próxima rodada no motor.
- O teste de 23/09 com o Running Lean criou uma pasta vazia na pasta real de saída, apesar de `BOOK_TO_AUDIO_SAIDA` apontar para uma pasta temporária naquela sessão. A resposta daquela sessão mostra que o modelo passou o destino por conta própria. Pasta removida. Lição: em teste, conferir a pasta real depois, porque a variável de ambiente não impede o modelo de escolher outro destino.
- A voz `pf_dora` foi considerada robótica demais para texto denso: dá para acompanhar, mas distrai. Aberta a pesquisa de vozes pt-BR mais naturais, com clonagem da voz do autor como opção.

---

## [2026-09-25] - Teste do OmniVoice pt-BR contra a Dora (16:40)

### DECISÃO
Por espaço em disco, um modelo só na bancada: o OmniVoice com o ajuste pt-BR `edwixx/omnivoice-brpt-v15`, o único dos três candidatos da pesquisa (`02-pesquisa-vozes-naturais.md`) com relato positivo de brasileiros ouvindo português. Teste de uns 5 minutos, sem gerar capítulo inteiro.

### SOLUÇÃO
Ambiente temporário com `uv` (torch 2.8.0, omnivoice 0.2.1, 990 MB, com o PyTorch reaproveitado do cache). Modelo em MPS e float16, gerado frase por frase (a pesquisa registrou chiado em texto longo), com 0,25 s entre frases e 0,4 s entre parágrafos. Voz: a referência publicada pelo autor do ajuste (um falante americano, 27,5 s) com a transcrição dela e a instrução "portuguese accent", como nas amostras dele. Com a transcrição dada, o OmniVoice não baixa o Whisper para transcrever a referência.

### RESULTADOS
- Trecho de 729 palavras do capítulo de 2018 que soou robótico na Dora.
- OmniVoice: 20 frases, 6,5 min de áudio em 14,4 min de geração (0,45 do tempo real). Carga do modelo, 87 s. Um capítulo de 1 hora levaria cerca de 3 horas, e um livro de 10 horas, uma noite e meia.
- Dora, mesmo trecho: 5,0 min em 77 s. O OmniVoice fala cerca de 30% mais devagar.
- O OmniVoice avisou que a referência passa dos 20 s recomendados (3 a 10 s ideais), o que deixa a geração mais lenta e pode piorar a clonagem. Cortar a referência é o primeiro ajuste de velocidade a testar.
- Espaço: modelo pt-BR mais o codificador de áudio do base, cerca de 3,3 GB no cache do Hugging Face.

### PENDENTE
Escuta do autor (arquivo de comparação com dois capítulos). Sobras de 23/09 que podem sair para liberar espaço: ferramentas `uv` do MinerU e do Docling avulso (2,7 GB) e cache do `uv` (3,6 GB).

---

## [2026-09-28] - Limpeza de sobras dos testes (09:19)

- Removidas as ferramentas `uv tool` do MinerU, do Docling avulso e do Piper, instaladas em 23/09 só para teste. O Docling do pipeline mora no `.venv` do projeto.
- O servidor local do MinerU (`mineru server start`, 23/09) ainda estava rodando cinco dias depois. Encerrado, e `~/.mineru` apagada. Lição: serviço iniciado em teste se desliga no fim do teste.
- `.trabalho/`: apagados os WAV e AIFF intermediários (465 MB para 3,5 MB). Ficam as extrações (JSON e Markdown), que permitem gerar de novo com outra voz sem extrair outra vez.
- `uv cache prune`: 1,4 GB. Espaço livre foi de 54 para 56 GB. Estimativa inicial de uns 6 GB estava errada: o `uv` compartilha os mesmos arquivos entre cache, ferramentas e ambientes, e somar o tamanho de cada pasta conta o mesmo dado várias vezes.
- A comparação de vozes saiu da pasta temporária para `Audiolivros/Comparação de vozes - Serra 2018/`.

---

## [2026-09-28] - OmniVoice com referências brasileiras (09:43)

### PROBLEMA
O autor não aprovou a primeira versão do OmniVoice: soava como um americano falando português. Gostou da velocidade, das pausas e da respiração. Causa: a referência publicada pelo autor do ajuste pt-BR é de um falante americano, e o OmniVoice copia da referência timbre e sotaque.

### SOLUÇÃO
- O banco do ajuste pt-BR (`edwixx/brazilian-portuguese-TTS`) exige aprovação manual e vem num zip único, então não serve.
- Usado o CML-TTS em português (`freds0/cml_tts_dataset_portuguese`, 74.163 trechos de audiolivros de domínio público), consultado trecho a trecho pela API de linhas do Hugging Face, sem baixar o banco. A API devolve HTTP 429 com pedidos seguidos, e a solução foram pausas de 3 s e nova tentativa com espera crescente.
- Critério: um trecho por locutor, de 6 a 10 s, com concordância entre transcrição e reconhecimento automático de pelo menos 0,97. Quatro locutores, lendo Alencar e Machado, prováveis brasileiros. O banco não informa sotaque nem gênero.

### RESULTADOS
- Com a referência de 7 a 8 s, a geração passou de 0,45 para 0,83-0,86 do tempo real. Um capítulo de 1 hora levaria cerca de 70 minutos.
- Primeiro parágrafo do trecho: 70 a 75 s de áudio em três locutores e 93 s no locutor 12249. Pode ser ritmo mais lento ou repetição de trecho; conferir na escuta.
- Arquivo para escuta: `Audiolivros/Comparação de vozes - Serra 2018/Vozes brasileiras - OmniVoice.mp3`, um capítulo por locutor, cada um abrindo com a voz original dele.

---

## [2026-09-28] - Primeira referência com a voz do autor (10:04)

- Pasta `vozes/` criada e posta no `.gitignore`: gravação de voz funciona como senha, porque 10 s bastam para clonar. `vozes/texto-para-gravar.md` traz um trecho de não ficção geral em português (*Conteúdo S.A.*, Joe Pulizzi) para a segunda gravação.
- Primeira gravação (QuickTime, AIFC, 48 kHz, 16 bits, estéreo, 38 s, pico em -10,5 dB). O Whisper large-v3-turbo transcreveu as três frases técnicas quase sem erro, e os tempos de cada frase saem da transcrição. Referência escolhida: a terceira frase, 24,0 a 33,95 s (9,95 s), mono, 24 kHz, normalizada a -20 LUFS.
- Primeiro parágrafo do trecho do Serra 2018: 80 s de áudio em 98 s de geração (0,82 do tempo real).
- Conferência automática nova, feita à mão por enquanto: transcrever o áudio gerado com o Whisper e comparar palavra a palavra com o texto. Deu 96% de semelhança, com dois pontos suspeitos: "terceira missão" ouvido como "a", e "numa elevada produção científica" ausente. Falta distinguir erro do Whisper de palavra pulada pelo modelo. Se o OmniVoice virar a voz padrão, essa conferência entra no pipeline para pegar frase pulada ou repetida em texto longo.

---

## [2026-09-28] - Segunda referência do autor e palavras puladas (10:08)

- Segunda gravação (82 s, trecho de *Conteúdo S.A.*). Referência: "Depois de encontrar o ponto ideal e definir o ajuste, você escolhe uma plataforma e constrói uma base de conteúdo.", de 47,9 a 55,6 s (7,7 s), corte ajustado pelas pausas do `silencedetect` e não pelos tempos do Whisper, que marcava o início 2 s antes, dentro da pausa entre parágrafos. O Whisper acrescentou "Obrigado por assistir!" no silêncio final, alucinação conhecida dele.
- Mesmo parágrafo do Serra 2018: 72,3 s em 87,3 s.
- Conferência pelo Whisper contra o texto do Serra: 86% com a referência do *Conteúdo S.A.*, 96% com a técnica. Com a do *Conteúdo S.A.* o modelo pulou uma oração inteira (cerca de 30 palavras, de "terceira missão" a "nacionais e estrangeiros") e trocou "regiões em que estão inseridas" por "redes sociais". Com a técnica, "terceira missão" e "numa elevada produção científica" já não apareciam.
- Padrão: o ponto de falha nas duas é a mesma frase longa do Serra, com um aparte entre travessões. O OmniVoice pula conteúdo em frase longa e com aparte. Se ele virar a voz padrão, o pipeline precisa (1) quebrar a frase nos travessões e em frases longas antes da síntese e (2) conferir cada frase gerada com o Whisper e gerar de novo a que vier incompleta.
- O autor estranhou as palavras ausentes porque não estavam no texto que ele leu: a explicação anterior não deixou claro que a gravação dele é só a referência de timbre e que o texto falado é o do Serra. Registrado para explicar melhor nos próximos testes.

---

## [2026-09-28] - Faxina da pasta vozes/ (10:16)

Primeiro uso da skill `/faxina`. O levantamento não achou nada: ele é feito para documentos (estado velho, número divergente, consolidado repetido, caminho quebrado) e classifica todo áudio como "bruto", sem separar gravação, recorte e áudio gerado. A arrumação foi proposta à mão e aprovada pelo autor. Nomes antigos citados nas entradas acima, de-para:

- `danilo-teste1-original.aifc` → `vozes/gravacoes/gravacao-1-frases-tecnicas.aifc`
- `danilo-teste2-original.aifc` → `vozes/gravacoes/gravacao-2-conteudo-sa.aifc`
- `vozes/texto-para-gravar.md` → `vozes/gravacoes/texto-para-gravar.md`
- `danilo-ref-frase3.wav` e `.txt` → `vozes/referencias/ref-tecnica.wav` e `.txt`
- `danilo-ref-conteudo.wav` e `.txt` → `vozes/referencias/ref-conteudo-sa.wav` e `.txt`
- MP3 de escuta → `vozes/testes/`

As gravações originais que estavam em Downloads foram apagadas depois de conferidas byte a byte com as cópias.

---

## [2026-09-28] - Referência mais rápida (10:27)

- O autor achou a leitura clonada lenta demais. Medido: a referência técnica tinha 127 palavras por minuto, a do *Conteúdo S.A.* 156. Audiolivros costumam ficar entre 150 e 170. O OmniVoice tem parâmetro `speed` em `generate()`, mas a escolha foi regravar no ritmo certo, porque acelerar leitura lenta tende a soar apressado; o parâmetro fica para retoque.
- Terceira gravação (`vozes/gravacoes/gravacao-3-frases-tecnicas-rapida.aifc`), mesmas três frases, uma tentativa: 23,7 s de fala contra 34 s da primeira. Referência `ref-tecnica-rapida`: a mesma terceira frase, de 19,3 a 26,65 s (7,35 s, 168 palavras por minuto), para que a comparação isole o ritmo.
- Mesmo parágrafo do Serra: 65,4 s de áudio (contra 80 s), 144 palavras por minuto, gerado em 80 s.
- Fidelidade 95%: desta vez "terceira missão" saiu, mas faltaram "caminharam" e "portanto o fato de ambos, livro e projeto, terem o mesmo", em outra frase longa. Confirma que o pulo em frase longa é do modelo e não da referência: a quebra de frase e a conferência pelo Whisper são necessárias com qualquer referência.

---

## [2026-09-28] - OmniVoice com a voz do autor dentro do motor (10:57)

### DECISÃO
O autor aprovou a voz clonada com a referência rápida (`vozes/referencias/ref-tecnica-rapida`). Ela vira a voz padrão em português. O inglês continua com o Kokoro `af_heart`. A voz fica fora do repositório. Sem referência configurada, o português volta para a Dora.

### SOLUÇÃO
- Dependência nova: `omnivoice` 0.2.1. PyTorch e torchaudio fixados em 2.11, casados. O `uv add omnivoice` tinha deixado torch 2.14 com torchaudio 2.11.
- Configuração no `~/.claude/.env`, pelas funções genéricas `ler_config` e `gravar_config`: `BOOK_TO_AUDIO_VOZ_PT` (a gravação; a transcrição fica num `.txt` de mesmo nome) e `BOOK_TO_AUDIO_WHISPER` (modelo ggml para a conferência). Opções `--definir-voz-pt`, `--definir-whisper`, e `--mostrar-pasta` mostra as três.
- `--motor auto` (padrão): OmniVoice em português quando há referência, Kokoro no resto. Opções `--referencia` e `--sem-conferencia`.
- `fragmentar()`: frase cortada nos travessões com espaço (inclusive "–," de fechamento de aparte) e nos ponto e vírgula, e o que passar de 160 caracteres cortado numa vírgula perto do meio. Palavras com hífen ficam inteiras. Pausas: 0,12 s entre trechos, 0,25 s entre frases, mais 0,15 s no fim do parágrafo.
- Conferência (`Conferente`): o `whisper-server` fica carregado durante a geração, e cada trecho é transcrito (0,8 a 0,9 s por trecho de 6 s) e comparado palavra a palavra. Cobertura mínima de 80% (50% abaixo de 6 palavras), transcrição no máximo 1,4 vez o original (contra repetição), trecho de até 3 palavras aceito sem conferir. Até 3 tentativas, fica a melhor. O que continuar incompleto vai para `<obra>/conferencia.txt`.
- Estimativa do `--so-roteiro` para o OmniVoice: 135 palavras por minuto e geração a 0,7 do tempo real.

### CORREÇÕES DO BACKLOG DE 25/09 (sessão de uso)
- Capítulo sem seção interna: sem seção numerada, o primeiro parágrafo de 40 palavras ou mais depois do título abre o corpo, num capítulo com o título do documento. Serra 2018: de 15 para 6.091 palavras de roteiro, sem contorno manual no JSON.
- "Fonte:", "Nota:" (e Source, Note) no começo de linha curta saem do áudio. Cunha 2018: 7 "Fonte: Elaborada pelos autores." a menos.
- Sem seção numerada, título de até 6 palavras abre capítulo. Cunha 2018: de 1 para 6 capítulos (Introdução, Metodologia, Base de dados, Resultados e discussão, Considerações finais). Título longo, que costuma ser de tabela mal marcada, continua subtítulo.
- Regressão conferida pelo `--so-roteiro`: artigo de revista (6.963 palavras, 9 capítulos) e capítulo de 2023 (5.563 palavras, 6 capítulos) iguais a antes.

### PROBLEMAS NO CAMINHO
- Primeiro teste no ambiente do projeto ficou mais de 10 min parado em "Loading weights", com o código passado pela entrada padrão e outro processo do mesmo modelo rodando ao mesmo tempo. Os testes seguintes pareciam travados pelo mesmo motivo, mas o `timeout` usado para limitá-los não existe no macOS: o comando nem rodava, e o filtro da saída escondia o erro. Três hipóteses erradas (versão do PyTorch, cache travado, pasta) antes de ver isso. Lição: no macOS não há `timeout`; e antes de concluir que algo travou, conferir que o comando chegou a executar.
- Teste curto com um `.md` de um título e um parágrafo: o parágrafo nem entrou (o mesmo defeito do capítulo sem seção) e a conferência refez à toa os trechos "Teste." e "Serra.", de uma palavra. Daí a regra das 3 palavras.

---

## [2026-09-28] - Capítulo inteiro com a voz do autor (12:19)

### RESULTADOS
- Serra 2018 (6.091 palavras), OmniVoice com `ref-tecnica-rapida` e conferência: 40,2 min de áudio em 82 min (10:56 a 12:18), 0,49 do tempo real. A versão da Dora tinha 41,4 min. MP3 de 19 MB.
- Conferência: 352 trechos, 14 gerações refeitas, 4 marcados como incompletos no fim. Dos 4, dois são defeito da extração ("regiãoo", "macroecon ômica") lido corretamente pela voz, um é diferença de grafia ("três" contra "3", sigla "(EGC)" não transcrita), e um pode ser pulo real ("(insumos) e outputs (produtos/serviços)", transcrição truncada).
- A estimativa de 0,7 do tempo real estava otimista. O teste de 0,82 fora feito com frases inteiras, de uns 20 s. Com trechos curtos (média de uns 7 s), cada chamada ao modelo rende menos. Estimativa do `--so-roteiro` corrigida para 0,45. Livro de 10 h: cerca de 20 h de geração.
- Sem progresso dentro do capítulo, um capítulo de 6 mil palavras ficou 80 min sem notícia no log. Para saber a posição, foi preciso transcrever o último trecho conferido e procurá-lo no roteiro (94% às 12:13). Agora o log mostra uma linha a cada 50 trechos.

### PENDENTE
- Escuta do autor.
- Normalizar número por extenso contra algarismo na conferência ("três" e "3"), para não marcar como incompleto o que saiu certo.

---

## [2026-09-28] - Teste do Gemini 3.8 Flash-Lite TTS, camada gratuita (15:40)

### CONTEXTO
O autor ouviu o capítulo com a voz clonada e achou estranho: pausa longa demais antes de vírgula, pausa curta entre frases e pouca dinâmica. Causas do nosso lado: `fragmentar()` corta na vírgula, cada trecho sai do modelo com silêncio próprio no começo e no fim e entonação de fim de frase, e as pausas eram 0,12 s e 0,25 s. Boa prática encontrada: gerar por parágrafo (contexto dá dinâmica), aparar o silêncio de cada trecho, pôr cerca de 0,5 s entre frases e perto de 1 s entre parágrafos, nunca cortar em vírgula.

### RESULTADOS
- Chave do Google em `~/.claude/.env` (`GEMINI_API_KEY`). O `.env` é ignorado pelo git do `~/.claude`, nunca foi rastreado e não aparece no histórico (conferido). Modelos de voz visíveis: gemini-2.5 flash/pro preview, 3.1 flash, 3.8 flash e 3.8 flash-lite TTS.
- Formato que funcionou: `generateContent` clássico, `responseModalities: ["AUDIO"]`, `speechConfig.voiceConfig.prebuiltVoiceConfig.voiceName`. Devolve PCM 16 bits, 24 kHz, mono, em base64.
- **Filtro de direito autoral:** o parágrafo inteiro do Serra (4 frases, 1.155 caracteres) foi recusado com `finishReason=OTHER`, "may contain material that resembles existing copyrighted works". As 4 frases, uma a uma, passaram. Em blocos de 2 frases, um passou e outro foi recusado. Consequência: livro publicado precisa ir frase a frase ou em blocos pequenos, com recuo para frase quando o bloco for recusado. Isso tira o contexto de parágrafo, que é justamente a vantagem do Gemini.
- **Camada gratuita:** 10 pedidos por dia por modelo (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`, limite 10). Serve só para teste. Um capítulo precisa de uns 150 pedidos.
- Velocidade: 20 s de áudio em 6 a 9 s. Uso medido de cerca de 32 tokens por segundo de áudio (e não 25). Custo na camada paga, preço até 31/12/2026: US$ 0,69 por hora de áudio (US$ 0,35 no modo em lote). Capítulo de 40 min, uns US$ 0,46; livro de 10 h, uns US$ 7 (US$ 3,50 em lote).
- Comparação para escuta: `Audiolivros/Comparação de vozes - Serra 2018/Gemini contra OmniVoice.mp3` (Charon com o parágrafo inteiro, Sadaltager com 3 frases e a voz do autor no OmniVoice), frases aparadas e 0,5 s entre elas.

---

## [2026-09-28] - Pausas revistas no OmniVoice (16:32)

### PROBLEMA
Na escuta do capítulo: pausa longa antes de vírgula, pausa curta entre frases e pouca dinâmica. No Gemini, chiado entre frases. As duas coisas vieram da montagem, não dos modelos: a vírgula virava fim de trecho (com entonação de fim de frase e silêncio do modelo somado ao nosso), 0,25 s entre frases é curto para narração, e no Gemini o silêncio foi cortado a seco, o que estala.

### SOLUÇÃO
- `aparar()`: tira o silêncio das pontas de cada trecho (limiar de -40 dB em relação ao pico, folga de 30 ms) e aplica rampa de 20 ms na entrada e na saída.
- Pausas: 0,3 s nos cortes de travessão, 0,5 s entre frases e mais 0,45 s no fim do parágrafo (cerca de 1 s).
- `TRECHO_MAXIMO` de 160 para 350: frase só é cortada na vírgula acima de 350 caracteres. Travessão e ponto e vírgula continuam cortando.

### RESULTADOS
Os mesmos 5 min do Serra 2018, com a voz do autor: 5,0 min em cerca de 9 min de geração. Conferência: 28 trechos, 0 refeitos, 0 incompletos. Com frases inteiras, o modelo não pulou nada nesse trecho, o que sugere que o corte na vírgula mais atrapalhava do que protegia. Arquivo de escuta: `Audiolivros/Comparação de vozes - Serra 2018/OmniVoice com pausas novas e Gemini.mp3`, com o parágrafo do Gemini (Charon) refeito com a mesma rampa.

---

## [2026-09-28] - Barra entre palavras e pausa exagerada na vírgula (16:58)

### PROBLEMA
Na escuta dos 5 min com as pausas novas (aprovada: "melhorou significativamente"), dois incômodos: "Integração Nacional/Capes" saía emendado, porque a barra não tem som; e havia uma pausa alongada antes de "tema", em "nesse importante, e pouco explorado, tema". Medido com o Whisper por palavra e o `silencedetect`: 0,43 s entre "explorado" e "tema", contra 0,2 a 0,35 s nas outras vírgulas. A pausa era do modelo, não de corte nosso.

### SOLUÇÃO
- `limpar()`: "e/ou" vira "e ou", e barra entre duas palavras (dois caracteres de cada lado, com ou sem espaço) vira ", ". "km/h" e "m/s" ficam intactos, porque um dos lados tem uma letra só. Vale para todos os motores e aparece no roteiro.
- `encurtar_silencios()`, chamada dentro de `aparar()`: dentro de um trecho, silêncio acima de 0,30 s vira 0,22 s, cortando o meio. As pausas entre frases e parágrafos entram depois e não são afetadas. Teste sintético: 0,45 s virou 0,22 s, e 0,20 s ficou intacto.

### RESULTADOS
Primeiro parágrafo gerado de novo: "Nacional, Capes" com pausa, e a pausa antes de "tema" com 0,24 s. Conferência: 9 trechos, nenhum refeito. O Whisper transcreveu a última palavra como "tempo", e não "tema": pode ser erro de reconhecimento ou de pronúncia, e fica para a escuta do autor. Uma palavra errada em 40 passa pelo limiar de 80% da conferência, que foi desenhado para pegar trecho pulado e não troca de palavra.

---

## [2026-09-28] - "tema" cortado ao meio, e início do teste do TADA (17:19)

### PROBLEMA (não corrigido)
O autor ouviu o primeiro parágrafo corrigido: a palavra "tema", no fim da primeira frase, saiu cortada ao meio, e por isso o Whisper ouviu "tempo". Causa provável: `aparar()` corta o fim do trecho no último ponto acima de -40 dB em relação ao pico, com 30 ms de folga e 20 ms de rampa. A última sílaba de uma palavra dita baixo cai abaixo desse limiar e é comida pela rampa. Correção a testar quando voltarmos ao OmniVoice: limiar mais baixo (-55 dB), folga maior no fim (uns 150 ms) e rampa só sobre o silêncio. Lição: aparo por limiar de volume precisa de folga generosa no fim da frase, porque a voz costuma cair no final.

### DECISÃO
O autor ainda não aprovou a qualidade do OmniVoice e pediu para testar o TADA (Hume AI), priorizando voz gratuita.

### DESCOBERTAS sobre o TADA
- `HumeAI/mlx-tada-3b`: pesos para Apple Silicon, 9,5 GB, abertos (não exigem aprovação). Licença Llama 3.2 Community. Memória: cerca de 17 GB em bfloat16 e cerca de 6 GB com `quantize=4`, que o fabricante recomenda para máquina de 16 GB e diz ser 10 vezes mais rápido.
- Pacote `mlx-tada` (PyPI). Clona a voz com `load_reference(audio, texto)`. Sem o texto, ele tenta transcrever com o mlx-whisper. Não há parâmetro de idioma: a língua sai do texto e da referência. O multilíngue declara português.
- O tokenizador é carregado de `meta-llama/Llama-3.2-1B`, repositório com aprovação manual da Meta. Exige conta no Hugging Face, aceite da licença e token. A máquina não tem token do Hugging Face. Existe cópia aberta do mesmo tokenizador (`unsloth/Llama-3.2-1B`), mas usá-la pula o aceite da licença.
- Download dos pesos iniciado às 17:19, em segundo plano.

---

## [2026-09-28] - TADA descartado, sessão encerrada (17:33)

- TADA descartado pelo autor pelo tamanho (9,5 GB). Download interrompido. Lição: o Hugging Face grava os pedaços na pasta compartilhada `hub/blobs`, e apagar a pasta do modelo não libera nada; os quatro blocos (9,5 GB, criados depois das 17:19) foram apagados à mão. Cache voltou a 3,5 GB, disco a 55 GB livres.
- `BOOK_TO_AUDIO_VOZ_PT` comentada no `~/.claude/.env`, para outras sessões que usem a `/audiolivro` não gerarem com uma voz ainda não aprovada e com o defeito do aparo. O motor responde "usa a Dora".
- Código da 0.4.0 fica sem commit até a voz ser aprovada.
- Handover completo em `03-handover-2026-09-28-vozes.md`.

---

## [2026-09-28] - Aparo do fim da frase corrigido e voz aprovada (18:53)

- `aparar()`: limiar de -40 para -55 dB e folga de 30 para 150 ms no fim. Os mesmos 5 min do Serra 2018: o Whisper passou a ouvir "tema." inteiro (0,6 s, colado a "explorado", sem a pausa longa), "Nacional, Capes" com pausa, conferência com 28 trechos e nenhum refeito.
- O autor aprovou esta versão ("está bom, vamos considerar esta"). `BOOK_TO_AUDIO_VOZ_PT` religada no `~/.claude/.env` com `ref-tecnica-rapida`. Versão 0.4.0 publicada.
- Próximo: gerar um capítulo inteiro com esta versão para confirmar em texto longo; depois, notas de rodapé.

