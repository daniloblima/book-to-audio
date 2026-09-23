# book-to-audio

Versão 0.3.0, de 23/09/2026. O que mudou em cada versão está no [CHANGELOG.md](CHANGELOG.md).

Converte um PDF num MP3 com capítulos, para ouvir num tocador de podcast. Tudo roda no seu Mac, com vozes gratuitas, sem enviar o documento para serviço nenhum.

O problema que resolve: quem tem mais para ler do que tempo para ler costuma ter tempo para ouvir, no carro, na caminhada, lavando louça. Os leitores de tela e os conversores de texto em voz leem o PDF como ele está, com número de página, cabeçalho repetido, afiliação do autor e cada citação "(Martin & Sunley, 2022; Zhu et al., 2019)" no meio da frase. E um player comum de MP3 não lembra onde você parou. O book-to-audio limpa o texto antes de falar, divide o áudio pelas seções do documento e entrega um arquivo que o tocador de podcast trata como um episódio, com capítulos e posição de escuta.

## Como funciona

```
documento.pdf
  │
  ├─ Docling: extrai o texto em ordem de leitura e marca o que é
  │           cabeçalho, rodapé, legenda, nota e fórmula
  ├─ roteiro: decide o que se fala, capítulo por capítulo
  ├─ Kokoro:  sintetiza a voz, localmente
  └─ ffmpeg e mutagen: montam o MP3 e gravam os capítulos
  │
saida/documento/documento.mp3          o áudio, com capítulos
saida/documento/roteiro.txt            o texto exato que foi falado
saida/documento/figuras/Figura 01.png  cada figura e tabela, recortada do PDF
saida/documento/figuras/legendas.txt   as legendas, na ordem
```

O roteiro é a parte própria deste projeto. As outras três etapas usam ferramentas abertas e maduras. Na versão 0.1.0 ele segue estas regras:

- o primeiro capítulo, "Abertura", tem o título, o autor e o resumo;
- da capa só se lê o resumo: nome da revista, ISSN, "To cite this article", palavras-chave, códigos JEL e histórico de submissão ficam de fora;
- cada seção numerada de primeiro nível ("1 Introduction", "2. Literature review") vira um capítulo;
- subseção ("7.1 Distribution of complexity") e título sem número são lidos como subtítulo, com uma pausa antes e depois;
- cabeçalho e rodapé de página, linhas de contato do autor e avisos de licença da editora ficam de fora;
- citações autor-ano entre parênteses saem do áudio, e "Schumpeter (1934)" vira "Schumpeter";
- figuras e tabelas não são lidas: no fim do parágrafo que cita a figura pela primeira vez, o áudio diz "Figure 3, in the figures folder" (ou "Figura 3, na pasta de figuras", em português) e lê a legenda inteira. Figura que o texto nunca cita é anunciada onde está impressa;
- logotipos e imagens sem legenda são ignorados, assim como fórmulas;
- a leitura para na seção de referências, notas, agradecimentos, financiamento ou declaração de conflito.

O arquivo `-roteiro.txt` mostra exatamente o que foi falado. Vale abrir antes de ouvir um documento longo, para conferir se nada importante ficou de fora.

## Requisitos

- Mac com Apple Silicon (M1 ou posterior). Foi testado num M3 Pro com 18 GB de memória. Em Mac Intel e Linux deve funcionar com ajustes, mas não foi testado.
- [Homebrew](https://brew.sh).
- Cerca de 2 GB livres em disco: 1,2 GB do ambiente Python (o Docling traz o PyTorch), 340 MB dos modelos de voz e os modelos de layout que o Docling baixa na primeira execução.

## Instalação

Precisa do [Homebrew](https://brew.sh). Com ele instalado, são dois comandos:

```bash
git clone https://github.com/daniloblima/book-to-audio.git
cd book-to-audio && ./instalar.sh
```

O `instalar.sh` faz, em ordem, e pula o que já estiver feito:

1. instala pelo Homebrew o `ffmpeg` (monta o MP3), o `espeak-ng` (converte o texto em fonemas para a voz) e o `uv` (cuida do ambiente Python sem mexer no Python do sistema);
2. baixa os modelos de voz da página oficial do kokoro-onnx, cerca de 350 MB, e confere a integridade de cada arquivo (`baixar_modelos.sh`). Os modelos ficam em `modelos/`, fora do repositório;
3. cria o ambiente Python com as versões exatas registradas no `uv.lock` (`uv sync`);
4. se o [Claude Code](https://claude.com/claude-code) estiver instalado, liga a skill `/audiolivro` em `~/.claude/skills/`.

Na primeira conversão, o Docling baixa também os seus modelos de análise de layout. Isso acontece uma vez só.

## Uso pelo Claude Code: `/audiolivro`

Com a skill ligada, basta pedir numa sessão nova do Claude Code, em qualquer pasta:

```
/audiolivro transforma em áudio o artigo da Feldman sobre creative destruction
```

Ou sem o comando: "quero ouvir esse PDF no carro", "gera o MP3 desse capítulo". A skill:

1. no primeiro uso, pergunta em que pasta você quer os áudios e grava a resposta em `~/.claude/.env` (`BOOK_TO_AUDIO_SAIDA`). Vale escolher uma pasta sincronizada com o celular, porque é por ela que você vê as figuras enquanto ouve;
2. acha o documento pelo caminho ou pelo nome, com o Spotlight, e pergunta quando houver mais de um candidato;
3. descobre título, autor e língua pela primeira página;
4. monta o roteiro sem gerar voz, confere se sobrou ruído de capa ou de página e mostra capítulos e duração estimada. Se o áudio passar de 1 hora, para e pede confirmação antes de gastar o tempo de síntese;
5. gera a voz e diz onde ficou o MP3.

## Uso pela linha de comando

Um artigo ou capítulo em inglês:

```bash
uv run gerar_audio.py artigo.pdf --lingua en --titulo "Creative Destruction in Place" --autor "Maryann P. Feldman"
```

Um texto em português:

```bash
uv run gerar_audio.py capitulo.pdf --lingua pt --titulo "Impacto socioeconômico da Unicamp" --autor "Serra, Cunha e Laplane"
```

O resultado vai para `<pasta de saída>/<nome do documento>/`: o MP3, o `roteiro.txt` e a pasta `figuras/`. Título e autor são opcionais, e sem eles o áudio anuncia o nome do arquivo. A pasta de saída é `saida/`, dentro do projeto, até você escolher outra com `uv run gerar_audio.py --definir-pasta ~/Audiolivros` (grava em `~/.claude/.env`) ou pela variável de ambiente `BOOK_TO_AUDIO_SAIDA`. Os arquivos intermediários ficam em `.trabalho/`, dentro do projeto, e a extração de um PDF é reaproveitada na conversão seguinte do mesmo arquivo.

Todas as opções:

| Opção | O que faz | Padrão |
|---|---|---|
| `--lingua en` ou `pt` | língua do texto, que define a voz | `en` |
| `--titulo`, `--autor` | anunciados na abertura e gravados nos metadados do MP3 | nome do arquivo |
| `--voz` | troca a voz (ver abaixo) | `af_heart` em inglês, `pf_dora` em português |
| `--saida` | pasta onde cada documento ganha a sua subpasta | a definida, ou `saida/` |
| `--nome` | nome do MP3, sem extensão | nome do arquivo de entrada |
| `--motor say` | usa a voz do próprio macOS no lugar do Kokoro, muito mais rápida e bem mais robótica | `kokoro` |
| `--sem-capitulos-de-figura` | não abre capítulo em cada figura anunciada | capítulos de figura ligados |
| `--identificar` | só mostra páginas, metadados, língua provável e o início do texto | |
| `--so-roteiro` | para depois do roteiro: capítulos, palavras e duração estimada, sem gerar voz | |
| `--mostrar-pasta`, `--definir-pasta` | mostra ou grava a pasta de saída | |

A entrada também pode ser o `.json` ou o `.md` já extraídos pelo Docling (ficam em `.trabalho/<nome>/`), o que permite corrigir o texto à mão antes de gerar a voz. Sem o PDF, as figuras são anunciadas mas não recortadas.

## Vozes

As vozes vêm do [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M), um modelo pequeno, com licença Apache 2.0, que roda no processador sem placa de vídeo. As duas vozes padrão foram escolhidas por escuta, comparando nove vozes em português e cinco em inglês sobre o mesmo parágrafo de texto acadêmico:

- inglês: `af_heart`. Alternativas: `am_michael`, e `bf_emma` para sotaque britânico;
- português: `pf_dora`. Alternativas: `pm_alex` e `pm_santa`.

A lista completa está no [catálogo de vozes do Kokoro](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md). As vozes em português do Kokoro são menos treinadas que as inglesas, e isso se ouve.

## Levando para o celular

O MP3 funciona em qualquer tocador que leia arquivo local. Para ter capítulos e posição de escuta, o projeto foi testado no [Podcast Addict](https://podcastaddict.com), no Android:

1. Copie o MP3 para uma pasta do celular.
2. No Podcast Addict, toque em `+`, escolha "Virtual Podcast" e aponte para essa pasta ([instruções oficiais](https://podcastaddict.com/faq/640)).
3. Cada MP3 da pasta vira um episódio. Os capítulos aparecem no player, e o app guarda o ponto em que você parou.

Os capítulos são gravados no formato ID3v2 (frames CHAP e CTOC), que é o padrão de capítulos em MP3 de podcast. Outros tocadores que leem capítulos devem funcionar, mas só o Podcast Addict foi testado.

Figuras: cada figura anunciada abre um capítulo próprio ("Results · Figure 5"), que vai até a próxima figura ou o fim da seção, então dá para pular direto para ela. A imagem da figura também vai embutida nesse capítulo. O Podcast Addict não mostra essa imagem em arquivo local (testado em 23/09/2026); outros tocadores que exibem arte de capítulo podem mostrar. O caminho que funciona em qualquer tocador é a pasta `figuras/`: se ela estiver numa nuvem sincronizada com o celular, você ouve o anúncio e abre a figura no app da nuvem.

## Desempenho

Medido num M3 Pro, só com o processador:

- extração de um artigo de 17 páginas em duas colunas pelo Docling: cerca de 1 minuto;
- voz do Kokoro: cerca de 5 vezes mais rápida que o tempo real. Um capítulo de 27 páginas deu 76 minutos de áudio, gerados em 15 minutos;
- o MP3 sai a 64 kbps mono, cerca de 27 MB por hora de áudio.

## Limitações conhecidas

- Só PDF. EPUB, AZW3 e DOCX estão planejados.
- Equações são ignoradas em silêncio. O conteúdo das tabelas não é lido, só a legenda.
- A figura só é reconhecida se tiver legenda começando por "Figure", "Fig.", "Table", "Figura", "Tabela", "Quadro" ou "Gráfico" seguido do número.
- Notas de rodapé ainda não são tratadas. O plano é lê-las como um parêntese, no ponto final seguinte à chamada da nota.
- Documentos longos saem num MP3 só. O plano é dividir em partes de até 3 horas.
- A detecção de capítulos depende de seções numeradas. Documento sem numeração sai com um capítulo só, além da abertura.
- A remoção de citações reconhece o formato autor-ano. Citação numérica, como "[12]", continua sendo lida.
- Até aqui, o caminho completo, do PDF ao celular, foi testado com dois documentos em inglês: um capítulo de livro acadêmico de 27 páginas e um artigo de revista de 17 páginas em duas colunas, com sete figuras e duas tabelas.

## O que está no repositório

| Arquivo | O que é |
|---|---|
| `gerar_audio.py` | o programa inteiro: extração, roteiro, voz e montagem |
| `instalar.sh` | instala tudo e liga a skill |
| `skill/SKILL.md` | a skill `/audiolivro` do Claude Code |
| `baixar_modelos.sh` | baixa e confere os modelos de voz |
| `pyproject.toml`, `uv.lock` | dependências, com versões exatas |
| `CHANGELOG.md` | cada versão, o que mudou e por quê, incluindo os problemas encontrados e como foram resolvidos |
| `LICENSE` | licença MIT |

Ficam fora do repositório, pelo `.gitignore`: o ambiente `.venv/`, os modelos, as pastas `saida/` e `.trabalho/` e qualquer PDF ou áudio. Documentos de terceiros costumam ter direitos autorais e não devem ser publicados junto.

## Versões

O projeto segue versionamento semântico. O número do meio sobe a cada funcionalidade nova, o último a cada correção, e a versão 1.0.0 marca o ponto em que o projeto estiver pronto para uso sem acompanhamento. Cada versão tem uma entrada no [CHANGELOG.md](CHANGELOG.md) e uma marca de release no GitHub.

## Créditos

- [Docling](https://github.com/docling-project/docling), da IBM Research, licença MIT: extração de PDF.
- [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M), de hexgrad, licença Apache 2.0: modelo de voz.
- [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx), de thewh1teagle, licença MIT: execução do Kokoro sem PyTorch.
- [eSpeak NG](https://github.com/espeak-ng/espeak-ng), licença GPL 3.0: conversão de texto em fonemas.
- [FFmpeg](https://ffmpeg.org): montagem do MP3.
- [mutagen](https://github.com/quodlibet/mutagen), licença GPL 2.0 ou posterior: gravação dos capítulos com imagem.
- [pypdfium2](https://github.com/pypdfium2-team/pypdfium2), licença Apache 2.0 ou BSD-3: recorte das figuras.

## Licença

MIT. Pode usar, modificar e redistribuir, inclusive comercialmente, mantendo o aviso de copyright. Os modelos e bibliotecas de terceiros listados em Créditos seguem as próprias licenças.
