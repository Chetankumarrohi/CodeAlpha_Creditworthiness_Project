import json
import math
import sys
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.predictor import CreditPredictor

FRONTEND_DIR = BASE_DIR / "frontend"
predictor = CreditPredictor()


def format_inr(amount):
    amount = int(round(amount))
    sign = "-" if amount < 0 else ""
    s = str(abs(amount))
    if len(s) <= 3:
        return f"{sign}₹{s}"
    last3 = s[-3:]
    rest = s[:-3]
    parts = []
    while len(rest) > 2:
        parts.insert(0, rest[-2:])
        rest = rest[:-2]
    if rest:
        parts.insert(0, rest)
    return f"{sign}₹{','.join(parts)},{last3}"


def short_inr(amount):
    amount = float(amount)
    if abs(amount) >= 1_00_00_000:
        return f"₹{amount / 1_00_00_000:.2f} Cr"
    if abs(amount) >= 1_00_000:
        return f"₹{amount / 1_00_000:.2f} L"
    return format_inr(amount)


def calculate_emi(principal, annual_rate, years):
    principal = float(principal)
    annual_rate = float(annual_rate)
    years = int(years)

    months = years * 12
    monthly_rate = annual_rate / 12 / 100
    if monthly_rate == 0:
        emi = principal / months
    else:
        power = math.pow(1 + monthly_rate, months)
        emi = principal * monthly_rate * power / (power - 1)

    total_payment = emi * months
    total_interest = total_payment - principal

    return {
        "principal": principal,
        "annualRate": annual_rate,
        "tenureYears": years,
        "monthlyEmi": round(emi, 2),
        "totalInterest": round(total_interest, 2),
        "totalPayment": round(total_payment, 2),
        "formatted": {
            "principal": short_inr(principal),
            "monthlyEmi": format_inr(emi),
            "totalInterest": short_inr(total_interest),
            "totalPayment": short_inr(total_payment),
        },
    }


class NovaGenZHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def _send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, file_path, content_type):
        if not file_path.exists():
            self.send_error(404, "File Not Found")
            return
        body = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]

        if path == "/api/health":
            self._send_json(200, {
                "status": "healthy",
                "ml_ready": predictor.is_ready,
                "model": predictor.metadata.get("champion_model", "RuleBased")
            })
            return

        if path == "/api/funds":
            funds = [
                {"rank": 1, "name": "Nippon India Large Cap Fund", "category": "Large Cap", "return1Y": "34.2%", "return3Y": "22.5%"},
                {"rank": 2, "name": "Motilal Oswal Midcap Fund", "category": "Mid Cap", "return1Y": "48.5%", "return3Y": "31.4%"},
                {"rank": 3, "name": "Quant Small Cap Fund", "category": "Small Cap", "return1Y": "52.1%", "return3Y": "36.2%"},
                {"rank": 4, "name": "Parag Parikh Flexi Cap Fund", "category": "Flexi Cap", "return1Y": "35.6%", "return3Y": "24.2%"},
            ]
            self._send_json(200, {"funds": funds})
            return

        # Serve static web frontend
        if path == "/" or path == "/index.html":
            self._send_file(FRONTEND_DIR / "index.html", "text/html; charset=utf-8")
        elif path == "/styles.css":
            self._send_file(FRONTEND_DIR / "styles.css", "text/css; charset=utf-8")
        elif path == "/app.js":
            self._send_file(FRONTEND_DIR / "app.js", "application/javascript; charset=utf-8")
        else:
            self._send_json(404, {"error": "Not Found"})

    def do_POST(self):
        path = self.path.split("?")[0]
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b"{}"
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except json.JSONDecodeError:
            self._send_json(400, {"error": "Invalid JSON body"})
            return

        if path == "/api/predict":
            res = predictor.predict(payload)
            self._send_json(200, res)
            return

        if path == "/api/calculate-emi":
            try:
                principal = float(payload.get("principal", 1000000))
                rate = float(payload.get("annualRate", 9.5))
                years = int(payload.get("tenureYears", 5))
                res = calculate_emi(principal, rate, years)
                self._send_json(200, res)
            except Exception as e:
                self._send_json(400, {"error": str(e)})
            return

        self._send_json(404, {"error": "Endpoint not found"})


def run(port=8085):
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass

    server_address = ("", port)
    try:
        httpd = ThreadingHTTPServer(server_address, NovaGenZHandler)
        print(f"🚀 Nova Gen-Z Credit Server running at http://localhost:{port}")
        httpd.serve_forever()
    except OSError:
        port += 1
        server_address = ("", port)
        httpd = ThreadingHTTPServer(server_address, NovaGenZHandler)
        print(f"🚀 Nova Gen-Z Credit Server running at http://localhost:{port}")
        httpd.serve_forever()


if __name__ == "__main__":
    run()
