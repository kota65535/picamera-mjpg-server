import io
import logging
import asyncio

import picamera
import tornado.ioloop
import tornado.web
import tornado.iostream

logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.INFO)
logger = logging.getLogger()

PAGE="""\
<html>
<head>
<title>picamera MJPEG streaming demo</title>
</head>
<body>
<h1>PiCamera MJPEG Streaming Demo</h1>
<img src="stream.mjpg" width="640" height="480" />
</body>
</html>
"""


class StreamingOutput(object):
    def __init__(self, loop: asyncio.AbstractEventLoop):
        self.frame = None
        self.buffer = io.BytesIO()
        self.condition = asyncio.Condition(loop=loop)
        self.loop = loop

    def write(self, buf):
        if buf.startswith(b'\xff\xd8'):
            # New frame, copy the existing buffer's content and notify all
            self.buffer.truncate()
            # TODO: back pressure
            asyncio.run_coroutine_threadsafe(self.set_frame(), self.loop)
            self.buffer.seek(0)
        return self.buffer.write(buf)

    async def set_frame(self):
        async with self.condition:
            self.frame = self.buffer.getvalue()
            self.condition.notify_all()


class IndexHandler(tornado.web.RequestHandler):
    def get(self):
        content = PAGE.encode('utf-8')
        self.write(content)


class StreamHandler(tornado.web.RequestHandler):

    def initialize(self, output: StreamingOutput):
        self.output = output

    async def get(self):
        self.set_header('Cache-Control', 'no-store')
        self.set_header('Content-Type', 'multipart/x-mixed-replace; boundary=--FRAME')

        try:
            while True:
                async with self.output.condition:
                    await self.output.condition.wait()
                    frame = self.output.frame
                logger.debug(f'sending {len(frame)} bytes')
                self.write('--FRAME\r\n')
                self.write('Content-Type: image/jpeg\r\n')
                self.write(f"Content-Length: {len(frame)}\r\n\r\n")
                self.write(frame)
                await self.flush()
        except tornado.iostream.StreamClosedError:
            logger.info('Removed streaming client.')
        except Exception:
            logging.exception('Unknown error.')


async def main():
    loop = asyncio.get_event_loop()
    output = StreamingOutput(loop)

    camera = picamera.PiCamera()
    camera.start_recording(output, format='mjpeg')

    application = tornado.web.Application([
        (r'/index.html', IndexHandler),
        (r'/stream.mjpg', StreamHandler, dict(output=output))
    ])
    application.listen(8000)
    logger.info('Server started.')


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    loop.run_until_complete(main())
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        tornado.ioloop.IOLoop.current().stop()
    logger.info('Server finished.')


