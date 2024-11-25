import streamlit as st
from crewai import LLM
import PyPDF2
import numpy as np
import docx
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
import litellm

# Função para extrair texto do PDF
def extract_text_from_pdf(file):
    pdf_reader = PyPDF2.PdfReader(file)
    text = ''
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

# Função para extrair texto de um arquivo DOCX usando leitura em buffer
def extract_text_from_docx(file):
    doc = docx.Document(file)
    text = []
    buffer_size = 100  # Definir o tamanho do buffer
    buffer = []
    for paragraph in doc.paragraphs:
        buffer.append(paragraph.text)
        if len(buffer) >= buffer_size:
            text.append('\n'.join(buffer))
            buffer = []
    if buffer:
        text.append('\n'.join(buffer))
    return '\n'.join(text)

# Função para dividir o texto em chunks
def chunk_text(text, max_chunk_size=15000):
    words = text.split()
    chunks = []
    current_chunk = []
    current_size = 0

    for word in words:
        word_size = len(word.encode('utf-8'))
        if current_size + word_size > max_chunk_size:
            chunks.append(' '.join(current_chunk))
            current_chunk = [word]
            current_size = word_size
        else:
            current_chunk.append(word)
            current_size += word_size

    if current_chunk:
        chunks.append(' '.join(current_chunk))

    return chunks

# Configuração do modelo LLM
llm = None

# Função para configurar o LLM com a API Key
def configure_llm(api_key):
    global llm
    llm = LLM(model="gpt-4", api_key=api_key)

# Função para chamada ao LLM com controle de taxa e backoff exponencial
def call_llm_with_exponential_backoff(chunk, question, max_retries=5):
    messages = [{"role": "system", "content": chunk}, {"role": "user", "content": question}]
    retries = 0
    backoff_time = 1  # Tempo inicial de espera em segundos
    while retries < max_retries:
        try:
            return llm.call(messages=messages)
        except litellm.RateLimitError:
            retries += 1
            time.sleep(backoff_time)  # Esperar antes de tentar novamente
            backoff_time *= 2  # Dobrar o tempo de espera a cada tentativa
    raise Exception("Exceeded maximum retries due to rate limit.")

# Função para processar pergunta usando o LLM com controle de taxa
async def process_question_with_llm_async(contract_text, question, _progress_bar):
    if not llm:
        st.warning("LLM não configurado. Por favor, registre a API KEY.")
        return ""
    chunks = chunk_text(contract_text, max_chunk_size=500)  # Ajustar o tamanho dos chunks para 500 tokens
    responses = []
    with ThreadPoolExecutor(max_workers=5) as executor:  # Ajustar max_workers para 5
        futures = [executor.submit(call_llm_with_exponential_backoff, chunk, question) for chunk in chunks]
        for future in futures:
            response = future.result()
            responses.append(response)
            _progress_bar.progress(len(responses) / len(chunks))  # Atualizar a barra de progresso
    return " ".join(responses)

# Função para extrair informações específicas do contrato
def extract_contract_info(contract_text):
    # Aqui você pode implementar a lógica para extrair as informações específicas do contrato
    # Por enquanto, vamos apenas retornar um texto de exemplo
    return "Informações do contrato: Identificação das Partes, Termos e Condições, Datas Importantes, etc."

# Configuração do Streamlit
st.set_page_config(page_title="Interpretador de Contratos")

# Verificar se a API Key está armazenada no st.session_state
# st.write(st.session_state)

# Configurar o LLM no início do aplicativo, se a API Key estiver presente
if 'api_key' in st.session_state and st.session_state['api_key']:
    configure_llm(st.session_state['api_key'])

# Barra lateral
st.sidebar.title("Configurações")
if 'api_key' not in st.session_state:
    st.session_state['api_key'] = ''
api_key = st.sidebar.text_input("Insira sua API Key:", value=st.session_state['api_key'], type="password")

# Configurar o LLM assim que a API Key for registrada
if st.sidebar.button("Registrar API Key"):
    if api_key:
        st.session_state['api_key'] = api_key  # Persistir a API Key
        configure_llm(api_key)
        st.sidebar.success("API Key registrada com sucesso!")
    else:
        st.sidebar.error("Por favor, insira uma API Key válida.")

# Instruções de Uso com bullets animados
st.sidebar.markdown("""
<ul style='list-style-type: circle;'>
    <li style='animation: fadeIn 1s ease-in;'>Ative sua API KEY</li>
    <li style='animation: fadeIn 1s ease-in 0.5s;'>Selecione o contrato no formato Word ou PDF</li>
    <li style='animation: fadeIn 1s ease-in 1s;'>Faça suas perguntas sobre os contratos</li>
    <li style='animation: fadeIn 1s ease-in 1.5s;'>Caso necessite, carregue outro contrato</li>
</ul>
<style>
@keyframes fadeIn {
  from {opacity: 0;}
  to {opacity: 1;}
}
</style>
""", unsafe_allow_html=True)

st.sidebar.info("Instruções sobre como usar o aplicativo...")

# Título e subtítulo
st.markdown('<h1 style="color: lightblue; background-color: darkblue; width: 100%; text-align: center; padding: 20px;">Interpretador de Contratos</h1>', unsafe_allow_html=True)
st.markdown('<h2 style="text-align: center;">Criado por Mauro de Souza Guimarães</h2>', unsafe_allow_html=True)

# Upload do arquivo PDF ou DOCX
uploaded_file = st.file_uploader("Carregar contrato", type=["pdf", "docx"])

# Barra de progresso para carregamento do contrato
progress_bar = st.progress(0)

if uploaded_file is not None:
    with st.spinner('Carregando contrato...'):
        if uploaded_file.type == "application/pdf":
            contract_text = extract_text_from_pdf(uploaded_file)
        elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            contract_text = extract_text_from_docx(uploaded_file)
        else:
            st.error("Tipo de arquivo não suportado.")
            contract_text = ""
        progress_bar.progress(100)
        st.success('Contrato carregado com sucesso!')

# Verificação da configuração do LLM antes de usar
if not llm:
    st.warning("LLM não configurado. Por favor, registre a API KEY antes de prosseguir.")
else:
    # Campo para perguntas
    question = st.text_area("Faça uma pergunta sobre o contrato:")

    # Barra de progresso para processamento da resposta
    response_progress_bar = st.progress(0)

    # Campo de resposta
    if st.button("Enviar Pergunta"):
        if uploaded_file is not None and question:
            with st.spinner('Processando pergunta...'):
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                response = loop.run_until_complete(process_question_with_llm_async(contract_text, question, response_progress_bar))
                st.write(response)
        else:
            st.warning("Por favor, carregue um contrato e faça uma pergunta.")

    # Botão para informações do contrato
    if st.button("Informações do Contrato"):
        contract_text = extract_text_from_pdf(uploaded_file) if uploaded_file.type == "application/pdf" else extract_text_from_docx(uploaded_file)
        contract_info = extract_contract_info(contract_text)
        st.write(contract_info)

    # Botão para carregar novo contrato
    if st.button("Carregar novo Contrato"):
        st.experimental_rerun()
