import { projectStore } from "@/store/index";
const pinia = projectStore();
import { CreateConversationApi } from "@/api/request";
export const userSendMessage = async (userMessage: string) => {
  if (userMessage.trim() === "") {
    uni.showToast({
      icon: "none",
      title: "请输入内容",
    });
    return;
  }
  // 开启模型正在回福中
  pinia.disabledStatus = true;
  // 如果会话id为空，就创建会话id
  if (pinia.sessionId === "") {
    const res = await CreateConversationApi();
    pinia.sessionId = res.data.sessionId;
    pinia.conversationList.unshift({ title: userMessage.trim(), created_at: "", thread_id: pinia.sessionId });
    pinia.sessionIndex = 0;
  }
  pinia.messageList.push(
    {
      role: "user",
      content: userMessage.trim(),
    },
    {
      role: "assistant",
      content: "",
      loadingCircle: true,
      toolList: [],
      toolThink: true,
      mapDataList: [],
    }
  );
  pinia.socketTask.send({
    data: JSON.stringify({
      sessionId: pinia.sessionId,
      content: userMessage.trim(),
    }),
    success: () => {
      console.log("发送成功");
    },
    fail: (err: any) => {
      console.log("发送失败:", err);
    },
  });
};
