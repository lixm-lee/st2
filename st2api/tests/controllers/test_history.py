import copy
import random

import bson
import six
from six.moves import http_client

from tests import FunctionalTest
from tests.fixtures import history as fixture
from st2api.controllers.history import ActionExecutionController
from st2common.persistence.history import ActionExecutionHistory
from st2common.models.api.history import ActionExecutionHistoryAPI


class TestActionExecutionHistory(FunctionalTest):

    @classmethod
    def setUpClass(cls):
        super(TestActionExecutionHistory, cls).setUpClass()

        cls.num_records = 100
        cls.references = {}

        cls.fake_types = [
            {
                'trigger': copy.deepcopy(fixture.ARTIFACTS['trigger']),
                'trigger_type': copy.deepcopy(fixture.ARTIFACTS['trigger_type']),
                'trigger_instance': copy.deepcopy(fixture.ARTIFACTS['trigger_instance']),
                'rule': copy.deepcopy(fixture.ARTIFACTS['rule']),
                'action': copy.deepcopy(fixture.ARTIFACTS['actions']['chain']),
                'runner': copy.deepcopy(fixture.ARTIFACTS['runners']['action-chain']),
                'execution': copy.deepcopy(fixture.ARTIFACTS['executions']['workflow']),
                'children': [str(bson.ObjectId()), str(bson.ObjectId())]
            },
            {
                'action': copy.deepcopy(fixture.ARTIFACTS['actions']['local']),
                'runner': copy.deepcopy(fixture.ARTIFACTS['runners']['run-local']),
                'execution': copy.deepcopy(fixture.ARTIFACTS['executions']['task1'])
            }
        ]

        for i in range(cls.num_records):
            obj_id = str(bson.ObjectId())
            fake_type = random.choice(cls.fake_types)
            cls.references[obj_id] = fake_type
            data = copy.deepcopy(fake_type)
            data['id'] = obj_id
            obj = ActionExecutionHistoryAPI(**data)
            ActionExecutionHistory.add_or_update(ActionExecutionHistoryAPI.to_model(obj))

    def test_get_all(self):
        response = self.app.get('/history/executions')
        self.assertEqual(response.status_int, 200)
        self.assertIsInstance(response.json, list)
        self.assertEqual(len(response.json), self.num_records)
        ids = [item['id'] for item in response.json]
        self.assertListEqual(sorted(ids), sorted(self.references.keys()))

    def test_get_one(self):
        obj_id = random.choice(self.references.keys())
        response = self.app.get('/history/executions/%s' % obj_id)
        self.assertEqual(response.status_int, 200)
        self.assertIsInstance(response.json, dict)
        record = response.json
        fake_record = self.references[obj_id]
        self.assertEqual(record['id'], obj_id)
        self.assertDictEqual(record['action'], fake_record['action'])
        self.assertDictEqual(record['runner'], fake_record['runner'])
        self.assertDictEqual(record['execution'], fake_record['execution'])

    def test_get_one_failed(self):
        response = self.app.get('/history/executions/%s' % str(bson.ObjectId()), expect_errors=True)
        self.assertEqual(response.status_int, http_client.NOT_FOUND)

    def test_limit(self):
        limit = 10
        refs = [k for k, v in six.iteritems(self.references) if v == self.fake_types[0]]
        response = self.app.get('/history/executions?action=chain&limit=%s' % limit)
        self.assertEqual(response.status_int, 200)
        self.assertIsInstance(response.json, list)
        self.assertEqual(len(response.json), limit)
        ids = [item['id'] for item in response.json]
        self.assertListEqual(list(set(ids) - set(refs)), [])

    def test_query(self):
        refs = [k for k, v in six.iteritems(self.references) if v == self.fake_types[0]]
        response = self.app.get('/history/executions?action=chain')
        self.assertEqual(response.status_int, 200)
        self.assertIsInstance(response.json, list)
        self.assertEqual(len(response.json), len(refs))
        ids = [item['id'] for item in response.json]
        self.assertListEqual(sorted(ids), sorted(refs))

    def test_filters(self):
        for param, field in six.iteritems(ActionExecutionController.supported_filters):
            value = self.fake_types[0]
            for item in field.split('__'):
                value = value[item]
            response = self.app.get('/history/executions?%s=%s' % (param, value))
            self.assertEqual(response.status_int, 200)
            self.assertIsInstance(response.json, list)
            self.assertGreater(len(response.json), 0)

    def test_pagination(self):
        retrieved = []
        page_size = 10
        page_count = self.num_records / page_size
        for i in range(page_count):
            offset = i * page_size
            response = self.app.get('/history/executions?offset=%s&limit=%s' % (offset, page_size))
            self.assertEqual(response.status_int, 200)
            self.assertIsInstance(response.json, list)
            self.assertEqual(len(response.json), page_size)
            ids = [item['id'] for item in response.json]
            self.assertListEqual(list(set(ids) - set(self.references.keys())), [])
            self.assertListEqual(sorted(list(set(ids) - set(retrieved))), sorted(ids))
            retrieved += ids
        self.assertListEqual(sorted(retrieved), sorted(self.references.keys()))
