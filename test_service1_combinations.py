from agents.service1_agent import build_service1_graph
import time

graph = build_service1_graph()
state = {
    "search_keyword": "Software Engineer, Software Developer",
    "search_location": "India, Remote India",
    "search_experience": "Any",
    "search_type": "ats",
    "target_jobs": [],
    "apply_results": [],
    "errors": []
}
start = time.time()
print("Starting graph with combinations...")
res = graph.invoke(state)
print(f"Graph completed in {time.time() - start:.2f}s with {len(res.get('target_jobs', []))} jobs.")
