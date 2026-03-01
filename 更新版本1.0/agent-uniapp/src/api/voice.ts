// 腾讯云语音识别
import { ref } from "vue";
// websocket实例
export let socketTask = null as any;
// 语音返回结果
export let voiceResText = ref("");
let asrSegments: any = []; // 存放每段 index 的最终文本
export const initVoice = async (wsurl: string) => {
  // @ts-ignore
  socketTask = await wx.connectSocket({
    url: wsurl,
    method: "GET",
  });
  // 收到消息
  socketTask.onMessage((res: any) => {
    console.log(res);
    const result = JSON.parse(res.data);
    // 握手成功
    if (result.code === 0) {
      // 语音返回结果
      if (result.result !== undefined && result.result.voice_text_str !== undefined) {
        // voiceResText.value = result.result.voice_text_str;
        const index: number = result.result.index;
        const text: string = result.result.voice_text_str;
        const sliceType: number = result.result.slice_type;
        // 初始化该 index 的段
        if (!asrSegments[index]) {
          asrSegments[index] = "";
        }
        // slice_type 0 临时覆盖
        if (sliceType === 0) {
          asrSegments[index] = text;
        }
        // slice_type 1 覆盖
        if (sliceType === 1) {
          asrSegments[index] = text;
          // 这个 index 已经定稿，可以在 UI 中固化
        }
        // slice_type 2最终wanzheng
        if (sliceType === 2) {
          asrSegments[index] = text;
        }
        // 拼接完整语音
        voiceResText.value = asrSegments.filter(Boolean).join("");
      }
    } else if (result.code === 4008) {
      uni.showToast({
        icon: "none",
        title: "没有听到你说话",
      });
    } else {
      uni.showToast({
        icon: "none",
        title: "连接失败",
      });
    }
  });
  // 连接成功
  socketTask.onOpen(() => {
    console.log("websocket连接上voice");
  });
  // 连接关闭
  socketTask.onClose(() => {
    console.log("连接关闭voice");
  });
  // 连接错误
  socketTask.onError((err: any) => {
    console.log("连接错误voice:", err);
  });
};
