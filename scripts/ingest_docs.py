"""Ingest knowledge documents into Qdrant for Knowledge RAG.

Embeds all chunks in a single batched forward pass through BGE-M3,
producing both dense and sparse vectors simultaneously.
"""

import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

from jantar.config import settings
from jantar.rag.embeddings import embed_dense_and_sparse

KNOWLEDGE_COLLECTION = "knowledge_vectors"
SEED_FILE = Path(__file__).parent.parent / "data" / "seed" / "knowledge_base.json"


def ensure_collection(client: QdrantClient):
    collections = [c.name for c in client.get_collections().collections]
    if KNOWLEDGE_COLLECTION not in collections:
        client.create_collection(
            collection_name=KNOWLEDGE_COLLECTION,
            vectors_config={"dense": VectorParams(size=1024, distance=Distance.COSINE)},
            sparse_vectors_config={"sparse": SparseVectorParams()},
        )


def main():
    client = QdrantClient(url=settings.qdrant_url)
    ensure_collection(client)

    with open(SEED_FILE) as f:
        data = json.load(f)

    # Prepare all texts and metadata first
    texts_to_embed = []
    metadata_list = []

    for doc in data["documents"]:
        parent_content = "\n\n".join(s["content"] for s in doc["sections"])

        for section in doc["sections"]:
            context_prefix = (
                f"This is from '{doc['title']}', section '{section['section_path']}'. "
                f"Source: {doc['source_url']}"
            )
            embed_text = f"{context_prefix}\n\n{section['content']}"
            texts_to_embed.append(embed_text)
            metadata_list.append({
                "content": section["content"],
                "context_prefix": context_prefix,
                "parent_content": parent_content,
                "source_url": doc["source_url"],
                "document_title": doc["title"],
                "section_path": section["section_path"],
                "language": doc.get("language", "en"),
                "effective_date": doc.get("effective_date", ""),
                "jurisdiction": doc.get("jurisdiction", "central"),
                "domain": doc.get("domain", "general"),
            })

    # Single batched forward pass for ALL chunks
    print(f"Embedding {len(texts_to_embed)} chunks with BGE-M3 (dense + sparse)...")
    dense_vecs, sparse_vecs = embed_dense_and_sparse(texts_to_embed)

    # Build Qdrant points
    points = []
    for i, (dense_vec, sparse_vec, meta) in enumerate(
        zip(dense_vecs, sparse_vecs, metadata_list)
    ):
        points.append(PointStruct(
            id=str(uuid.uuid4()),
            vector={
                "dense": dense_vec,
                "sparse": SparseVector(
                    indices=sparse_vec["indices"],
                    values=sparse_vec["values"],
                ),
            },
            payload=meta,
        ))

    # Batch upsert
    batch_size = 50
    for i in range(0, len(points), batch_size):
        batch = points[i:i + batch_size]
        client.upsert(collection_name=KNOWLEDGE_COLLECTION, points=batch)

    print(
        f"Ingested {len(points)} chunks from {len(data['documents'])} documents "
        f"into '{KNOWLEDGE_COLLECTION}'"
    )


if __name__ == "__main__":
    main()
