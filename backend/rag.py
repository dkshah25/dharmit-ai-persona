import os
import json
import shutil
import math
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database")
COLLECTION_NAME = "persona_kb"

def tokenize(text: str) -> list[str]:
    import re
    return re.findall(r'[a-zA-Z0-9_]+', text.lower())

class TFIDFEmbeddings(Embeddings):
    """
    Pure-python local TF-IDF Embeddings model to avoid external API calls/quota limits.
    """
    def __init__(self, vocab=None, idfs=None):
        self.vocab = vocab or []
        self.idfs = idfs or {}
        self.word_to_idx = {word: idx for idx, word in enumerate(self.vocab)}
        
    def fit(self, texts: list[str]):
        import math
        tokenized_docs = [tokenize(text) for text in texts]
        vocab_set = set()
        for doc in tokenized_docs:
            vocab_set.update(doc)
        self.vocab = sorted(list(vocab_set))
        self.word_to_idx = {word: idx for idx, word in enumerate(self.vocab)}
        
        self.idfs = {}
        N = len(texts)
        for word in self.vocab:
            df = sum(1 for doc in tokenized_docs if word in doc)
            self.idfs[word] = math.log(1 + N / (1 + df))
            
    def save(self, filepath: str):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({"vocab": self.vocab, "idfs": self.idfs}, f, indent=2)
            
    @classmethod
    def load(cls, filepath: str):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                return cls(vocab=data.get("vocab", []), idfs=data.get("idfs", {}))
        except Exception:
            return cls()
            
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        embeddings = []
        for text in texts:
            words = tokenize(text)
            vec = [0.0] * len(self.vocab)
            if not words:
                embeddings.append(vec)
                continue
            word_counts = {}
            for w in words:
                word_counts[w] = word_counts.get(w, 0) + 1
            for w, count in word_counts.items():
                if w in self.word_to_idx:
                    idx = self.word_to_idx[w]
                    tf = count / len(words)
                    vec[idx] = tf * self.idfs.get(w, 0.0)
            embeddings.append(vec)
        return embeddings

    def embed_query(self, text: str) -> list[float]:
        if not self.vocab:
            return []
        return self.embed_documents([text])[0]

def get_embeddings():
    vocab_file = os.path.join(DB_DIR, "tfidf_vocab.json")
    if os.path.exists(vocab_file):
        return TFIDFEmbeddings.load(vocab_file)
    return TFIDFEmbeddings()

def build_vector_store(processed_dir):
    """
    Load processed JSON files, chunk them, attach metadata,
    and index them into ChromaDB.
    """
    print("Building vector store...")
    
    # Safety Check: Wipe old database directory to prevent vector dimension mismatch
    if os.path.exists(DB_DIR):
        print(f"Wiping old vector store directory at {DB_DIR} to prevent vector size conflicts...")
        try:
            shutil.rmtree(DB_DIR)
            print("Old database cleared successfully.")
        except Exception as e:
            print(f"Warning: Failed to clear old database folder: {e}")

    if not os.path.exists(processed_dir):
        print(f"Processed data directory not found at {processed_dir}. Run ingestion first.")
        return False
    
    documents = []
    
    # 1. Load Resume
    resume_path = os.path.join(processed_dir, "resume.json")
    if os.path.exists(resume_path):
        with open(resume_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            resume_text = data.get("content", "")
            
            # Split resume into sections or general chunks
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=600,
                chunk_overlap=100
            )
            chunks = splitter.split_text(resume_text)
            for idx, chunk in enumerate(chunks):
                doc = Document(
                    page_content=chunk,
                    metadata={
                        "source": "resume",
                        "chunk_idx": idx,
                        "title": "Dharmit Shah Resume Details"
                    }
                )
                documents.append(doc)
            print(f"Prepared {len(chunks)} chunks from resume.")
            
    # 2. Load GitHub repos
    for filename in os.listdir(processed_dir):
        if filename.startswith("repo_") and filename.endswith(".json"):
            file_path = os.path.join(processed_dir, filename)
            with open(file_path, "r", encoding="utf-8") as f:
                repo_data = json.load(f)
                repo_name = repo_data.get("repository", "")
                url = repo_data.get("url", "")
                description = repo_data.get("description", "")
                languages = repo_data.get("languages", [])
                topics = repo_data.get("topics", [])
                stars = repo_data.get("stats", {}).get("stars", 0)
                forks = repo_data.get("stats", {}).get("forks", 0)
                commits = repo_data.get("commits", [])
                readme = repo_data.get("readme", "")
                
                # 2a. Build repository overview document
                commit_lines = []
                for c in commits:
                    commit_lines.append(f"- [{c.get('sha')}] {c.get('author')} ({c.get('date')[:10]}): {c.get('message')}")
                commit_history_str = "\n".join(commit_lines) if commit_lines else "No recent commits found."
                
                repo_overview = (
                    f"Repository: {repo_name}\n"
                    f"URL: {url}\n"
                    f"Description: {description}\n"
                    f"Languages: {', '.join(languages)}\n"
                    f"Topics: {', '.join(topics)}\n"
                    f"Stats: Stars: {stars}, Forks: {forks}\n"
                    f"Commit History / Recent Commits:\n{commit_history_str}"
                )
                
                overview_doc = Document(
                    page_content=repo_overview,
                    metadata={
                        "source": "github",
                        "repository": repo_name,
                        "url": url,
                        "type": "overview",
                        "languages": ", ".join(languages),
                        "topics": ", ".join(topics)
                    }
                )
                documents.append(overview_doc)
                
                # 2b. Chunk and index README
                if readme.strip():
                    # Prefix chunks to keep context
                    splitter = RecursiveCharacterTextSplitter(
                        chunk_size=800,
                        chunk_overlap=120
                    )
                    readme_chunks = splitter.split_text(readme)
                    for idx, chunk in enumerate(readme_chunks):
                        readme_chunk_text = f"Repository: {repo_name} - README context:\n{chunk}"
                        doc = Document(
                            page_content=readme_chunk_text,
                            metadata={
                                "source": "github",
                                "repository": repo_name,
                                "url": url,
                                "type": "readme",
                                "chunk_idx": idx
                            }
                        )
                        documents.append(doc)
                    print(f"Prepared {len(readme_chunks)} README chunks for repo: {repo_name}")
                else:
                    print(f"No README content for repo: {repo_name}")

    if not documents:
        print("No documents to index.")
        return False
        
    print(f"Total structured documents prepared: {len(documents)}. Embedding and indexing...")
    
    # Compute embeddings for all prepared documents
    embeddings_model = TFIDFEmbeddings()
    texts = [doc.page_content for doc in documents]
    embeddings_model.fit(texts)
    
    # Save the TF-IDF vocabulary and IDF values
    vocab_file = os.path.join(DB_DIR, "tfidf_vocab.json")
    os.makedirs(DB_DIR, exist_ok=True)
    embeddings_model.save(vocab_file)
    
    print(f"Generating embeddings for {len(texts)} chunks...")
    vectors = embeddings_model.embed_documents(texts)
    
    # Combine texts, metadata, and vectors
    store_data = []
    for doc, vec in zip(documents, vectors):
        store_data.append({
            "content": doc.page_content,
            "metadata": doc.metadata,
            "embedding": vec
        })
        
    db_file = os.path.join(DB_DIR, "vectors.json")
    os.makedirs(DB_DIR, exist_ok=True)
    with open(db_file, "w", encoding="utf-8") as f:
        json.dump(store_data, f, indent=2)
        
    print(f"Vector store build successfully completed. Saved to {db_file}")
    return True

def query_vector_store(query, top_k=5, min_confidence=0.3):
    """
    Queries the pure-python vector store.
    Returns list of matches. Match includes document content, metadata, and confidence score.
    """
    db_file = os.path.join(DB_DIR, "vectors.json")
    if not os.path.exists(db_file):
        print(f"Vector store file does not exist at {db_file}. Please build it first.")
        return [], 0.0
        
    # 1. Generate query embedding
    embeddings_model = get_embeddings()
    query_vec = embeddings_model.embed_query(query)
    
    # 2. Load stored documents and vectors
    with open(db_file, "r", encoding="utf-8") as f:
        store_data = json.load(f)
        
    # 3. Calculate cosine similarity
    def dot_product(v1, v2):
        return sum(x * y for x, y in zip(v1, v2))
        
    def magnitude(v):
        return math.sqrt(sum(x * x for x in v))
        
    def cosine_similarity(v1, v2):
        mag1 = magnitude(v1)
        mag2 = magnitude(v2)
        if mag1 == 0 or mag2 == 0:
            return 0.0
        return dot_product(v1, v2) / (mag1 * mag2)
        
    scored_results = []
    for doc in store_data:
        similarity = cosine_similarity(query_vec, doc["embedding"])
        scored_results.append({
            "content": doc["content"],
            "metadata": doc["metadata"],
            "confidence": similarity
        })
        
    # 4. Sort by similarity in descending order
    scored_results.sort(key=lambda x: x["confidence"], reverse=True)
    
    # 5. Filter top_k
    top_results = scored_results[:top_k]
    max_confidence = top_results[0]["confidence"] if top_results else 0.0
    
    return top_results, max_confidence

if __name__ == "__main__":
    workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    processed_dir = os.path.join(workspace_dir, "data", "processed")
    build_vector_store(processed_dir)
