import asyncio
import unittest
from tornado.ioloop import IOLoop
from tornado.testing import AsyncHTTPTestCase
from tornado.web import Application, RequestHandler
from json import loads

import server

class MyTestCase(AsyncHTTPTestCase):
    @classmethod
    def setUpClass(cls):
        loop = asyncio.get_event_loop()
        cls.my_app, cls.redis_pool, cls.db_pool = loop.run_until_complete(server.make_app())

    @classmethod
    def tearDownClass(cls):
        cls.db_pool.close()
        cls.redis_pool.close()
        loop = asyncio.get_event_loop()
        loop.run_until_complete(asyncio.gather(
            cls.redis_pool.wait_closed(),
            cls.db_pool.wait_closed(),
        ))

    def get_new_ioloop(self):
        return IOLoop.current()

    def get_app(self):
        return self.my_app

    def test_post_and_get(self):
        post_response = self.fetch(
            "/guid",
            method='POST',
            body='{"user":"john"}',
        )
        guid = loads(post_response.body)['guid']
        get_response = self.fetch(f'/guid/{guid}')
        self.assertEqual(get_response.body, post_response.body)

if __name__ == '__main__':
    unittest.main()
