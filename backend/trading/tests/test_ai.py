"""AI 助手:服务端 VIP 强制校验与问答契约。"""
from rest_framework import status

from .base import BaseAPITestCase


class AITests(BaseAPITestCase):
    def test_query_requires_vip(self):
        self.auth()
        resp = self.client.post("/api/ai/query/", {"text": "怎么看大盘?"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("VIP", str(resp.data["detail"]))

    def test_activate_then_query_contract(self):
        self.auth()
        self.client.post("/api/ai/activate/")
        resp = self.client.post("/api/ai/query/", {"text": "分析我的持仓"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("answer", resp.data)
        conversation = resp.data["conversation"]
        self.assertEqual(len(conversation["messages"]), 2)  # 用户 + 机器人
        self.assertEqual(conversation["messages"][0]["sender"], "user")

    def test_query_continues_conversation(self):
        self.auth()
        self.client.post("/api/ai/activate/")
        r1 = self.client.post("/api/ai/query/", {"text": "你好"}, format="json").data
        cid = r1["conversation"]["id"]
        r2 = self.client.post("/api/ai/query/", {"text": "继续", "conversation_id": cid}, format="json").data
        self.assertEqual(r2["conversation"]["id"], cid)
        self.assertEqual(len(r2["conversation"]["messages"]), 4)

    def test_empty_text_rejected(self):
        self.auth()
        self.client.post("/api/ai/activate/")
        resp = self.client.post("/api/ai/query/", {"text": "  "}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_activate_contract(self):
        self.auth()
        resp = self.client.post("/api/ai/activate/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["detail"], "activated")
        self.assertTrue(resp.data["is_vip"])
        self.assertIn("balance", resp.data["cash"])
