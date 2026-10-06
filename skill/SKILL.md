---
name: audiolivro
description: Transforma um PDF (artigo, capítulo, livro, relatório) num MP3 com capítulos para ouvir num tocador de podcast, com voz local e gratuita, ou num EPUB para ler no Kindle, com as figuras e tabelas no ponto em que o texto as chama e as notas de rodapé abrindo em janela. Limpa cabeçalho, rodapé e número de página nos dois casos. Use sempre que o usuário quiser ouvir um documento em vez de ler, ou levar um PDF para o Kindle, mesmo sem dizer "audiolivro" — "transforma esse PDF em áudio", "quero escutar esse artigo no carro", "gera o MP3 desse capítulo", "vira podcast", "manda pro Podcast Addict", "quero ler isso no Kindle", "manda pro Kindle", "gera um EPUB desse livro", "esse PDF fica ruim no Kindle". Não use para transcrever áudio em texto, que é o caminho inverso.
---

# /audiolivro — documento para MP3 com capítulos ou EPUB para o Kindle

São dois scripts na raiz do repositório book-to-audio, sobre a mesma extração do Docling, que é feita uma vez e reaproveitada:

- `gerar_audio.py` monta um roteiro (o que se fala, capítulo por capítulo), sintetiza a voz e grava o MP3 com capítulos;
- `gerar_kindle.py` monta o texto de leitura, com citações, notas, fórmulas e referências, e grava um EPUB com cada figura e tabela logo depois do parágrafo que a cita.

Esta skill conduz a conversa em volta deles: descobre o que o usuário quer e em que formato, confere o resultado antes de entregar e diz como ouvir ou como mandar ao Kindle.

Todos os comandos abaixo usam a raiz do repositório:

```bash
REPO="$(dirname "$(readlink -f ~/.claude/skills/audiolivro)")"
cd "$REPO" && uv run gerar_audio.py <opções>     # ou gerar_kindle.py
```

Se o `uv` não existir ou a pasta `modelos/` estiver vazia, a instalação não terminou: indique `./instalar.sh` na raiz do repositório e pare. O EPUB precisa também do Pandoc (`brew install pandoc`); o `gerar_kindle.py` avisa se faltar.

## Passo 0 — Formato

Decida se o pedido é de áudio, de Kindle ou dos dois. Quando a frase já diz ("quero ouvir", "manda pro Kindle"), siga sem perguntar. Quando não diz ("transforma esse PDF", "faz aquele livro"), pergunte numa linha: áudio, Kindle ou os dois. Os passos 1 a 3 valem para os dois formatos; depois, o áudio segue pelos passos 4 e 5 e o Kindle pelo passo 6. Nos dois, faça o Kindle primeiro, porque sai em segundos depois da extração, entregue o EPUB e só então rode o áudio em segundo plano.

## Passo 1 — Pasta de saída

```bash
uv run gerar_audio.py --mostrar-pasta
```

Se vier `escolhida pelo usuário: não`, é o primeiro uso nesta máquina. Pergunte onde ele quer os áudios antes de seguir. Cada documento vai ganhar uma subpasta ali, com o MP3, o `roteiro.txt` e uma pasta `figuras/`, e o EPUB quando ele pedir a versão para o Kindle. Vale sugerir uma pasta sincronizada com o celular, porque as figuras não são lidas em voz alta e o jeito de vê-las enquanto ouve é abrir essa pasta no telefone. Grave a resposta, mesmo que seja o padrão, para não perguntar de novo:

```bash
uv run gerar_audio.py --definir-pasta "<caminho>"
```

## Passo 2 — Achar o documento

Se o usuário deu o caminho, use. Se deu só um nome ("o capítulo da Feldman", "aquele artigo sobre complexidade regional"), procure pelo Spotlight:

```bash
mdfind -name "<termo>" 2>/dev/null | grep -iE '\.(pdf|epub|azw3|kfx|docx|mobi)$' | head -20
```

**Com mais de um arquivo, liste e pergunte qual usar, antes de extrair qualquer coisa.** A escolha é do usuário porque só ele sabe qual edição quer ouvir: a do Kindle que ele está lendo, a da editora, a tradução. Critério técnico seu (mais páginas, texto mais limpo) não substitui isso, e uma cópia de origem duvidosa (nome de site de download, "cópia") nunca é escolha que se faz em nome dele. Extrair antes de confirmar desperdiça minutos num arquivo que pode ser descartado.

Hoje o motor aceita só PDF. Se entre os candidatos houver EPUB, AZW3, KFX, DOCX ou MOBI, diga que esses formatos ainda não são aceitos, para ele não esperar que você converta por conta própria.

**Se o documento já tiver sido convertido,** haverá uma pasta com o nome dele na pasta de saída. Diga que o áudio ou o EPUB já existe e de quando (data do arquivo), e pergunte se ele quer o existente ou gerar de novo. Não descreva o arquivo antigo como se fosse o resultado deste pedido.

**Capítulo de um livro.** Se ele pedir um capítulo e só houver o PDF do livro inteiro, liste os capítulos pelo sumário do próprio livro, com a faixa de páginas do PDF de cada um:

```bash
uv run gerar_kindle.py "<livro.pdf>" --nome "<nome do livro>" --capitulos
```

A primeira vez extrai o livro inteiro (416 páginas levaram 5 min 43 s); depois, qualquer capítulo sai em segundos, com `--paginas <início>-<fim>` e `--nome` do capítulo. Livro sem sumário reconhecido não lista: aí procure as páginas no PDF. Hoje a faixa de páginas só existe no `gerar_kindle.py`; para o áudio de um capítulo, ainda é preciso recortar o PDF.

## Passo 3 — Identificar título, autor e língua

```bash
uv run gerar_audio.py "<arquivo.pdf>" --identificar
```

A saída traz páginas, metadados, a língua provável e o início da primeira página. Os metadados costumam vir sujos (nomes grudados com afiliações, título truncado) e às vezes são da editora e não do texto. Decida pelo que se lê na primeira página, porque é o que o autor escreveu:

- **título**: o título do texto, sem subtítulo longo;
- **autor**: forma curta, como se diria em voz alta ("Maryann P. Feldman", "Pinheiro, Balland, Boschma e Hartmann");
- **língua**: `en` ou `pt`. Ela escolhe a voz e a língua do anúncio das figuras, então errar aqui estraga o áudio inteiro;
- **nome da pasta e do MP3**: `Sobrenome Ano - Título curto`, que se lê bem na lista do tocador.

Se a primeira página vier sem texto, o PDF é escaneado e o motor não tem OCR: avise e pare.

## Passo 4 — Áudio: roteiro, sem voz

```bash
uv run gerar_audio.py "<arquivo.pdf>" --lingua <en|pt> --titulo "<título>" \
  --autor "<autor>" --nome "<nome>" --so-roteiro
```

A extração leva de um a vários minutos, conforme o tamanho, e fica guardada: a síntese no passo 5 não repete. A última linha começa com `RESUMO` e traz capítulos, palavras, duração estimada, tempo de geração estimado e figuras.

Abra o `roteiro.txt` e leia o começo de dois ou três capítulos. Você está procurando o que não deveria ser falado: nome da revista, ISSN, afiliação do autor, número de página solto, linha repetida em toda página, texto de dentro de gráfico. Se o log disser `ATENÇÃO: ... palavras anormalmente longas`, a extração perdeu espaços e o áudio vai sair ruim. Achou problema, conte ao usuário com um exemplo do trecho antes de sintetizar.

**Quando parar para confirmar.** Até 60 minutos de duração estimada, siga direto: o custo de errar é pequeno e regerar é rápido. Acima disso, pare e mostre ao usuário capítulos, duração e tempo de geração. Um livro de dez horas leva umas duas horas de síntese, e vale ele olhar o roteiro antes.

## Passo 5 — Áudio: voz e entrega

Rode o mesmo comando do passo 4 sem `--so-roteiro`, em segundo plano, e diga ao usuário quanto tempo deve levar. Acompanhe até aparecer `MP3 pronto` no log e só então entregue: o usuário quer o arquivo, não a promessa de que ele vai sair, e uma sessão que termina antes pode levar a síntese junto. O motor escolhe a voz sozinho (`--motor auto`): em português, a voz do próprio usuário pelo OmniVoice, se ele gravou uma referência (`--mostrar-pasta` diz se há); sem referência, e em inglês, o Kokoro (`pf_dora` e `af_heart`). Com o OmniVoice a geração leva cerca de duas vezes a duração do áudio (40 minutos de áudio em 82 minutos, medido em 28/09/2026), porque o texto vai em trechos curtos e cada um é conferido pelo Whisper; avise o usuário desse tempo antes. O log mostra o progresso a cada 50 trechos. Só passe `--voz` ou `--motor` se ele pedir outra voz.

Ao terminar, a última linha do log diz `MP3 pronto`, com duração e número de capítulos. Entregue em poucas linhas:

- onde está o MP3 e a pasta `figuras/`, se houver figuras;
- duração e capítulos;
- com o OmniVoice, o resumo da conferência (última linha com `conferência:`). Se houver trechos incompletos, diga quantos e que estão listados em `conferencia.txt`, na pasta do documento, com o texto e o que foi ouvido;
- como ouvir: copiar o MP3 para a pasta que o tocador de podcast lê. No Podcast Addict, é a pasta de um "Virtual Podcast"; ele guarda a posição de escuta e mostra os capítulos.

## Passo 6 — Kindle: EPUB e envio

```bash
uv run gerar_kindle.py "<arquivo.pdf>" --lingua <en|pt> --titulo "<título>" \
  --autor "<autor>" --nome "<nome>" [--livro | --paginas <início>-<fim>]
```

`--livro` é para livro inteiro: os capítulos vêm do sumário do próprio livro e a numeração das figuras recomeça a cada capítulo. `--paginas` é para um capítulo tirado de um livro (passo 2). Sem nenhum dos dois, o documento é tratado como artigo ou capítulo avulso, e a folha de rosto que a editora acrescenta ao PDF baixado sai.

O log diz onde ficou o EPUB e o tamanho. Antes de entregar, confira:

- a linha `capítulos; parágrafos; imagens; notas: X casadas, Y no fim do parágrafo`. As notas do fim do parágrafo abrem normalmente, só que a chamada fica no fim do parágrafo, e não no ponto exato;
- se apareceu `AVISO: ... figuras citadas não colocadas`; se sim, diga quais;
- o tamanho: acima de 50 MB o e-mail da Amazon recusa o anexo;
- o `posicoes.txt`, em `.trabalho/<nome>/kindle/`, que diz depois de qual trecho cada figura e tabela entrou. Olhe duas ou três: a frase anterior deve citar a figura.

Entregue em poucas linhas:

- onde está o EPUB;
- capítulos, figuras e notas, com as que ficaram no fim do parágrafo, se houver;
- como mandar: e-mail para o endereço @kindle.com dele, com o EPUB anexo e o assunto em branco (a Amazon sempre converte EPUB; o "convert" no assunto só vale para PDF), ou o arquivo arrastado em amazon.com/sendtokindle. O endereço fica na Amazon, em Conteúdo e dispositivos, Preferências, Configurações de documentos pessoais, e o remetente precisa estar na lista de e-mails aprovados;
- se for a versão corrigida de um EPUB já mandado, apagar a anterior no Kindle antes, senão aparecem as duas.

## Quando algo dá errado

Contorne para entregar o áudio ou o EPUB e registre o defeito, sem editar o motor nem esta skill no meio do uso: conserto feito durante uma entrega não é testado. Anote em `$REPO/BACKLOG.md` (crie se não existir) com a data, o documento, o que aconteceu e um trecho do roteiro ou do log como evidência. Se o defeito for do código e não do documento, sugira ao usuário abrir uma issue em https://github.com/daniloblima/book-to-audio/issues, sem anexar o PDF, que pode ter direitos autorais.
