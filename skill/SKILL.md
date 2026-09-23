---
name: audiolivro
description: Transforma um PDF (artigo, capítulo, livro, relatório) num MP3 com capítulos para ouvir num tocador de podcast, com voz local e gratuita, limpando cabeçalho, rodapé, número de página e citações, e anunciando figuras e tabelas com a legenda. Use sempre que o usuário quiser ouvir um documento em vez de ler, mesmo sem dizer "audiolivro" — "transforma esse PDF em áudio", "quero escutar esse artigo no carro", "gera o MP3 desse capítulo", "vira podcast", "lê isso pra mim em voz alta num arquivo", "manda pro Podcast Addict". Não use para transcrever áudio em texto, que é o caminho inverso.
---

# /audiolivro — documento para MP3 com capítulos

O motor é o `gerar_audio.py`, na raiz do repositório book-to-audio. Ele extrai o texto com o Docling, monta um roteiro (o que se fala, capítulo por capítulo), sintetiza com a voz Kokoro e grava o MP3 com capítulos. Esta skill conduz a conversa em volta dele: descobre o que o usuário quer ouvir, confere o roteiro antes de gastar tempo de síntese e entrega o resultado.

Todos os comandos abaixo usam a raiz do repositório:

```bash
REPO="$(dirname "$(readlink -f ~/.claude/skills/audiolivro)")"
cd "$REPO" && uv run gerar_audio.py <opções>
```

Se o `uv` não existir ou a pasta `modelos/` estiver vazia, a instalação não terminou: indique `./instalar.sh` na raiz do repositório e pare.

## Passo 1 — Pasta de saída

```bash
uv run gerar_audio.py --mostrar-pasta
```

Se vier `escolhida pelo usuário: não`, é o primeiro uso nesta máquina. Pergunte onde ele quer os áudios antes de seguir. Cada documento vai ganhar uma subpasta ali, com o MP3, o `roteiro.txt` e uma pasta `figuras/`. Vale sugerir uma pasta sincronizada com o celular, porque as figuras não são lidas em voz alta e o jeito de vê-las enquanto ouve é abrir essa pasta no telefone. Grave a resposta, mesmo que seja o padrão, para não perguntar de novo:

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

**Se o documento já tiver sido convertido,** haverá uma pasta com o nome dele na pasta de saída. Diga que o áudio já existe e de quando (data do MP3), e pergunte se ele quer ouvir o existente ou gerar de novo. Não descreva o áudio antigo como se fosse o resultado deste pedido.

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

## Passo 4 — Roteiro, sem voz

```bash
uv run gerar_audio.py "<arquivo.pdf>" --lingua <en|pt> --titulo "<título>" \
  --autor "<autor>" --nome "<nome>" --so-roteiro
```

A extração leva de um a vários minutos, conforme o tamanho, e fica guardada: a síntese no passo 5 não repete. A última linha começa com `RESUMO` e traz capítulos, palavras, duração estimada, tempo de geração estimado e figuras.

Abra o `roteiro.txt` e leia o começo de dois ou três capítulos. Você está procurando o que não deveria ser falado: nome da revista, ISSN, afiliação do autor, número de página solto, linha repetida em toda página, texto de dentro de gráfico. Se o log disser `ATENÇÃO: ... palavras anormalmente longas`, a extração perdeu espaços e o áudio vai sair ruim. Achou problema, conte ao usuário com um exemplo do trecho antes de sintetizar.

**Quando parar para confirmar.** Até 60 minutos de duração estimada, siga direto: o custo de errar é pequeno e regerar é rápido. Acima disso, pare e mostre ao usuário capítulos, duração e tempo de geração. Um livro de dez horas leva umas duas horas de síntese, e vale ele olhar o roteiro antes.

## Passo 5 — Voz e entrega

Rode o mesmo comando do passo 4 sem `--so-roteiro`, em segundo plano, e diga ao usuário quanto tempo deve levar. Acompanhe até aparecer `MP3 pronto` no log e só então entregue: o usuário quer o arquivo, não a promessa de que ele vai sair, e uma sessão que termina antes pode levar a síntese junto. A voz padrão é `af_heart` em inglês e `pf_dora` em português, escolhidas por escuta. Só passe `--voz` se o usuário pedir outra.

Ao terminar, a última linha do log diz `MP3 pronto`, com duração e número de capítulos. Entregue em poucas linhas:

- onde está o MP3 e a pasta `figuras/`, se houver figuras;
- duração e capítulos;
- como ouvir: copiar o MP3 para a pasta que o tocador de podcast lê. No Podcast Addict, é a pasta de um "Virtual Podcast"; ele guarda a posição de escuta e mostra os capítulos.

## Quando algo dá errado

Contorne para entregar o áudio e registre o defeito, sem editar o motor nem esta skill no meio do uso: conserto feito durante uma entrega não é testado. Anote em `$REPO/BACKLOG.md` (crie se não existir) com a data, o documento, o que aconteceu e um trecho do roteiro ou do log como evidência. Se o defeito for do código e não do documento, sugira ao usuário abrir uma issue em https://github.com/daniloblima/book-to-audio/issues, sem anexar o PDF, que pode ter direitos autorais.
