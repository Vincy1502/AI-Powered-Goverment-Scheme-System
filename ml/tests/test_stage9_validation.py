import unittest
from fastapi.testclient import TestClient
from app.main import app, persisted_scheme_records


class Stage9ValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_empty_scheme_payload_is_rejected(self):
        response = self.client.post('/recommend', json={
            'profile': {'state': 'Tamil Nadu', 'occupation': 'Farmer'},
            'schemes': [],
        })
        self.assertEqual(response.status_code, 422)

    def test_missing_profile_query_fields_are_rejected(self):
        response = self.client.post('/recommend', json={
            'profile': {'age': 28, 'income': 250000},
            'schemes': persisted_scheme_records,
        })
        self.assertEqual(response.status_code, 422)

    def test_invalid_numeric_profile_values_remain_unknown(self):
        response = self.client.post('/recommend', json={
            'profile': {'state': 'Tamil Nadu', 'occupation': 'Farmer', 'age': 'not-a-number',
                        'income': 'unknown', 'query': 'agriculture irrigation'},
            'schemes': persisted_scheme_records,
            'limit': 2,
        })
        self.assertEqual(response.status_code, 200, response.text)
        recommendations = response.json()['recommendations']
        self.assertTrue(recommendations)
        for item in recommendations:
            self.assertIn(item['eligibility_status'], {
                'insufficient_information', 'potential_eligibility', 'not_eligible'
            })
            age_checks = [c for c in item['eligibility_checks'] if c['criterion'] in {'minimum age', 'maximum age'}]
            self.assertTrue(all(c['status'] != 'pass' for c in age_checks))

    def test_recommendation_limit_is_validated(self):
        response = self.client.post('/recommend', json={
            'profile': {'state': 'Tamil Nadu', 'occupation': 'Farmer'},
            'schemes': persisted_scheme_records,
            'limit': 0,
        })
        self.assertEqual(response.status_code, 422)


if __name__ == '__main__':
    unittest.main()
