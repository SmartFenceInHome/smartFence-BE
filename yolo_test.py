from flask import Flask, request, jsonify
import logging

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)

@app.route('/test', methods=['POST'])
def test() :
    app.logger.info('Request received: %s', request.json)
    # data = request.get_json()
    return {"message": "Test successful"}

    # return jsonify({
    #     "status": "success",
    #     "message": "test succeeded",
    #     "data": data
    # })
if __name__ == '__main__':
    print("server start on http://0.0.0.0:9001")
    app.run(host='0.0.0.0', port=9001)