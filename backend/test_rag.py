from services.rag_agent import rag_agent
import logging

logging.basicConfig(level=logging.DEBUG)

def test_rag():
    try:
        res = rag_agent.process_query("Summarize the financial report")
        print("Result:", res)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    test_rag()
