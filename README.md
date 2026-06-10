# Análise de Vigas de Euler-Bernoulli

Programa em Python para análise de vigas pelo método das diferenças finitas, desenvolvido para a Avaliação 3 da disciplina de Programação de Métodos Numéricos aplicados à Engenharia Civil.

O script calcula deslocamentos, esforços internos e tensões normais máximas de flexão para vigas com diferentes geometrias, materiais, carregamentos e vinculações.

## Funcionalidades

- Seleção do comprimento da viga e da seção transversal:
  - retangular;
  - circular;
  - Perfil I simétrico.
- Cálculo das propriedades geométricas:
  - área `A`;
  - momento de inércia `Iyy`;
  - distância `zmax` até a fibra extrema.
- Seleção das propriedades do material:
  - módulo de elasticidade `E`;
  - tensão limite `sigma_y`.
- Inclusão de qualquer número de cargas verticais:
  - cargas concentradas `P`;
  - cargas distribuídas lineares `q`, variando de `(x1, q1)` até `(x2, q2)`.
- Definição de vínculos:
  - apoios;
  - engastes nos extremos;
  - extremos livres;
  - apoios internos.
- Solução de `w(x)` por diferenças finitas a partir da equação da linha elástica.
- Cálculo numérico de:
  - esforço cortante `Q(x)`;
  - momento fletor `M(x)`;
  - razão `sigma_max / sigma_y`.
- Geração automática de:
  - tabela `.csv` com os resultados;
  - figura `.png`;
  - figura `.pdf`.

## Método Numérico

A formulação resolve a equação diferencial da viga de Euler-Bernoulli:

```text
d4w(x)/dx4 = q(x)/(E I)
```

onde `q(x)` representa a soma das cargas distribuídas e das cargas concentradas aproximadas na malha por uma carga equivalente `P/dx` no nó mais próximo.

Depois de obtido o deslocamento `w(x)`, o programa calcula:

```text
M(x) = -E I w''(x)
Q(x) = dM(x)/dx
sigma_max(x) = |M(x)| zmax / I
```

## Requisitos

- Python 3.10 ou superior
- NumPy
- Matplotlib

Instale as dependências com:

```bash
python -m pip install -r requirements.txt
```

## Como Executar

No terminal, dentro da pasta do projeto:

```bash
python Avaliação-3.py
```

No Windows PowerShell:

```powershell
python .\Avaliação-3.py
```

O programa solicitará os dados da viga em etapas:

1. comprimento e seção transversal;
2. material;
3. vínculos;
4. cargas;
5. opção de exibir ou não a janela do Matplotlib.

## Exemplo Automático

Para rodar um caso de teste pronto:

```bash
python Avaliação-3.py --exemplo
```

Para rodar o exemplo e abrir a janela do Matplotlib:

```bash
python Avaliação-3.py --exemplo --mostrar
```

## Arquivos Gerados

Após a execução, o programa cria:

- `resultados_viga.csv`: tabela com `x`, `q`, `w`, `Q`, `M`, `sigma` e `sigma/sigma_y`;
- `resultado_viga.png`: plotagem final em imagem;
- `resultado_viga.pdf`: plotagem final em PDF.

Esses arquivos são resultados de execução e não fazem parte do código-fonte versionado.

## Convenção de Sinais

- Cargas positivas atuam para baixo.
- Deslocamentos positivos são para baixo.
- O eixo `x` vai da esquerda para a direita, de `0` até `L`.
- O momento fletor segue a convenção `M(x) = -E I w''(x)`.

## Estrutura do Repositório

```text
.
├── Avaliação-3.py
├── README.md
├── LICENSE
├── requirements.txt
├── .gitignore
└── .gitattributes
```

## Licença

Este projeto não é open source.

Todos os direitos são reservados aos autores. Não é concedida permissão para uso, cópia, modificação, publicação, distribuição, sublicenciamento ou criação de trabalhos derivados sem autorização prévia por escrito dos detentores dos direitos autorais.

Consulte o arquivo `LICENSE` para os termos completos.

## Observações

A qualidade dos resultados depende do refinamento da malha de diferenças finitas. Para cargas concentradas, recomenda-se usar uma malha suficientemente refinada, pois a força pontual é representada numericamente como uma carga distribuída equivalente aplicada ao nó mais próximo.

Integrantes: Maurício Meucci e Luis Eduardo Aires.
