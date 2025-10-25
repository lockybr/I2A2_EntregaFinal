from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import SecretStr

OPENROUTER_API_KEY = SecretStr("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")
OPENROUTER_MODEL = "deepseek/deepseek-chat-v3.1:free"

ocr_text = "Teste de extração fiscal: Produto X, valor 100, emitente ABC, destinatário DEF, ICMS 18%."

prompt = ChatPromptTemplate.from_template(
    """
Extraia os seguintes campos fiscais do texto abaixo, retornando um JSON estruturado:
- Informações do emitente e destinatário (nome, CNPJ/CPF, inscrição estadual, endereço)
- Itens da nota (descrição, quantidade, unidade, valor unitário, valor total)
- Tributos e impostos (ICMS, IPI, PIS, COFINS, alíquota, base de cálculo, valor)
- Códigos fiscais (CFOP, CST, NCM, CSOSN)
- Outros elementos (número da nota, chave de acesso, data de emissão, natureza da operação, forma de pagamento, valor total)
Texto extraído:
{ocr_text}
"""
)
llm = ChatOpenAI(api_key=OPENROUTER_API_KEY, base_url="https://openrouter.ai/api/v1", model=OPENROUTER_MODEL)
chain = prompt | llm
result = chain.invoke({"ocr_text": ocr_text})
print('Resposta LLM:')
print(result.content if hasattr(result, "content") else str(result))
