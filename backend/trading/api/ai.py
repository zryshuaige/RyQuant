"""AI 助手:问答(登录即可)与会话延续。"""
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import AIConversation, AIMessage
from ..services.errors import BusinessError
from ..serializers import AIConversationSerializer
from ..services.ai_client import get_ai_reply
from .throttling import AIThrottle


class AIQueryView(APIView):
    """
    POST /api/ai/query/ — body: {text, conversation_id?}
    未传 conversation_id 时新建会话;传入本人会话 id 则续聊(携带历史上下文)。
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [AIThrottle]

    def post(self, request):
        text = str(request.data.get("text", "")).strip()
        if not text:
            raise BusinessError("请输入你的问题")

        conversation = None
        conversation_id = request.data.get("conversation_id")
        if conversation_id not in (None, ""):
            try:
                conversation = AIConversation.objects.get(pk=int(conversation_id), user=request.user)
            except (AIConversation.DoesNotExist, TypeError, ValueError):
                conversation = None

        history = []
        if conversation is not None:
            history = [
                {"sender": m.sender, "content": m.content}
                for m in conversation.messages.order_by("-created_at", "-pk")[:20]
            ][::-1]  # 取最新 20 条后恢复升序,避免长会话喂入陈旧上下文

        answer = get_ai_reply(request.user, text, history)

        if conversation is None:
            conversation = AIConversation.objects.create(user=request.user, title=text[:50])
        AIMessage.objects.create(conversation=conversation, sender="user", content=text)
        AIMessage.objects.create(conversation=conversation, sender="bot", content=answer)

        return Response({"answer": answer, "conversation": AIConversationSerializer(conversation).data})