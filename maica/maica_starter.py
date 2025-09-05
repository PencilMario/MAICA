import sys, os
def get_basedir():
    if hasattr(sys, "_MEIPASS"):  # PyInstaller 临时目录
        # 改为 exe 所在目录
        return os.path.dirname(sys.executable)
    else:
        # 开发环境下直接用当前文件目录
        return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_basedir()

import asyncio
import maica_ws
import maica_http
import common_schedule
from maica_utils import *
from initializer import *

def check_init():
    if not check_marking():
        generate_rsa_keys()
        asyncio.run(create_tables())
        create_marking()
        asyncio.run(messenger(info="MAICA Illuminator initiation finished", type=MsgType.PRIM_SYS))
    else:
        asyncio.run(messenger(info="Initiated marking detected, skipping initiation", type=MsgType.DEBUG))

async def start_all():
    auth_pool, maica_pool = await asyncio.gather(ConnUtils.auth_pool(), ConnUtils.maica_pool())
    kwargs = {"auth_pool": auth_pool, "maica_pool": maica_pool}
    task_ws = asyncio.create_task(maica_ws.prepare_thread(**kwargs))
    task_http = asyncio.create_task(maica_http.prepare_thread(**kwargs))
    task_schedule = asyncio.create_task(common_schedule.schedule_rotate_cache(**kwargs))

    await asyncio.wait([
        task_ws,
        task_http,
        task_schedule,
    ], return_when=asyncio.FIRST_COMPLETED)

    await messenger(info="All quits collected, doing final cleanup...", type=MsgType.DEBUG)
    await asyncio.gather(auth_pool.close(), maica_pool.close(), return_exceptions=True)
    quit()

if __name__ == "__main__":
    check_init()
    asyncio.run(start_all())