from flask import Flask

app = Flask(__name__)
PATH = "/dynamic"


@app.route(PATH)
def hello() -> str:
    return "ok"
