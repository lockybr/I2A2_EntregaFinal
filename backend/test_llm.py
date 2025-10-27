import os
import sys
from pydantic import SecretStr
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

_raw_key = os.environ.get('OPENROUTER_API_KEY')
OPENROUTER_API_KEY = SecretStr(_raw_key) if _raw_key else None
OPENROUTER_MODEL = os.environ.get('OPENROUTER_MODEL', "deepseek/deepseek-chat-v3.1:free")

if not OPENROUTER_API_KEY:
    print("Error: OPENROUTER_API_KEY is not set. Set the environment variable and retry.", file=sys.stderr)
    sys.exit(1)

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

if __name__ == "__main__":
    llm = ChatOpenAI(api_key=OPENROUTER_API_KEY, base_url="https://openrouter.ai/api/v1", model=OPENROUTER_MODEL)
    chain = prompt | llm
    result = chain.invoke({"ocr_text": ocr_text})
    print('Resposta LLM:')
    print(result.content if hasattr(result, "content") else str(result))
