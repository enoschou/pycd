import os

from flask import Flask, request, abort
from google.cloud import storage

from linebot.v3 import (
    WebhookHandler
)
from linebot.v3.exceptions import (
    InvalidSignatureError
)
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    MessagingApiBlob,
    ReplyMessageRequest,
    TextMessage,
    AudioMessage
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    AudioMessageContent
)

from yourgcpchat import GcpChat


app = Flask(__name__)

configuration = Configuration(access_token='YOUR_CHANNEL_ACCESS_TOKEN')
handler = WebhookHandler('YOUR_CHANNEL_SECRET')

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'YOUR_SERVICE'

storage_client = storage.Client()
bucket = storage_client.bucket('YOUR_BUCKET')
g = GcpChat(collection='YOUR_COLLECTION', instruction='YOUR_INSTRUCTION')


@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.info("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=event.message.text)]
            )
        )

@handler.add(MessageEvent, message=AudioMessageContent)
def handle_message(event):
    with ApiClient(configuration) as api_client:
        messages = []
        line_bot_api_blob = MessagingApiBlob(api_client)
        content = line_bot_api_blob.get_message_content(event.message.id)
        
        r = g.chat(event.source.user_id, content, format='m4a')
        if type(r) == tuple:
            content, duration = r
            blob = bucket.blob(event.message.id+'.mp3')
            blob.upload_from_string(content, content_type='audio/mpeg')
            messages.append(AudioMessage(originalContentUrl=blob.public_url, duration=int(duration)))
        else:
            messages.append(TextMessage('bad chat!'))

        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(reply_token=event.reply_token, messages=messages)
        )


if __name__ == "__main__":
    app.run()
