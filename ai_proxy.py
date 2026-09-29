import json
import os
import re
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlencode, urlsplit
from urllib.request import Request, urlopen

BASE_DIR = Path(__file__).resolve().parent
GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
LLAMA_MODEL = "llama-3.3-70b-versatile"
DEEPSEEK_MODEL = "deepseek-r1-distill-llama-70b"
MAX_BODY_BYTES = 20_000_000
GEMINI_MODELS = {
    "gemini-3.6-flash",
    "gemini-3.7-flash",
    "gemini-3.8-flash",
    "gemini-3.5-flash",
    "gemini-flash-latest",
    "gemini-2.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash-lite",
}


class AppHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def send_json(self, status, payload):
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        allowed_origin = self.allowed_request_origin()
        if allowed_origin:
            self.send_header("Access-Control-Allow-Origin", allowed_origin)
            self.send_header("Vary", "Origin")
        self.end_headers()
        self.wfile.write(encoded)

    def allowed_request_origin(self):
        origin_header = self.headers.get("Origin", "")
        origin = urlsplit(origin_header)
        if origin.scheme not in {"http", "https"} or not origin.netloc or origin.path not in {"", "/"}:
            return ""
        normalized_origin = origin_header.rstrip("/")
        if origin.netloc == self.headers.get("Host"):
            return normalized_origin
        allowed_origins = {
            item.strip().rstrip("/")
            for item in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",")
            if item.strip()
        }
        return normalized_origin if normalized_origin in allowed_origins else ""

    def do_GET(self):
        request_path = unquote(urlsplit(self.path).path)
        if request_path == "/health":
            self.send_json(200, {
                "ok": True,
                "geminiApiKeyConfigured": bool(os.environ.get("GEMINI_API_KEY")),
                "groqApiKeyConfigured": bool(os.environ.get("GROQ_API_KEY")),
            })
            return
        if request_path not in {"/", "/index.html", "/index (1).html"}:
            self.send_json(404, {"error": "Not found."})
            return
        try:
            content = (BASE_DIR / "index (1).html").read_bytes()
        except OSError:
            self.send_json(404, {"error": "App HTML file not found."})
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def do_HEAD(self):
        self.send_response(405)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_OPTIONS(self):
        allowed_origin = self.allowed_request_origin()
        if not allowed_origin:
            self.send_json(403, {"error": "Cross-origin model requests are not allowed."})
            return
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", allowed_origin)
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "600")
        self.send_header("Vary", "Origin")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        route = urlsplit(self.path).path
        if route == "/api/gemini":
            self.handle_gemini_request()
        elif route == "/api/animation":
            self.handle_model_request(LLAMA_MODEL, "animation")
        elif route == "/api/math-review":
            self.handle_model_request(DEEPSEEK_MODEL, "math-review")
        elif route == "/api/math-solve":
            self.handle_model_request(DEEPSEEK_MODEL, "math-solve")
        else:
            self.send_json(404, {"error": "Unknown API route."})

    def handle_gemini_request(self):
        if not self.allowed_request_origin():
            self.send_json(403, {"error": "Cross-origin model requests are not allowed."})
            return
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            self.send_json(503, {"error": "Set GEMINI_API_KEY in the backend environment."})
            return
        try:
            body_size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_json(400, {"error": "Invalid Content-Length header."})
            return
        if body_size <= 0 or body_size > MAX_BODY_BYTES:
            self.send_json(413, {"error": "Request body is empty or too large."})
            return
        try:
            payload = json.loads(self.rfile.read(body_size))
        except (ValueError, UnicodeDecodeError):
            self.send_json(400, {"error": "Invalid JSON request."})
            return
        if not isinstance(payload, dict):
            self.send_json(400, {"error": "Expected a JSON object."})
            return

        model = payload.get("model")
        streaming = payload.get("stream") is True
        request_body = payload.get("request") if streaming else {
            key: value for key, value in payload.items() if key not in {"model", "stream"}
        }
        if model not in GEMINI_MODELS:
            self.send_json(400, {"error": "Gemini model is not allowed."})
            return
        if not isinstance(request_body, dict) or not isinstance(request_body.get("contents"), list):
            self.send_json(400, {"error": "Invalid Gemini request body."})
            return

        method = "streamGenerateContent" if streaming else "generateContent"
        query = urlencode({"alt": "sse", "key": api_key}) if streaming else urlencode({"key": api_key})
        request = Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:{method}?{query}",
            data=json.dumps(request_body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=120) as response:
                if streaming:
                    self.send_response(response.status)
                    self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Connection", "close")
                    self.send_header("Access-Control-Allow-Origin", self.allowed_request_origin())
                    self.send_header("Vary", "Origin")
                    self.end_headers()
                    self.close_connection = True
                    try:
                        while True:
                            chunk = response.read1(8192)
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        self.close_connection = True
                    return
                result = json.loads(response.read())
            self.send_json(200, result)
        except HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")[:3000]
            self.send_json(error.code, {"error": {"message": details or "Google Gemini request failed."}})
        except (URLError, TimeoutError, json.JSONDecodeError) as error:
            self.send_json(502, {"error": {"message": str(error)[:500]}})

    def handle_model_request(self, model, task):
        origin = urlsplit(self.headers.get("Origin", ""))
        if origin.scheme not in {"http", "https"} or origin.netloc != self.headers.get("Host"):
            self.send_json(403, {"error": "Cross-origin model requests are not allowed."})
            return
        api_key = os.environ.get("GROQ_API_KEY", "").strip()
        if not api_key:
            self.send_json(503, {"error": "Set GROQ_API_KEY before starting the proxy."})
            return

        try:
            body_size = int(self.headers.get("Content-Length", "0"))
        except (ValueError, UnicodeDecodeError):
            self.send_json(400, {"error": "Invalid Content-Length header."})
            return
        if body_size <= 0 or body_size > MAX_BODY_BYTES:
            self.send_json(413, {"error": "Request body is empty or too large."})
            return
        try:
            payload = json.loads(self.rfile.read(body_size))
        except (ValueError, UnicodeDecodeError):
            self.send_json(400, {"error": "Invalid JSON request."})
            return
        if not isinstance(payload, dict):
            self.send_json(400, {"error": "Expected a JSON object."})
            return
        try:
            messages = self.build_messages(task, payload)
        except ValueError as error:
            self.send_json(400, {"error": str(error)})
            return

        request_body = {
            "model": model,
            "messages": messages,
            "max_tokens": 8192 if task == "animation" else 2600 if task == "math-solve" else 1800,
        }
        if task == "animation":
            request_body["temperature"] = 0.15

        request = Request(
            GROQ_CHAT_URL,
            data=json.dumps(request_body).encode("utf-8"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=120) as response:
                result = json.loads(response.read())
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            if isinstance(content, list):
                content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
            if not isinstance(content, str) or not content.strip():
                self.send_json(502, {"error": "The model returned an empty response."})
                return
            if task == "math-review":
                content = re.sub(r"<think>[\s\S]*?(?:</think>|$)", "", content, flags=re.IGNORECASE).strip()
                if not content:
                    self.send_json(502, {"error": "The model returned no final review."})
                    return
            self.send_json(200, {"text": content.strip()})
        except HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")[:2000]
            self.send_json(error.code, {"error": "Groq API request failed.", "details": details})
        except (URLError, TimeoutError, json.JSONDecodeError) as error:
            self.send_json(502, {"error": "Could not complete the model request.", "details": str(error)[:500]})

    @staticmethod
    def build_messages(task, payload):
        if task == "animation":
            prompt = payload.get("prompt", "")
            if not isinstance(prompt, str) or not prompt.strip():
                raise ValueError("Missing animation prompt.")
            return [
                {"role": "system", "content": prompt[:120_000]},
                {
                    "role": "user",
                    "content": "Generate the AnimScene JSON requested by the system instructions. Return only one <anim_code>{\"steps\":[...]}</anim_code> block. Do not return executable JavaScript, HTML, Python, or markdown fences.",
                },
            ]

        question = payload.get("question", "")
        answer = payload.get("answer", "")
        if not isinstance(question, str) or not question.strip():
            raise ValueError("A math question is required.")
        if task == "math-solve":
            system_prompt = (
                "Bạn là gia sư Toán THPT. Hãy tự giải đề bài độc lập, không giả định có lời giải mẫu. "
                "Nêu mục tiêu, ý tưởng, điều kiện áp dụng, các bước có giải thích và phép kiểm tra kết quả. "
                "Viết bằng tiếng Việt dễ hiểu, dùng LaTeX với dấu $...$ hoặc $$...$$. "
                "Nếu thiếu dữ kiện, nói rõ điều còn thiếu thay vì đoán; không tiết lộ suy nghĩ nội bộ."
            )
            return [{"role": "system", "content": system_prompt}, {"role": "user", "content": question[:12_000]}]
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError("A proposed answer is required for math review.")
        system_prompt = (
            "Bạn là người phản biện Toán học độc lập cho lời giải THPT. Kiểm tra từng phép biến đổi, phép tính, "
            "điều kiện áp dụng, miền xác định và đơn vị. Không mặc định lời giải đúng. Không tiết lộ suy nghĩ nội bộ. "
            "Chỉ trả lời ngắn bằng tiếng Việt theo cấu trúc: Kết luận (Đúng / Có lỗi / Chưa đủ dữ kiện), "
            "Điểm cần sửa (nếu có, trích bước cụ thể), Cách kiểm tra. Nếu đúng, nói rõ đã rà soát những gì; "
            "không bịa lỗi và không viết lại toàn bộ lời giải."
        )
        user_prompt = f"Đề bài:\n{question[:12_000]}\n\nLời giải cần kiểm tra:\n{answer[:24_000]}"
        return [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]


def main():
    host = os.environ.get("AI_PROXY_HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", os.environ.get("AI_PROXY_PORT", "8787")))
    server = ThreadingHTTPServer((host, port), AppHandler)
    print(f"AI proxy and app listening on {host}:{port}")
    print("Health check: /health")
    server.serve_forever()


if __name__ == "__main__":
    main()
