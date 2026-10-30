# Integração de Dados e Análise da Relação entre Disponibilidade Hídrica e Preços de Energia Elétrica no Mercado Brasileiro (2021–2026)

**Trabalho de Conclusão de Curso**  
Curso de Engenharia de Computação  
Universidade Tecnológica Federal do Paraná (UTFPR)  
Autora: Amanda Moura Cavalcante  

---

## 1. Contexto e Objetivos

O Sistema Interligado Nacional (SIN) possui matriz predominantemente hidrotérmica, o que confere à disponibilidade hídrica papel determinante sobre os custos marginais de operação e sobre a formação de preços de curto prazo. Em cenários de afluência reduzida e depleção de reservatórios, o acionamento complementar do parque termelétrico eleva significativamente os custos operativos, refletindo-se diretamente no Preço de Liquidação das Diferenças (PLD).

Este projeto desenvolve uma solução de engenharia de dados e análise quantitativa com os seguintes objetivos:
1. **Engenharia de Dados (ETL):** Implementar um pipeline automatizado, reprodutível e com verificações formais de qualidade para extrair, transformar, cruzar e armazenar dados históricos do setor elétrico brasileiro referentes ao período de 2021 a 2026.
2. **Modelagem Dimensional:** Estruturar um banco de dados relacional (SQLite) em esquema estrela, complementado por arquivos analíticos colunares (Parquet) e tabulares (CSV).
3. **Garantia de Qualidade:** Validar a integridade referencial, limites de domínio físico e regras de negócio por meio de testes unitários automatizados.
4. **Análise Estatística e Econométrica:** Quantificar as relações lineares e monotônicas entre armazenamento hidrológico e preços de curto prazo através dos coeficientes de Pearson e Spearman, com geração de representações gráficas em resolução científica (300 DPI).

---

## 2. Fontes de Dados

Os dados brutos utilizados são de acesso público e provêm dos órgãos reguladores e operadores centrais do setor elétrico nacional:

| Órgão | Conjunto de Dados | Métricas Utilizadas | Granularidade Original |
| :--- | :--- | :--- | :--- |
| **ONS** | Energia Armazenada (EAR) | EAR em percentual (`ear_percentual`) e em MWmês (`ear_mwmes`) | Diária |
| **ONS** | Energia Natural Afluente (ENA) | ENA em MWmed (`ena_mwmed`) e em relação à MLT (`ena_percentual_mlt`) | Diária |
| **CCEE** | Preço de Liquidação das Diferenças (PLD) | Valor horário do PLD em R$/MWh (`pld_valor`) | Horária (1h a 24h) |

O escopo geográfico contempla os quatro submercados oficiais do SIN:
- Sudeste / Centro-Oeste (`SE/CO`)
- Sul (`S`)
- Nordeste (`NE`)
- Norte (`N`)

---

## 3. Arquitetura da Solução

O pipeline é estruturado em módulos com separação clara de responsabilidades:

```
[ Ingestão ]         [ Transformação e Qualidade ]          [ Carga e Armazenamento ]
  ONS (EAR/ENA)  -->   Conversão Numérica Defensiva   -->     SQLite (energy_sector.db)
  CCEE (PLD)           Mapeamento Canônico Submercados        Parquet (Armazenamento Colunar)
                       Agregação Temporal (Diária/Horária)    CSV (Exportação e Power BI)
                       Asserções de Qualidade de Dados
                              |
                     [ Camada Analítica ]
                       Testes Automatizados (unittest)
                       Modelagem de Correlação (Pearson/Spearman)
                       Figuras Científicas (300 DPI em docs/figures/)
```

### Detalhamento dos Módulos

- **`src/extractors.py`:** Mecanismo de download automatizado para o ONS e CCEE com controle de cache local em disco, evitando requisições redundantes.
- **`src/transformers.py`:** Tratamento defensivo de caracteres não numéricos e formatação regional brasileira (vírgulas decimais e separadores de milhar), mapeamento de variações de nomenclatura para os quatro submercados oficiais, agregação de médias, mínimos e máximos diários do PLD, e cruzamento relacional via chave composta (`data`, `id_submercado`).
- **`src/loaders.py`:** Persistência dos conjuntos transformados em banco relacional SQLite e arquivos estruturados para consumo analítico.
- **`src/pipeline.py`:** Orquestrador central que executa sequencialmente as etapas de extração, transformação, asserções de qualidade e exportação para horizontes anuais ou multianuais.
- **`main.py`:** Ponto de entrada via interface de linha de comando (CLI) baseada em argumentos formais (`argparse`).
- **`tests/test_pipeline.py`:** Suíte de testes unitários que audita transformações, cálculos e a integridade referencial do banco de dados.
- **`src/analysis.py`:** Módulo estatístico para cálculo de matrizes de correlação, testes de significância estatística ($p$-valor) e geração de gráficos científicos.

---

## 4. Estrutura do Repositório

```text
TCC-Amanda-Moura-Cavalcante/
├── data/
│   ├── raw/                 # Dados brutos em cache local (armazenamento local)
│   └── processed/           # Arquivos Parquet, CSV e banco SQLite (energy_sector.db)
├── docs/
│   └── figures/             # Gráficos de alta resolução para a monografia (300 DPI)
├── notebooks/
│   ├── 01_data_ingestion.ipynb       # Ingestão e validação inicial de formatos
│   ├── 02_data_processing.ipynb      # Limpeza, modelagem dimensional e carga
│   └── 03_statistical_analysis.ipynb # Avaliação estatística e correlações
├── src/
│   ├── __init__.py          # Identificador de pacote Python
│   ├── extractors.py        # Rotinas de ingestão de dados
│   ├── transformers.py      # Transformações e validações de integridade
│   ├── loaders.py           # Persistência relacional e colunar
│   ├── pipeline.py          # Orquestrador do fluxo ETL
│   └── analysis.py          # Análise quantitativa e exportação de figuras
├── tests/
│   ├── __init__.py          # Identificador do pacote de testes
│   └── test_pipeline.py     # Suíte de testes unitários automatizados
├── .gitignore               # Regras de exclusão do controle de versão
├── main.py                  # Ponto de entrada CLI
├── README.md                # Documentação técnica do projeto
└── requirements.txt         # Especificação de dependências do projeto
```

---

## 5. Modelo Dimensional Relacional

O banco de dados relacional `data/processed/energy_sector.db` implementa o esquema estrela (*Star Schema*):

### Tabela Fato: `fato_energia_daily`

| Coluna | Tipo | Restrição | Descrição |
| :--- | :--- | :--- | :--- |
| `data` | DATE | NOT NULL | Data de referência do registro |
| `id_submercado` | VARCHAR(5) | NOT NULL, FK | Identificador canônico do submercado (`SE/CO`, `S`, `NE`, `N`) |
| `ear_percentual` | FLOAT | CHECK (0 <= val <= 100) | Energia armazenada em percentual do volume útil |
| `ear_mwmes` | FLOAT | | Energia armazenada em MWmês |
| `ena_mwmed` | FLOAT | | Energia natural afluente em MWmed |
| `ena_percentual_mlt` | FLOAT | | Afluência relativa à Média de Longo Termo (%) |
| `pld_medio` | FLOAT | CHECK (val >= 0) | Média aritmética das 24 horas do PLD no dia (R$/MWh) |
| `pld_min` | FLOAT | CHECK (val >= 0) | Menor cotação horária do PLD registrada no dia (R$/MWh) |
| `pld_max` | FLOAT | CHECK (val >= 0) | Maior cotação horária do PLD registrada no dia (R$/MWh) |
| `horas_registradas` | INTEGER | CHECK (val = 24) | Número de horas horárias que compuseram a agregação |
| `ano` | INTEGER | NOT NULL | Ano de referência |
| `mes` | INTEGER | NOT NULL | Mês de referência |
| `dia` | INTEGER | NOT NULL | Dia do mês de referência |

**Chave Primária Composta:** `(data, id_submercado)`

### Tabela Dimensão: `dim_submercado`

| Coluna | Tipo | Restrição | Descrição |
| :--- | :--- | :--- | :--- |
| `id_submercado` | VARCHAR(5) | PRIMARY KEY | Código canônico do submercado (`SE/CO`, `S`, `NE`, `N`) |
| `nom_submercado` | VARCHAR(50) | NOT NULL | Nome descritivo oficial do submercado |
| `regiao` | VARCHAR(50) | NOT NULL | Região geográfica principal |

---

## 6. Procedimentos de Reprodução e Execução

### 6.1. Configuração do Ambiente Virtual

O projeto requer Python 3.10 ou superior.

```bash
# Clonar o repositório
git clone https://github.com/amandacavalcante/TCC-Amanda-Moura-Cavalcante.git
cd TCC-Amanda-Moura-Cavalcante

# Criação do ambiente virtual
python -m venv .venv

# Ativação do ambiente virtual
# No Windows:
.venv\Scripts\activate
# No Linux ou macOS:
# source .venv/bin/activate

# Instalação das dependências
pip install -r requirements.txt
```

### 6.2. Execução do Pipeline (CLI)

O arquivo `main.py` disponibiliza interface de linha de comando para controle de execução:

```bash
# Execução completa para todo o período histórico (2021 a 2026):
python main.py

# Execução restrita a um ano específico (exemplo: 2026):
python main.py --year 2026

# Execução em intervalo definido:
python main.py --start 2023 --end 2025

# Execução forçando re-download das bases primárias:
python main.py --force

# Execução preservando a granularidade horária do PLD:
python main.py --granularity hourly
```

### 6.3. Bateria de Testes Automatizados

A verificação do código e da qualidade dos dados processados é realizada com o módulo `unittest`:

```bash
python -m unittest discover tests
```

A suíte audita seis aspectos críticos:
1. `test_01`: Conversão defensiva de strings decimais brasileiras (`1.500,50` para `1500.50`) e tratamento de nulos/ruídos.
2. `test_02`: Convergência de nomenclaturas heterogêneas aos quatro submercados canônicos.
3. `test_03`: Agregação diária de médias e cômputo completo das 24 horas.
4. `test_04`: Bloqueio de duplicatas na chave primária composta `(data, id_submercado)`.
5. `test_05`: Restrição de domínio físico (EAR entre 0% e 100%; PLD estritamente não negativo).
6. `test_06`: Integridade relacional e correspondência de chave estrangeira entre fato e dimensão no SQLite.

### 6.4. Execução da Análise Estatística

A rotina de modelagem estatística e geração de figuras em padrão acadêmico é acionada por:

```bash
python src/analysis.py
```

As quatro figuras geradas são salvas em `docs/figures/`:
- `figura_matriz_correlacao_submercados.png`: Matrizes comparativas de correlação de Spearman por submercado.
- `figura_serie_historica_ear_pld_se_co.png`: Série histórica temporal de eixo duplo (EAR versus PLD) no Sudeste/Centro-Oeste.
- `figura_dispersao_ear_pld.png`: Diagramas de dispersão com curva polinomial de ajuste e discriminação anual.
- `figura_dispersao_ena_pld.png`: Diagramas de dispersão da afluência hidrológica imediata (ENA) versus PLD.

---

## 7. Síntese dos Resultados Estatísticos

A avaliação quantitativa das séries históricas consolidadas (2021 a 2026) fundamenta as seguintes conclusões técnicas:

1. **Correlação Inversa entre Armazenamento e Preço:**  
   Em todos os submercados com capacidade expressiva de regularização plurianual, a correlação entre EAR e PLD é estatisticamente significante ($p < 10^{-100}$) e negativa. No subsistema Sul, o coeficiente de Spearman atinge $\rho = -0,460$; no Sudeste/Centro-Oeste, atinge $\rho = -0,455$. O resultado comprova empiricamente que o esgotamento dos reservatórios eleva o custo marginal de operação e força a escalada dos preços no mercado de curto prazo.

2. **Assimetria Não-Linear e Efeito das Travas Regulatórias:**  
   A correlação monotônica de Spearman supera consistentemente a correlação linear de Pearson em capacidade explicativa. Isso ocorre porque o PLD está sujeito a limites regulatórios de piso (aproximadamente R$ 60,00/MWh) e teto definidos pela ANEEL. Os diagramas de dispersão evidenciam um perfil característico em "L": durante a crise hídrica de 2021, o PLD operou próximo ao teto; nos períodos de recuperação e abundância (2022 e 2023), o preço saturou no piso legal, atenuando a linearidade do modelo de Pearson.

3. **Especificidade Operacional do Subsistema Norte:**  
   Diferente dos demais submercados, no subsistema Norte a correlação de Spearman entre a Energia Natural Afluente (ENA) e o PLD é expressiva ($\rho = -0,505$), suplantando o efeito do EAR ($\rho = -0,173$). Esse comportamento decorre da presença de grandes usinas hidrelétricas a fio d'água (notadamente Belo Monte), cuja reduzida capacidade de acumulação torna a geração dependente do fluxo hidrológico afluente imediato.

---

## 8. Tecnologias Empregadas

| Categoria | Tecnologia | Versão de Referência | Aplicação no Projeto |
| :--- | :--- | :--- | :--- |
| Linguagem | Python | 3.10+ | Desenvolvimento geral da solução |
| Manipulação de Dados | Pandas | 2.2+ | Estruturação e manipulação tabular |
| Computação Numérica | NumPy | 1.26+ | Operações vetoriais e cálculos de suporte |
| Persistência Colunar | PyArrow | 15.0+ | Serialização eficiente em formato Parquet |
| Persistência Relacional | SQLite3 | Padrão Python | Banco de dados relacional embarcado |
| Ingestão Web | Requests / curl_cffi | 2.31+ / 0.7+ | Coleta de dados com contorno a bloqueios |
| Modelagem Quantitativa | SciPy | 1.11+ | Testes de correlação e cálculo de $p$-valores |
| Visualização de Dados | Matplotlib / Seaborn | 3.8+ / 0.13+ | Construção de figuras científicas a 300 DPI |
| Verificação de Código | Unittest | Padrão Python | Bateria de testes unitários automatizados |

---

## 9. Identificação Institucional

- **Trabalho de Conclusão de Curso (TCC)**
- **Instituição:** Universidade Tecnológica Federal do Paraná (UTFPR)
- **Curso:** Engenharia de Computação
- **Autora:** Amanda Moura Cavalcante
- **Ano de Conclusão:** 2026