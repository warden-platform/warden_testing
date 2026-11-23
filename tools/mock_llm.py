# -*- coding = utf-8 -*-
"""Mock OpenAI 兼容 LLM 服务（SSE 流式），供 AI 助手黑盒测试。

warden 的 AI runner 通过 go-openai 以 stream=true 调 {base_url}/chat/completions，
这里实现一个本地 HTTP 服务返回固定流式 completion，无需真实 LLM。
"""
from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # 丢弃请求体（Authorization 头无需校验）
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length:
            self.rfile.read(length)

        if not self.path.endswith("/chat/completions"):
            self.send_response(404)
            self.end_headers()
            return

        chunks = [
            (
                'data: {"id":"chatcmpl-mock","object":"chat.completion.chunk",'
                '"choices":[{"index":0,"delta":{"role":"assistant","content":"这是 mock '
                '回答"},"finish_reason":null}]}\n\n'
            ),
            'data: {"id":"chatcmpl-mock","object":"chat.completion.chunk",'
            '"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}\n\n',
            "data: [DONE]\n\n",
        ]
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        for chunk in chunks:
            self.wfile.write(chunk.encode("utf-8"))
            self.wfile.flush()

    def log_message(self, *args) -> None:  # 静默访问日志
        pass


class MockLLMServer:
    """固定端口的 mock LLM。start() 后监听，stop() 释放。"""

    def __init__(self, host: str = "127.0.0.1", port: int = 9100):
        self.httpd = HTTPServer((host, port), _Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        host, port = self.httpd.server_address[:2]
        return f"http://{host}:{port}/v1"

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()