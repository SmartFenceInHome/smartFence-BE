from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/test', methods=['POST'])
def test() :
    data = request.get_json()

    return jsonify({
        "status": "success",
        "message": "test succeeded",
        "data": data
    })
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)