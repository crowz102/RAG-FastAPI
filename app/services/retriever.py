from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchAny
from sentence_transformers import CrossEncoder
from app.core.config import QDRANT_HOST, QDRANT_PORT, COLLECTION_NAME
from app.services.ingest import embedder

client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
cross_encoder = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')


def retrieve(question: str, top_k: int = 5, filenames: list[str] = None) -> list[dict]:
    query_vector = embedder.encode(question).tolist()

    query_filter = None
    if filenames:
        query_filter = Filter(
            must=[FieldCondition(key="filename", match=MatchAny(any=filenames))]
        )

    raw_results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        query_filter=query_filter,
        limit=top_k * 2,
        with_payload=True,
    ).points

    if not raw_results:
        return []

    documents = [
        {
            "text": hit.payload["text"],
            "filename": hit.payload.get("filename", "unknown"),
            "qdrant_score": round(hit.score, 4),
        }
        for hit in raw_results
    ]

    cross_inp = [[question, doc["text"]] for doc in documents]
    cross_scores = cross_encoder.predict(cross_inp)

    for idx, score in enumerate(cross_scores):
        documents[idx]["cross_score"] = float(score)

    documents.sort(key=lambda x: x["cross_score"], reverse=True)

    return documents[:top_k]