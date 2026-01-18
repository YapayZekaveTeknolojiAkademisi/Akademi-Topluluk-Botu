import os
import faiss
import numpy as np
import pickle
from typing import List, Dict, Any, Tuple
from sentence_transformers import SentenceTransformer
from src.core.logger import logger
from src.core.singleton import SingletonMeta

class VectorClient(metaclass=SingletonMeta):
    """
    Yerel FAISS indeksi ve SentenceTransformers kullanarak 
    ücretsiz ve limitsiz vektör arama işlemlerini yönetir.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", index_path: str = "data/vector_store"):
        self.model = SentenceTransformer(model_name)
        self.index_path = index_path
        self.index = None
        self.documents = []  # Chunks/Texts
        self.dimension = self.model.get_sentence_embedding_dimension()
        
        # Dizini oluştur
        os.makedirs(os.path.dirname(index_path) if os.path.dirname(index_path) else "data", exist_ok=True)
        
        # Mevcut indeksi yükle
        self.load_index()

    def add_texts(self, texts: List[str], metadata: List[Dict] = None):
        """Metinleri vektörleştirir ve indekse ekler."""
        if not texts:
            return

        embeddings = self.model.encode(texts)
        embeddings = np.array(embeddings).astype('float32')

        if self.index is None:
            self.index = faiss.IndexFlatL2(self.dimension)
        
        self.index.add(embeddings)
        
        for i, text in enumerate(texts):
            meta = metadata[i] if metadata else {}
            self.documents.append({"text": text, "metadata": meta})
        
        self.save_index()
        logger.info(f"[+] {len(texts)} yeni parça vektör indeksine eklendi.")

    def search(self, query: str, top_k: int = 5, threshold: float = 0.8) -> List[Dict]:
        """
        Soruya en yakın metin parçalarını döner.
        
        Args:
            query: Arama sorgusu
            top_k: Dönecek maksimum sonuç sayısı (varsayılan: 5)
            threshold: L2 mesafesi için maksimum eşik (varsayılan: 0.8)
                      Küçük değer = sıkı eşleşme, büyük değer = gevşek eşleşme
        
        Returns:
            Eşleşen dökümanlar listesi (score ile sıralı)
        """
        if self.index is None or not self.documents:
            logger.warning(f"[!] Vector search: İndeks veya döküman yok | Toplam döküman: {len(self.documents) if self.documents else 0}")
            return []

        query_embedding = self.model.encode([query])
        query_embedding = np.array(query_embedding).astype('float32')

        # Daha fazla sonuç al, sonra filtrele (top_k * 4 ile daha geniş arama)
        search_k = min(top_k * 4, len(self.documents)) if self.documents else top_k
        distances, indices = self.index.search(query_embedding, search_k)
        
        results = []
        filtered_count = 0
        for i, idx in enumerate(indices[0]):
            if idx != -1 and idx < len(self.documents):
                distance = float(distances[0][i])
                # Filtreleme: Mesafe eşikten küçükse (yani yeterince benzerse) ekle
                if distance <= threshold:
                    doc = self.documents[idx].copy()
                    doc["score"] = distance
                    results.append(doc)
                else:
                    filtered_count += 1
                    if filtered_count <= 3:  # İlk 3 filtrelenen sonucu logla
                        logger.debug(f"[i] Sonuç filtrelendi: score={distance:.3f} > threshold={threshold}")
        
        # En iyi sonuçları döndür (top_k kadar)
        results = sorted(results, key=lambda x: x.get('score', float('inf')))[:top_k]
        
        if results:
            logger.debug(f"[i] Vector search: {len(results)}/{search_k} sonuç döndürüldü (threshold: {threshold}, {filtered_count} filtrelendi)")
        else:
            logger.debug(f"[!] Vector search: Hiç uygun sonuç yok (threshold: {threshold}, toplam: {search_k}, filtrelenen: {filtered_count})")
        
        return results

    def save_index(self):
        """İndeksi ve dökümanları diske kaydeder."""
        if self.index is not None:
            faiss.write_index(self.index, f"{self.index_path}.index")
            with open(f"{self.index_path}.pkl", "wb") as f:
                pickle.dump(self.documents, f)
            logger.debug("[i] Vektör indeksi diske kaydedildi.")

    def load_index(self):
        """İndeksi ve dökümanları diskten yükler."""
        if os.path.exists(f"{self.index_path}.index"):
            self.index = faiss.read_index(f"{self.index_path}.index")
            with open(f"{self.index_path}.pkl", "rb") as f:
                self.documents = pickle.load(f)
            logger.info(f"[i] Vektör indeksi yüklendi: {len(self.documents)} parça.")
