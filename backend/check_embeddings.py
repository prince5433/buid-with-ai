from services.embeddings import embeddings_service

def check_embeddings():
    results = embeddings_service.query("what are my kew skills", n_results=5)
    for res in results:
        print(f"Score: {res['score']}, Doc: {res['document_name']}")
        print(f"Text: {res['text'][:200]}...")
        print("-" * 50)

if __name__ == "__main__":
    check_embeddings()
