"""AI 助手:登录门槛与问答契约。"""
from rest_framework import status

from .base import BaseAPITestCase


class AITests(BaseAPITestCase):
    def test_query_requires_auth(self):
        self.anon()
        resp = self.client.post("/api/ai/query/", {"text": "怎么看大盘?"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_query_contract(self):
        self.auth()
        resp = self.client.post("/api/ai/query/", {"text": "分析我的自选"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("answer", resp.data)
        conversation = resp.data["conversation"]
        self.assertEqual(len(conversation["messages"]), 2)  # 用户 + 机器人
        self.assertEqual(conversation["messages"][0]["sender"], "user")

    def test_query_continues_conversation(self):
        self.auth()
        r1 = self.client.post("/api/ai/query/", {"text": "你好"}, format="json").data
        cid = r1["conversation"]["id"]
        r2 = self.client.post("/api/ai/query/", {"text": "继续", "conversation_id": cid}, format="json").data
        self.assertEqual(r2["conversation"]["id"], cid)
        self.assertEqual(len(r2["conversation"]["messages"]), 4)

    def test_empty_text_rejected(self):
        self.auth()
        resp = self.client.post("/api/ai/query/", {"text": "  "}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)