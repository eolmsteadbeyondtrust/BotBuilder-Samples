# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import sys
import traceback
from datetime import datetime
from http import HTTPStatus

from aiohttp import web
from aiohttp.web import Request, Response, json_response
from botbuilder.core import (
    BotFrameworkAdapter,
    BotFrameworkAdapterSettings,
    MemoryStorage,
    TurnContext,
    UserState,
)
from botbuilder.core.integration import aiohttp_error_middleware
from botbuilder.schema import Activity, ActivityTypes

from bots import WelcomeUserBot
from config import DefaultConfig

import logging
log=logging.getLogger(__name__)

# Catch-all for errors.
async def on_error(context: TurnContext, error: Exception):
    # This check writes out errors to console log .vs. app insights.
    # NOTE: In production environment, you should consider logging this to Azure
    #       application insights.
    print(f"\n [on_turn_error] unhandled error: {error}", file=sys.stderr)
    traceback.print_exc()

    # Send a message to the user
    await context.send_activity("The bot encountered an error or bug.")
    await context.send_activity(
        "To continue to run this bot, please fix the bot source code."
    )
    # Send a trace activity if we're talking to the Bot Framework Emulator
    if context.activity.channel_id == "emulator":
        # Create a trace activity that contains the error object
        trace_activity = Activity(
            label="TurnError",
            name="on_turn_error Trace",
            timestamp=datetime.utcnow(),
            type=ActivityTypes.trace,
            value=f"{error}",
            value_type="https://www.botframework.com/schemas/error",
        )
        # Send a trace activity, which will be displayed in Bot Framework Emulator
        await context.send_activity(trace_activity)

# Listen for incoming requests on /api/messages.
async def messages(req: Request) -> Response:
    # Main bot message handler.
    if "application/json" in req.headers["Content-Type"]:
        body = await req.json()
    else:
        return Response(status=HTTPStatus.UNSUPPORTED_MEDIA_TYPE)

    activity = Activity().deserialize(body)
    auth_header = req.headers["Authorization"] if "Authorization" in req.headers else ""

    response = await ADAPTER.process_activity(activity, auth_header, BOT.on_turn)
    if response:
        return json_response(data=response.body, status=response.status)

    return Response(status=HTTPStatus.OK)

if __name__ == "__main__":
    try:

        import http.client
        import json

        # http.client only uses print to log, this will override that
        httpclient_logger = logging.getLogger("http.client")

        def httpclient_log(*args):
            import re
            text = " ".join(args)
            m1 = re.search(r'b\'((?:POST|GET|PUT|DELETE).*)\'$', args[1])
            if (m1):
                httpclient_logger.log(logging.DEBUG, bytes(
                    m1.group(1), "utf-8").decode('unicode_escape'))
                return

            m2 = re.search(r'send: b\'({.*})', text)
            if (m2):
                httpclient_logger.log(logging.DEBUG, json.dumps(
                    json.loads(str(m2.group(1))), indent=4))
                return

            httpclient_logger.log(logging.DEBUG, text)

        # mask the print() built-in in the http.client module to use
        # logging instead
        http.client.HTTPConnection.debuglevel = 1
        http.client.print = httpclient_log

        logging.basicConfig(level=logging.DEBUG)

        log.info("STARTED")

        CONFIG = DefaultConfig()

        # Create adapter.
        # See https://aka.ms/about-bot-adapter to learn more about how bots work.
        SETTINGS = BotFrameworkAdapterSettings(CONFIG.APP_ID, CONFIG.APP_PASSWORD)
        ADAPTER = BotFrameworkAdapter(SETTINGS)

        ADAPTER.on_turn_error = on_error

        # Create MemoryStorage, UserState
        MEMORY = MemoryStorage()
        USER_STATE = UserState(MEMORY)

        # Create the Bot
        BOT = WelcomeUserBot(USER_STATE)

        APP = web.Application(middlewares=[aiohttp_error_middleware])
        APP.router.add_post("/api/messages", messages)

        web.run_app(APP, host="localhost", port=CONFIG.PORT)
    except Exception as error:
        raise error
    finally:
        log.info("STOPPED")
