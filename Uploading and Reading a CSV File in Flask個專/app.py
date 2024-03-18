import os
import ssl
import urllib
import json
import pandas as pd
import datetime
from flask import Flask, request, render_template, session, send_file
from werkzeug.utils import secure_filename

# Constants
UPLOAD_FOLDER = os.path.join('staticFiles', 'uploads')
ALLOWED_EXTENSIONS = {'csv'}
SCORE_URL = 'http://695c3b83-9ad1-4828-9657-73bfbaa9f578.eastus.azurecontainer.io/score'
HEADERS = {'Content-Type':'application/json'}

# Flask app
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = 'This is your secret key to utilize session in Flask'

# 如果允許自簽名 HTTPS，則設置為不驗證 SSL 證書的上下文
def allow_self_signed_https(allowed):
    if allowed and not os.environ.get('PYTHONHTTPSVERIFY', '') and getattr(ssl, '_create_unverified_context', None):
        ssl._create_default_https_context = ssl._create_unverified_context

# 使用模型進行預測
def model_predict(data):
    # 列出模型需要的欄位
    required_columns = ['HomePlanet', 'CryoSleep', 'RoomService','Spa','VRDeck']

    # 刪除不需要的欄位
    data = pd.DataFrame(data)
    for column in data.columns:
        if column not in required_columns:
            data = data.drop(column, axis=1)

    
    # 將數據轉換為字典格式
    # data = pd.DataFrame(data)
    inputs = data.to_dict(orient='records')
    # 創建請求體
    body = {"Inputs": {"data": inputs}, "GlobalParameters": {"method": "predict"}}
    # 將請求體轉換為字節流
    body = str.encode(json.dumps(body))
    # 創建請求
    req = urllib.request.Request(SCORE_URL, body, HEADERS)
    try:
        # 發送請求並獲取響應
        response = urllib.request.urlopen(req)
        result = response.read()
        result_decode = result.decode('utf-8')
        # 返回解析後的 JSON 響應
        return json.loads(result_decode)
    except urllib.error.HTTPError as error:
        print("The request failed with status code: " + str(error.code))
        print(error.info())
        print(error.read().decode("utf8", 'ignore'))

# 提交數據並獲取預測結果
def submit(data):
    result = model_predict(data)
    return result['Results']

# 處理文件上傳和預測
@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        # 獲取上傳的文件
        f = request.files.get('file')
        data_filename = secure_filename(f.filename)
        # 將文件名儲存到 session
        session['data_filename'] = data_filename
        # 保存文件
        f.save(os.path.join(app.config['UPLOAD_FOLDER'],data_filename))
        # 讀取文件數據
        session['uploaded_data_file_path'] = os.path.join(app.config['UPLOAD_FOLDER'],data_filename)
        data = pd.read_csv(session['uploaded_data_file_path'])
        json_data = data.to_json(orient='records')
        # 獲取預測結果
        result = submit(json.loads(json_data))
        session['result'] = result
        # 返回預測結果
        return render_template('index2.html', prediction=result)
    return render_template("index.html")

# 處理提交數據並獲取預測結果
@app.route('/submit', methods=['POST'])
def submit_route():
    if request.method == 'POST':
        # 獲取提交的數據
        data = request.get_json()
        # 獲取預測結果
        result = submit(data)
        session['result'] = result
        # 返回預測結果
        return render_template('index2.html', prediction=result)

# 顯示數據
@app.route('/show_data')
def show_data():
    data_file_path = session.get('uploaded_data_file_path', None)
    uploaded_df = pd.read_csv(data_file_path, encoding='unicode_escape')
    result = session.get('result', None)
    uploaded_df['Transported'] = result
    uploaded_df.to_csv('output.csv', index=False)
    uploaded_df_html = uploaded_df.to_html(classes='table')
    return render_template('show_csv_data.html', data_var=uploaded_df_html)

# 下載數據
@app.route('/download')
def download():
    df = pd.read_csv('output.csv')
    df = df.drop(['HomePlanet', 'CryoSleep','Cabin','Destination','Age','VIP','RoomService','FoodCourt','ShoppingMall','Spa','VRDeck','Name'], axis=1)
    
    # 獲取當前日期
    now = datetime.datetime.now()

    # 將日期格式化為 YYYYMMDD
    date_str = now.strftime('%Y%m%d')
    
    # 從 session 中獲取文件名
    data_filename = session.get('data_filename')
    
    # 創建新的文件名
    data_filename = data_filename.rsplit('.', 1)[0] + '-' +  date_str + '.' + data_filename.rsplit('.', 1)[1]
    
    df.to_csv(data_filename, index=False)
    return send_file(data_filename, as_attachment=True)

if __name__ == "__main__":
    allow_self_signed_https(True)
    app.run()