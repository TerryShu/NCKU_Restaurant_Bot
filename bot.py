from flask import Flask, request, abort, session
from datetime import timedelta
from enum import IntEnum
import random
from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
)

import psycopg2

app = Flask(__name__)
app.secret_key = b'_a3g8K"Q4T8n\n\xEc]/'

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import and_
app.config['SQLALCHEMY_DATABASE_URI'] = 'YOUR_DATABASEURI'
db = SQLAlchemy(app)

line_bot_api = LineBotApi('YOUR_CHANNEL_ACCESS_TOKEN')
handler = WebhookHandler('YOUR_CHANNEL_SECRET')

class restaurant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    restaurant_name = db.Column(db.String(100), nullable=False)
    restaurant_type = db.Column(db.String(100), nullable=False)
    low_price = db.Column(db.Integer)
    high_price = db.Column(db.Integer)

@app.before_request
def make_session_permanent():
    session.permanent = True
    app.permanent_session_lifetime = timedelta(minutes=3)

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
        abort(400)

    return 'OK'

class State(IntEnum):
    UploadName = 1
    UploadType = 2
    UploadPrice = 3
    SearchRestaurant = 4
    SearchType = 5
    SearchPrice = 6

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    come_msg = event.message.text
    come_ID = event.source.user_id

    if come_ID in session :
        if session[come_ID]['state'] == int(State.UploadName) :
            session[come_ID]['name'] = come_msg
            session[come_ID]['state'] = int(State.UploadType)
            reply_msg = TextSendMessage(text='餐廳類別：')
        elif session[come_ID]['state'] == int(State.UploadType):
            session[come_ID]['type'] = come_msg
            session[come_ID]['state'] = int(State.UploadPrice)
            reply_msg = TextSendMessage(text='價格區間（ex:100~200）：')
        elif session[come_ID]['state'] == int(State.UploadPrice):
            price = come_msg.split('~')
            if len(price) != 2 :
                price = come_msg.split('～')

            if len(price) != 2 :
                reply_msg = TextSendMessage(text='輸入格式錯誤 （ex:100~200）')
            else :
                low_price = price[0]
                high_price = price[1]
                if low_price.isnumeric() and high_price.isnumeric() :
                    new_restaurant = restaurant(restaurant_name=session[come_ID]['name'], restaurant_type=session[come_ID]['type'], low_price=int(low_price),
                                                high_price=int(high_price))
                    db.session.add(new_restaurant)
                    db.session.commit()
                    reply_msg = TextSendMessage(text='上傳成功')
                    session.pop(come_ID)
                else :
                    reply_msg = TextSendMessage(text='輸入格式錯誤 （ex:100~200）')
        elif session[come_ID]['state'] == int(State.SearchRestaurant):
            if come_msg.isnumeric() :
                if int(come_msg) == 1 :
                    session[come_ID]['state'] = int(State.SearchType)
                    reply_msg = TextSendMessage(text=allTypes())
                elif int(come_msg) == 2 :
                    session[come_ID]['state'] = int(State.SearchPrice)
                    reply_msg = TextSendMessage(text='輸入最高價格或價格區間\n（ex:300或100~300）')
                else:
                    reply_msg = TextSendMessage(text='輸入格式錯誤 輸入1或2進行查詢')
            else :
                reply_msg = TextSendMessage(text='輸入格式錯誤 輸入1或2進行查詢')
        elif session[come_ID]['state'] == int(State.SearchType):
            searchString = '%' + come_msg + '%'
            result = restaurant.query.filter(restaurant.restaurant_type.like(searchString)).all()
            reply_msg = TextSendMessage(text=searchResult(result))
            session.pop(come_ID)
        elif session[come_ID]['state'] == int(State.SearchPrice):
            if come_msg.isnumeric() :
                result = restaurant.query.filter(restaurant.high_price <= int(come_msg)).all()
                reply_msg = TextSendMessage(text=searchResult(result))
                session.pop(come_ID)
            else :
                price = come_msg.split('~')
                if len(price) != 2:
                    price = come_msg.split('～')

                if len(price) != 2:
                    reply_msg = TextSendMessage(text='輸入格式錯誤 （ex:100~200）')
                else :
                    low_price = price[0]
                    high_price = price[1]
                    result = restaurant.query.filter(and_(restaurant.high_price <= int(high_price), restaurant.low_price <= int(high_price))).all()
                    reply_msg = TextSendMessage(text=searchResult(result))
                    session.pop(come_ID)
        else :
            reply_msg = TextSendMessage(text='Error!')
    else :
        if come_msg == '隨機選擇':
            reply_msg = TextSendMessage(text=randomSelectRestaurant())
        elif come_msg == '查詢餐廳':
            reply_msg = TextSendMessage(text='查詢類別\n1.類型\n2.價格')
            session[come_ID] = { 'state' : int(State.SearchRestaurant), 'name' : '', 'type' : '', 'low_price' : 0, 'high_price' : 0}
        elif come_msg == '列出所有':
            reply_msg = TextSendMessage(text=listAllRestaurant())
        elif come_msg == '上傳餐廳':
            reply_msg = TextSendMessage(text='餐廳名稱：')
            session[come_ID] = { 'state' : int(State.UploadName), 'name' : '', 'type' : '', 'low_price' : 0, 'high_price' : 0}
        else:
            reply_msg = TextSendMessage(text='501 Not Implemented')

    line_bot_api.reply_message(event.reply_token, reply_msg)


def listAllRestaurant():
    _str = ""
    for i in restaurant.query.all():
        if _str != "":
            _str = _str + '\n'

        _str = _str + str(i.__dict__['restaurant_name'])

    return _str

def randomSelectRestaurant():
    selected = random.choice(restaurant.query.all()).__dict__
    _str = "餐廳名稱：{}\n餐廳類型：{}\n價格區間：{}~{}".format(selected['restaurant_name'], selected['restaurant_type'] ,selected['low_price'] ,selected['high_price'])
    return _str

def allTypes():
    _str = ""
    _set = set()
    for i in restaurant.query.all():
        _list = i.__dict__['restaurant_type'].split(',')
        for j in _list:
            _set.add(j)

    _str = '目前類別有：'
    for i in _set :
        _str = _str + '\n' + str(i)

    return _str

def searchResult(result):
    if len(result) == 0 :
        return '查無符合餐廳'
    else :
        _str = '查詢結果：'
        for i in result:
            _str = _str + "\n\n餐廳名稱：{}\n餐廳類型：{}\n價格區間：{}~{}".format(i.__dict__['restaurant_name'], i.__dict__['restaurant_type'],
                                                         i.__dict__['low_price'], i.__dict__['high_price'])
        return _str

import os
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port ,debug=True)
