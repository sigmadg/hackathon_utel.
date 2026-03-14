"""
RAG (Retrieval-Augmented Generation) para el chat del asistente.
Recupera fragmentos relevantes de documentación sobre métodos de pago,
chats automatizados y plataformas de dropshipping para enriquecer las respuestas del LLM.
"""
import re
from pathlib import Path

# Stopwords en español (reducen ruido en la recuperación)
STOPWORDS = {
    "de", "la", "que", "el", "en", "y", "a", "los", "del", "se", "las", "por", "un", "para",
    "con", "no", "una", "su", "al", "lo", "como", "más", "pero", "sus", "le", "ya", "o",
    "fue", "porque", "esta", "entre", "cuando", "muy", "sin", "sobre", "también", "me",
    "hasta", "hay", "donde", "quien", "desde", "todo", "nos", "durante", "estados", "uno",
    "les", "ni", "contra", "otros", "ese", "eso", "ante", "ellos", "e", "esto", "mí",
    "antes", "algunos", "qué", "unos", "yo", "otro", "otras", "otra", "él", "tanto",
    "esa", "estos", "mucho", "quienes", "nada", "cuánto", "sí", "decir", "solo", "han",
    "ser", "es", "son", "está", "están", "como", "son", "tiene", "tienen", "hacer",
    "puede", "pueden", "cómo", "qué", "cuál", "cuáles", "si", "para", "te", "ti",
}

# Ruta a la carpeta de documentos RAG (relativa al directorio del app)
RAG_DOCS_DIR = Path(__file__).resolve().parent.parent / "rag_docs"
MAX_CHUNKS = 5
MAX_CHARS_CONTEXT = 2800


def _tokenize(text):
    """Normaliza y tokeniza el texto para búsqueda (sin stopwords)."""
    if not text or not isinstance(text, str):
        return set()
    lower = text.lower().strip()
    # Mantener letras, números, acentos (simplificado)
    tokens = re.findall(r"[a-záéíóúñü0-9]+", lower)
    return {t for t in tokens if len(t) > 1 and t not in STOPWORDS}


def _chunk_document(content, doc_id):
    """
    Divide el contenido en chunks por secciones (##) o por párrafos.
    Devuelve lista de (chunk_text, token_set).
    """
    chunks = []
    # Dividir por ## o por doble salto
    parts = re.split(r"\n##\s+|\n\n+", content)
    for part in parts:
        part = part.strip()
        if not part or len(part) < 40:
            continue
        # Limpiar líneas de solo # o vacías al inicio
        part = re.sub(r"^#+\s*\n?", "", part).strip()
        if len(part) < 40:
            continue
        tokens = _tokenize(part)
        if tokens:
            chunks.append((part, tokens, doc_id))
    return chunks


def _load_rag_documents():
    """Carga todos los .md de rag_docs y devuelve lista de (doc_id, content)."""
    docs = []
    if not RAG_DOCS_DIR.is_dir():
        return docs
    for path in sorted(RAG_DOCS_DIR.glob("*.md")):
        try:
            content = path.read_text(encoding="utf-8")
            doc_id = path.stem
            docs.append((doc_id, content))
        except Exception:
            continue
    return docs


def _build_index():
    """Construye el índice de chunks en memoria."""
    docs = _load_rag_documents()
    index = []
    for doc_id, content in docs:
        index.extend(_chunk_document(content, doc_id))
    return index


def _score_chunk(query_tokens, chunk_tokens, chunk_text):
    """
    Puntuación simple: cantidad de tokens de la query que aparecen en el chunk.
    Opcional: bonus si el chunk tiene muchos términos en común (cobertura).
    """
    if not query_tokens:
        return 0
    overlap = query_tokens & chunk_tokens
    return len(overlap) / len(query_tokens)


def get_context_for_query(query, top_k=MAX_CHUNKS, max_chars=MAX_CHARS_CONTEXT):
    """
    Dado el mensaje del usuario, recupera los fragmentos más relevantes de la documentación RAG.
    Devuelve una cadena con el contexto para inyectar en el prompt del LLM, o cadena vacía si no hay nada relevante.
    """
    if not query or not isinstance(query, str) or len(query.strip()) < 2:
        return ""

    query_clean = query.strip()
    query_tokens = _tokenize(query_clean)
    if not query_tokens:
        return ""

    index = _build_index()
    if not index:
        return ""

    # Puntuar cada chunk
    scored = []
    for chunk_text, chunk_tokens, doc_id in index:
        score = _score_chunk(query_tokens, chunk_tokens, chunk_text)
        if score > 0:
            scored.append((score, chunk_text, doc_id))

    # Ordenar por puntuación descendente
    scored.sort(key=lambda x: (-x[0], -len(x[1])))

    # Construir contexto con top_k chunks sin pasarse de max_chars
    parts = []
    total_chars = 0
    for _, text, doc_id in scored[: top_k * 2]:  # tomar más por si acorto
        if total_chars + len(text) + 2 > max_chars:
            if len(text) > 200:
                text = text[: max_chars - total_chars - 50].rsplit(" ", 1)[0] + "..."
            if total_chars + len(text) > max_chars:
                break
        parts.append(f"[{doc_id}]\n{text}")
        total_chars += len(text) + 2
        if len(parts) >= top_k:
            break

    if not parts:
        return ""

    return "\n\n---\n\n".join(parts)
