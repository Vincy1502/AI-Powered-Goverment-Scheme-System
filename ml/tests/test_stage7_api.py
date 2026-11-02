import unittest
from fastapi.testclient import TestClient
from app.main import app, persisted_scheme_records


class Stage7ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health_reports_persisted_model_loaded(self):
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['model_ready'])
        self.assertEqual(response.json()['model_source'], 'persisted_stage6_artifacts')

    def test_recommendation_api_returns_structured_eligibility_assessment(self):
        payload = {
            'profile': {'state': 'Tamil Nadu', 'occupation': 'Farmer', 'gender': 'Female',
                        'category': 'OBC', 'age': 30, 'income': 200000,
                        'query': 'irrigation agriculture support'},
            'schemes': persisted_scheme_records,
            'limit': 3,
        }
        response = self.client.post('/recommend', json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data['model_source'], 'Stage 6 persisted artifacts')
        self.assertEqual(data['dataset_scheme_count'], 174)
        self.assertEqual(len(data['recommendations']), 3)
        item = data['recommendations'][0]
        self.assertIn(item['eligibility_status'], {'confirmed_eligible', 'potential_eligibility', 'insufficient_information', 'not_eligible'})
        self.assertTrue(item['eligibility_checks'])
        self.assertIn('manual_review', item)
        self.assertIn('eligibility_disclaimer', item)


if __name__ == '__main__':
    unittest.main()
