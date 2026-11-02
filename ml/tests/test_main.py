from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
SCHEMES = [
    {"scheme_name": "Farmer Irrigation Support", "parent_scheme": "Agriculture Loan Schemes", "objectives": ["Support farmers with irrigation"], "eligibility_criteria": ["Resident of Tamil Nadu", "Engaged in agriculture"], "benefits": {"loan_amount": "varies"}},
    {"scheme_name": "Student Scholarship", "parent_scheme": "Education", "objectives": ["Support students with education"], "eligibility_criteria": ["Students enrolled in college"], "benefits": {"grant": "varies"}}
]

def test_health():
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json()['status'] == 'ok'

def test_recommendation_uses_supplied_scheme_text():
    response = client.post('/recommend', json={"profile": {"state": "Tamil Nadu", "occupation": "Farmer", "query": "irrigation loan"}, "schemes": SCHEMES})
    assert response.status_code == 200
    body = response.json()
    assert body['total_schemes_received'] == 2
    assert body['recommendations'][0]['scheme_name'] == 'Farmer Irrigation Support'
    assert 'relevance_score' in body['recommendations'][0]
    assert body['recommendations'][0]['eligibility_status'] == 'needs_review'

def test_no_scheme_data_returns_validation_error():
    response = client.post('/recommend', json={"profile": {"state": "Tamil Nadu", "occupation": "Farmer"}, "schemes": []})
    assert response.status_code == 422

def test_ranking_metrics_need_reviewed_cases():
    response = client.post('/evaluate-ranking', json={
        "k": 2,
        "schemes": SCHEMES,
        "cases": [{
            "profile": {"state": "Tamil Nadu", "occupation": "Farmer", "query": "irrigation loan"},
            "relevant_scheme_names": ["Farmer Irrigation Support"]
        }]
    })
    assert response.status_code == 200
    assert response.json()['precision_at_k'] == 0.5
    assert response.json()['recall_at_k'] == 1.0

def test_compare_returns_two_rankings_without_claiming_accuracy():
    response = client.post('/compare', json={
        "profile": {"state": "Tamil Nadu", "occupation": "Farmer", "query": "irrigation loan"},
        "schemes": SCHEMES,
        "limit": 5
    })
    assert response.status_code == 200
    body = response.json()
    assert 'baseline_top_k' in body
    assert 'ml_top_k' in body
    assert 'interpretation' in body
    assert 'accurate' in body['interpretation'].lower()
