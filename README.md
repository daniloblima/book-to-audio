# book-to-audio

Versão 0.1.0, de 23/09/2026. O que mudou em cada versão está no [CHANGELOG.md](CHANGELOG.md).

Converte um PDF num MP3 com capítulos, para ouvir num tocador de podcast. Tudo roda no seu Mac, com vozes gratuitas, sem enviar o documento para serviço nenhum.

O problema que resolve: quem tem mais para ler do que tempo para ler costuma ter tempo para ouvir, no carro, na caminhada, lavando louça. Os leitores de tela e os conversores de texto em voz leem o PDF como ele está, com número de página, cabeçalho repetido, afiliação do autor e cada citação "(Martin & Sunley, 2022; Zhu et al., 2019)" no meio da frase. E um player comum de MP3 não lembra onde você parou. O book-to-audio limpa o texto antes de falar, divide o áudio pelas seções do documento e entrega um arquivo que o tocador de podcast trata como um episódio, com capítulos e posição de escuta.

## Como funciona

```
documento.pdf
  │
  ├─ Docling: extrai o texto em ordem de leitura, sem cabeçalho,
  │           rodapé nem número de página
  ├─ roteiro: decide o que se fala, capítulo por capítulo
  ├─ Kokoro:  sintetiza a voz, localmente
  └─ ffmpeg:  monta o MP3 e grava os capítulos
  │
saida/documento.mp3            o áudio, com capítulos
saida/documento-roteiro.txt    o texto exato que foi falado
```

O roteiro é a parte própria deste projeto. As outras três etapas usam ferramentas abertas e maduras. Na versão 0.1.0 ele segue estas regras:

- o primeiro capítulo, "Abertura", tem o título, o autor e o resumo;
- cada seção numerada do documento ("1 Introduction", "2. Literature review") vira um capítulo;
- título de subseção é lido como subtítulo, com uma pausa antes e depois;
- citações autor-ano entre parênteses saem do áudio, e "Schumpeter (1934)" vira "Schumpeter";
- imagens são ignoradas;
- a leitura para na seção de referências, notas, agradecimentos, financiamento ou declaração de conflito.

O arquivo `-roteiro.txt` mostra exatamente o que foi falado. Vale abrir antes de ouvir um documento longo, para conferir se nada importante ficou de fora.

## Requisitos

- Mac com Apple Silicon (M1 ou posterior). Foi testado num M3 Pro com 18 GB de memória. Em Mac Intel e Linux deve funcionar com ajustes, mas não foi testado.
- [Homebrew](https://brew.sh).
- Cerca de 2 GB livres em disco: 1,2 GB do ambiente Python (o Docling traz o PyTorch), 340 MB dos modelos de voz e os modelos de layout que o Docling baixa na primeira execução.

## Instalação

São quatro passos, e cada um roda uma vez só.

1. Instale as ferramentas do sistema pelo Homebrew. O `ffmpeg` monta o MP3, o `espeak-ng` converte o texto em fonemas para a voz e o `uv` cuida do ambiente Python:

```bash
brew install ffmpeg espeak-ng uv
```

2. Baixe o repositório:

```bash
git clone https://github.com/daniloblima/book-to-audio.git
cd book-to-audio
```

3. Baixe os modelos de voz. O script busca os arquivos na página oficial do kokoro-onnx, cerca de 350 MB, e confere a integridade de cada um. Os modelos ficam na pasta `modelos/`, que não vai para o repositório:

```bash
./baixar_modelos.sh
```

4. Crie o ambiente Python. O `uv` instala a versão certa do Python e as bibliotecas com as versões exatas registradas no `uv.lock`, sem mexer no Python do sistema:

```bash
uv sync
```

Na primeira conversão, o Docling baixa também os seus modelos de análise de layout. Isso acontece uma vez só.

## Uso

Um artigo ou capítulo em inglês:

```bash
uv run gerar_audio.py artigo.pdf --lingua en --titulo "Creative Destruction in Place" --autor "Maryann P. Feldman"
```

Um texto em português:

```bash
uv run gerar_audio.py capitulo.pdf --lingua pt --titulo "Impacto socioeconômico da Unicamp" --autor "Serra, Cunha e Laplane"
```

O resultado vai para a pasta `saida/`. Título e autor são opcionais, e sem eles o áudio anuncia o nome do arquivo.

Todas as opções:

| Opção | O que faz | Padrão |
|---|---|---|
| `--lingua en` ou `pt` | língua do texto, que define a voz | `en` |
| `--titulo`, `--autor` | anunciados na abertura e gravados nos metadados do MP3 | nome do arquivo |
| `--voz` | troca a voz (ver abaixo) | `af_heart` em inglês, `pf_dora` em português |
| `--saida` | pasta de saída | `saida/` |
| `--nome` | nome do MP3, sem extensão | nome do arquivo de entrada |
| `--motor say` | usa a voz do próprio macOS no lugar do Kokoro, muito mais rápida e bem mais robótica | `kokoro` |

A entrada também pode ser um `.md` já extraído pelo Docling, o que permite corrigir o texto à mão antes de gerar a voz.

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

## Desempenho

Medido num M3 Pro, só com o processador:

- extração de um artigo de 17 páginas em duas colunas pelo Docling: cerca de 1 minuto;
- voz do Kokoro: cerca de 5 vezes mais rápida que o tempo real. Um capítulo de 27 páginas deu 76 minutos de áudio, gerados em 15 minutos;
- o MP3 sai a 64 kbps mono, cerca de 27 MB por hora de áudio.

## Limitações conhecidas

- Só PDF. EPUB, AZW3 e DOCX estão planejados.
- Figuras, tabelas e equações são ignoradas. A próxima versão deve anunciar "Figura 3, ver anexo", ler a legenda e salvar as imagens numa pasta ao lado do áudio.
- Notas de rodapé ainda não são tratadas. O plano é lê-las como um parêntese, no ponto final seguinte à chamada da nota.
- Documentos longos saem num MP3 só. O plano é dividir em partes de até 3 horas.
- A detecção de capítulos depende de seções numeradas. Documento sem numeração sai com um capítulo só, além da abertura.
- A remoção de citações reconhece o formato autor-ano. Citação numérica, como "[12]", continua sendo lida.
- O travessão às vezes vira hífen na extração ("insight-that"), o que pode alterar a entonação da frase.
- Até aqui, o caminho completo, do PDF ao celular, foi testado com um capítulo de livro acadêmico em inglês, de 27 páginas. A extração também foi testada num artigo de revista em duas colunas, com figuras e tabelas.

## O que está no repositório

| Arquivo | O que é |
|---|---|
| `gerar_audio.py` | o programa inteiro: extração, roteiro, voz e montagem |
| `baixar_modelos.sh` | baixa e confere os modelos de voz |
| `pyproject.toml`, `uv.lock` | dependências, com versões exatas |
| `CHANGELOG.md` | cada versão, o que mudou e por quê, incluindo os problemas encontrados e como foram resolvidos |
| `LICENSE` | licença MIT |

Ficam fora do repositório, pelo `.gitignore`: o ambiente `.venv/`, os modelos, a pasta `saida/` e qualquer PDF ou áudio. Documentos de terceiros costumam ter direitos autorais e não devem ser publicados junto.

## Versões

O projeto segue versionamento semântico. O número do meio sobe a cada funcionalidade nova, o último a cada correção, e a versão 1.0.0 marca o ponto em que o projeto estiver pronto para uso sem acompanhamento. Cada versão tem uma entrada no [CHANGELOG.md](CHANGELOG.md) e uma marca de release no GitHub.

## Créditos

- [Docling](https://github.com/docling-project/docling), da IBM Research, licença MIT: extração de PDF.
- [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M), de hexgrad, licença Apache 2.0: modelo de voz.
- [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx), de thewh1teagle, licença MIT: execução do Kokoro sem PyTorch.
- [eSpeak NG](https://github.com/espeak-ng/espeak-ng), licença GPL 3.0: conversão de texto em fonemas.
- [FFmpeg](https://ffmpeg.org): montagem do MP3 e dos capítulos.

## Licença

MIT. Pode usar, modificar e redistribuir, inclusive comercialmente, mantendo o aviso de copyright. Os modelos e bibliotecas de terceiros listados em Créditos seguem as próprias licenças.
