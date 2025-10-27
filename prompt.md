# Desafio Final

Você como especialista em desenvolvimento de aplicações contábeis precisa Desenvolver uma solução inteligente para recuperação e extração automatizada de informações fiscais a partir de documentos como notas fiscais eletrônicas (NF-e), cupons fiscais e documentos similares. A extração será feita a partir de fontes conhecidas, utilizando tecnologias de OCR (Reconhecimento Óptico de Caracteres) e NLP (Processamento de Linguagem Natural) para identificar e estruturar os dados relevantes.

Os requisitos do desafio final são: Recuperar documentos fiscais em fontes conhecidas, Utilizar OCR (Reconhecimento Óptico de Caracteres) em conjunto com NLP (Processamento de Linguagem Natural) para extrair dados relevantes dos 
documentos como:
 • Informações do emitente e destinatário
 • Itens da nota (descrição, quantidade, valor)
 • Impostos (ICMS, IPI, PIS, COFINS)
 • CFOP, CST e outros códigos fiscais

Como principais Desafios os agentes de IA devem ser capaz de se adaptarem a diferentes layouts e formatos de documentos bem como às mudanças legais (ex. IVA)

## Escopo da Extração de Dados

### Informações do Emitente e Destinatário

• Nome/Razão Social;
• CNPJ/CPF;
• Inscrição Estadual;
• Endereço Completo.

### Itens da Nota

 • Descrição dos Produtos ou Serviços;
 • Quantidade;
 • Unidade de Medida;
 • Valor Unitário;
 • Valor Total.

### Tributos e Impostos

 • ICMS (Imposto sobre Circulação de Mercadorias e Serviços);
 • Alíquota;
 • Base de Cálculo;
 • Valor do ICMS;
 • IPI (Imposto sobre Produtos Industrializados);
 • PIS (Programa de Integração Social);
 • COFINS (Contribuição para o Financiamento da Seguridade Social).

### Códigos Fiscais

 • CFOP (Código Fiscal de Operações e Prestações);
 • CST (Código de Situação Tributária);
 • NCM (Nomenclatura Comum do Mercosul).

Itens da Nota
    • Descrição dos Produtos ou Serviços;
    • Quantidade;
    • Unidade de Medida;
    • Valor Unitário;
    • Valor Total;
    • CSOSN (Código de Situação da Operação no Simples Nacional).

### Outros Elementos

 • Número da Nota Fiscal;
 • Chave de Acesso;
 • Data de Emissão;
 • Natureza da Operação;
 • Forma de Pagamento;
 • Valor Total da Nota.

## Construção da Solução Técnica

 • Implementação de OCR com ferramentas como Tesseract.
 
 Aplicação de técnicas de NLP para:
 • Identificação de entidades fiscais (NER);
 • Classificação de seções do documento;
 • Extração de padrões fiscais;
 • Criação de um modelo de validação de dados extraídos;
 • Desenvolvimento de interface de visualização e conferência.

## Integração e Entrega

 • Exportação dos dados para sistemas (ERP, BI, RPA);
 • Geração de relatórios fiscais automatizados.

## Premissas Importantes
 
 • O sistema deve obrigatóriamente fazer uso de Agentes especialistas para executar as atividades CORE, por exemplo, de extração de dados, de OCR, de NLP, de relatórios e etc;
 • Usar um framework para orquestrar a solução, pode ser CrewAI, LangChain ou outro que você, como especialista, entenda que seja melhor adequado;
 • Ter uma interface web moderna e responsiva;
 • Usar uma arquitetura moderna e modular para facilitar a manutenção e evolução da solução.

 ## Documentação
 O repositório do Github deve permitir acesso público e em seu readme.md deve se destacar que o projeto se encontra sob a licença MIT.

 O Relatório do Projeto:
 • Cada grupo deverá gerar um relatório em formato PDF;
 • O arquivo deverá ter o nome: I2A2_Agentes_Inteligentes_Projeto_Final_<Nome_do_Grupo>.pdf
 • No relatório deverá ser apresentado:
 • Nome do Grupo
 • Integrantes do Grupo
 • Descrição do Tema Escolhido (o que foi feito)
 • Público alvo (quem irá utilizar a solução)
 • Justificativa do Tema Escolhido (por que isto é importante, o que agrega de valor ao público alvo)
 • Detalhamento do que foi desenvolvido (quais as funções, como a solução é operada, etc.)
 • Elementos adicionais: tabelas, gráficos, diagramas
 • Link para o repositório do github que contém o projeto

 ## Variáveis de apio
 <NOME_DO_GRUPO> =  Os Promptados
 <TEMA_ESCOLHIDO> =  Extração de Dados  Solução OCR + NLP para Documentos Fiscais
 <INTEGRANTES_DO_GRUPO> = {
    Ricardo: ricardo.florentino@gmail.com,
	Patricia: patricia.correa@meta.com.br,
	Sabrina: sabrina.nascimento@meta.com.br,
	Saulo: saulo.belchior@gmail.com,
	Wilson: wozu2003@gmail.com
 }