import json
import re
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
PORT = 8000

SESSION_STORE = {}


def build_chat_response(message: str, session_id: str | None = None):
    session = SESSION_STORE.setdefault(session_id or str(uuid.uuid4()), {
        "name": None,
        "phone": None,
        "email": None,
        "project_type": None,
        "location": None,
        "turns": 0,
    })
    session["turns"] += 1

    if not message:
        return {
            "reply": "Hello! I’m Dennik Assistant. I can answer basic questions about our services and help collect your project details. What would you like to build?",
            "handoff": False,
            "whatsappUrl": None,
            "collected": session_to_payload(session),
        }

    text = message.strip()
    lowered = text.lower()

    if not session.get("name"):
        name_match = re.search(r"(?:my name is|i am|i'm|this is)\s+([a-zA-Z][a-zA-Z .'-]+)", text)
        if name_match:
            session["name"] = name_match.group(1).strip()

    if not session.get("phone"):
        phone_match = re.search(r"(?:\+?27|0)?\s*(\d[\d\s]{8,12})", text)
        if phone_match:
            session["phone"] = phone_match.group(1).replace(" ", "")

    if not session.get("email"):
        email_match = re.search(r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", text)
        if email_match:
            session["email"] = email_match.group(0)

    if not session.get("project_type"):
        if any(k in lowered for k in ["roof", "roofing", "structural", "steel", "frame", "wall"]):
            session["project_type"] = "Structural / Roofing"
        elif any(k in lowered for k in ["ceiling", "interior", "finish", "finishes", "paint", "lighting"]):
            session["project_type"] = "Interior Finishes"
        elif any(k in lowered for k in ["renov", "addition", "extend", "extension", "remodel"]):
            session["project_type"] = "Renovations / Additions"
        elif any(k in lowered for k in ["house", "home", "build", "building"]):
            session["project_type"] = "Residential Construction"

    if not session.get("location"):
        loc_match = re.search(r"(?:in|from|near|around)\s+([A-Za-z][A-Za-z .'-]+)", text)
        if loc_match:
            session["location"] = loc_match.group(1).strip()

    services = [
        "Residential Construction",
        "Structural & Roofing",
        "Interior Finishes",
        "Renovations & Additions",
    ]

    if any(k in lowered for k in ["quote", "price", "cost", "estimate", "budget", "urgent", "call me", "contact me", "consult"]):
        missing = [field for field in ["name", "phone", "email"] if not session.get(field)]
        summary = f"Project: {session.get('project_type') or 'Not yet specified'} | Location: {session.get('location') or 'Not yet specified'}"
        if missing:
            reply = (
                f"I can help arrange a consultation. I’m collecting your project details first."
                f" Please share your {' , '.join(missing)} so I can hand this off properly."
            )
        else:
            reply = (
                "I can connect you with our team on WhatsApp right away. "
                "A summary of your enquiry has been prepared for the handoff."
            )
        return {
            "reply": reply,
            "handoff": True,
            "whatsappUrl": build_whatsapp_url(session, text),
            "collected": session_to_payload(session),
        }

    if any(k in lowered for k in ["service", "services", "what do you do", "do you build"]):
        reply = "We specialise in: " + ", ".join(services) + ". Which service are you interested in?"
    elif any(k in lowered for k in ["hello", "hi", "hey"]):
        reply = "Hello! I’m Dennik Assistant. I can help with project enquiries, service info, and collecting the details we need for a consultation. What are you planning?"
    elif any(k in lowered for k in ["roof", "roofing", "structural"]):
        reply = "We handle structural work, roofing, framing, and weather-resistant envelope solutions. Tell me a bit more about your project and location."
    elif any(k in lowered for k in ["finish", "ceiling", "interior"]):
        reply = "We provide interior finishing services such as ceilings, lighting integration, and detail work. Would you like to share your project location or timeline?"
    elif any(k in lowered for k in ["renov", "addition", "extension"]):
        reply = "We also manage renovations and additions for homes that need more space or a refresh. What would you like to change?"
    elif any(k in lowered for k in ["house", "home", "build", "building"]):
        reply = "We can help with new residential construction from groundwork to handover. Share your preferred location and a rough timeline and I’ll prepare a handoff for our team."
    else:
        reply = "I can help with questions about our residential construction, structural and roofing work, interior finishes, and renovations. Tell me a little about your project and I’ll guide you from there."

    if session["turns"] >= 2 and not session.get("phone") and not session.get("email"):
        reply += " If you want a faster response, send your phone number or email and I’ll hand this over to our team."

    return {
        "reply": reply,
        "handoff": False,
        "whatsappUrl": None,
        "collected": session_to_payload(session),
    }


def build_whatsapp_url(session, inquiry):
    base = "https://wa.me/270000000000?text="
    summary = (
        f"Hello Dennik Construction, I need help with a project. "
        f"Name: {session.get('name') or 'Not provided'}. "
        f"Phone: {session.get('phone') or 'Not provided'}. "
        f"Email: {session.get('email') or 'Not provided'}. "
        f"Project: {session.get('project_type') or 'Not provided'}. "
        f"Location: {session.get('location') or 'Not provided'}. "
        f"Inquiry: {inquiry[:120]}"
    )
    return base + requests_quote(summary)


def requests_quote(value: str) -> str:
    return re.sub(r"\s+", "%20", value)


def session_to_payload(session):
    return {
        "name": session.get("name"),
        "phone": session.get("phone"),
        "email": session.get("email"),
        "project_type": session.get("project_type"),
        "location": session.get("location"),
    }


class ChatHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/chat":
            self._send_json({"status": "ok"})
            return

        file_path = ROOT / path.lstrip("/")
        if file_path.is_file():
            self._serve_file(file_path)
            return

        if path in ["/", ""]:
            self._serve_file(ROOT / "index.html")
            return

        self.send_error(404, "Not Found")

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/api/chat":
            self.send_error(404, "Not Found")
            return

        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        try:
            payload = json.loads(body or "{}")
        except json.JSONDecodeError:
            payload = {}

        message = payload.get("message", "")
        session_id = payload.get("session_id")
        response = build_chat_response(message, session_id)
        response["session_id"] = session_id or next(iter(SESSION_STORE)) if SESSION_STORE else str(uuid.uuid4())
        self._send_json(response)

    def _serve_file(self, file_path: Path):
        content_type = "text/html; charset=utf-8" if file_path.suffix.lower() in {".html", ".htm"} else "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(file_path.read_bytes())

    def _send_json(self, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


def run_server(port: int = PORT):
    server = ThreadingHTTPServer(("0.0.0.0", port), ChatHandler)
    print(f"Dennik assistant server running on http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
