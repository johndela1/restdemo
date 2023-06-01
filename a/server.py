import tornado.ioloop
import tornado.web
import aioredis
import tornado.locks
import aiopg
from json import loads, dumps
from tornado.escape import json_decode
from uuid import uuid4
from datetime import datetime, timedelta

class MainHandler(tornado.web.RequestHandler):
    def initialize(self, cache, db):
        self.cache = cache
        self.db = db

    async def post(self, guid):
        if guid is '': guid = uuid4().hex.upper()
        data = json_decode(self.request.body)
        expire = data.get('expire',
            int((datetime.now() + timedelta(days=30)).timestamp()))
        user = data['user']
        response = dict(guid=guid, user=user, expire=expire)
        async with self.db.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"insert into guid values('{guid}', '{user}', '{expire}');")
        self.write(response)

    async def get(self, guid):
        with await self.cache as conn:
            val = await conn.execute('get', guid)
        if val is not None:
            self.write(loads(val))
            return
        async with self.db.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"SELECT * from guid where guid='{guid}'")
                async for row in cur:
                    col_names = [i.name.replace('_', '') for i in cur.description]
                    result = dict(zip(col_names, row))
                    with await self.cache as conn:
                        await conn.execute('set', guid, dumps(result))
                    self.write(result)

async def make_app():
    redis_pool = await aioredis.create_pool('redis://localhost')
    db_pool = await aiopg.create_pool(host='localhost', dbname='guid')
    app = tornado.web.Application([
        (r"/guid/?(.*)", MainHandler, dict(cache=redis_pool, db=db_pool)),
    ], debug=True, autoreload=True)
    return app, redis_pool, db_pool

async def main():
    app, _, _ = await make_app()
    app.listen(5000)
    shutdown_event = tornado.locks.Event()
    await shutdown_event.wait()

if __name__ == "__main__":
     tornado.ioloop.IOLoop.current().run_sync(main)
