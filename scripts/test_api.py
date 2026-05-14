"""Quick tests for the SHL Assessment Recommender API."""
import requests
import json
import time

BASE = "http://localhost:8000"

def test(name, payload):
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"{'='*60}")
    start = time.time()
    r = requests.post(f"{BASE}/chat", json=payload)
    elapsed = time.time() - start
    data = r.json()
    print(f"Status: {r.status_code} | Time: {elapsed:.1f}s")
    reply_preview = data['reply'][:300]
    print(f"Reply: {reply_preview}")
    print(f"Recommendations: {len(data['recommendations'])}")
    for rec in data['recommendations']:
        print(f"  - {rec['name']} ({rec['test_type']}) -> {rec['url']}")
    print(f"End of conversation: {data['end_of_conversation']}")
    return data

# Test 1: Vague query -- should clarify, no recommendations
test("Vague query (should clarify)", {
    "messages": [
        {"role": "user", "content": "I need an assessment"}
    ]
})

# Test 2: Specific query -- should recommend
test("Java developer (should recommend)", {
    "messages": [
        {"role": "user", "content": "I am hiring a mid-level Java developer who will work with Spring Boot and SQL databases"}
    ]
})

# Test 3: Multi-turn with refinement
test("Multi-turn refinement", {
    "messages": [
        {"role": "user", "content": "Hiring a Java developer"},
        {"role": "assistant", "content": "I'd be happy to help! Could you tell me more about the role? What seniority level are you looking for, and are there specific skills beyond Java that are important?"},
        {"role": "user", "content": "Senior level, 5+ years. Needs Java, Spring, AWS, and Docker"}
    ]
})

# Test 4: Off-topic -- should refuse
test("Off-topic (should refuse)", {
    "messages": [
        {"role": "user", "content": "What is the best salary to offer a software engineer in San Francisco?"}
    ]
})

# Test 5: Comparison
test("Comparison request", {
    "messages": [
        {"role": "user", "content": "What is the difference between OPQ32r and the Motivation Questionnaire?"}
    ]
})

print("\n\nAll tests completed!")
