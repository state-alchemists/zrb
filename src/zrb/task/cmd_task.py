from typing import Callable
from .base_task import BaseTask

import asyncio


class CmdTask(BaseTask):
    cmd: str

    async def run(self):
        process = await asyncio.create_subprocess_shell(
            self.cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        self._task_pid = process.pid
        # Create queue
        stdout_queue = asyncio.Queue()
        stderr_queue = asyncio.Queue()
        # Create reader task
        stdout_task = asyncio.create_task(self._stream_reader(
            process.stdout, stdout_queue
        ))
        stderr_task = asyncio.create_task(self._stream_reader(
            process.stderr, stderr_queue
        ))
        # Create logger task
        stdout_logger_task = asyncio.create_task(
            self._stream_logger(self.print_out, stdout_queue)
        )
        stderr_logger_task = asyncio.create_task(
            self._stream_logger(self.print_err, stdout_queue)
        )
        # wait process
        await process.wait()
        await stdout_queue.put(None)
        await stderr_queue.put(None)
        # wait reader and logger
        await stdout_task
        await stderr_task
        await stdout_logger_task
        await stderr_logger_task
        # get return code
        return_code = process.returncode
        if return_code != 0:
            raise Exception(f'Process {self.name} exited ({return_code})')

    async def _stream_reader(self, stream, queue: asyncio.Queue):
        while True:
            line = await stream.readline()
            if not line:
                break
            await queue.put(line)

    async def _stream_logger(
        self, print_log: Callable[[str], None], queue: asyncio.Queue
    ):
        while True:
            line = await queue.get()
            if not line:
                break
            print_log(line.decode())
