<template>
  <view class="chat-input">
    <view class="chat-backdrop">
      <!-- 输入框 -->
      <view class="user-input">
        <textarea
          placeholder="请输入内容"
          fixed
          maxlength="500"
          :auto-height="autoHeight"
          confirm-type="next"
          :show-confirm-bar="false"
          placeholder-class="textarea-color"
          cursor-spacing="20"
          @linechange="lineChange"
          v-model="userMessage"
        >
        </textarea>
      </view>
      <view class="voice-button">
        <image mode="widthFix" src="/static/yuyin.png" @click="voiceShow = true"></image>
      </view>
      <!-- 发送按钮 -->
      <view class="action-button">
        <button plain class="user-send" @click="sendMessage">
          <image src="/static/send-icon.png" mode="widthFix" class="send-button-image"></image>
        </button>
      </view>
    </view>
  </view>
  <!-- 语音 -->
  <view class="voice-view" v-if="voiceShow">
    <view class="voice-position">
      <view class="voice-text">
        <text>{{ voiceResText.trim() == "" ? "我在听，请说话" : voiceResText.trim() }}</text>
      </view>
      <view class="long-press">长按说话 松开发送</view>
      <view class="speak-btn" @longpress="longpress" @touchend="touchend">
        <text v-for="item in 12" :key="item"></text>
      </view>
      <!-- 关闭 -->
      <view class="close-btn" @click="voiceShow = false">
        <image src="/static/icon-close.png"></image>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { userSendMessage } from "@/api/send-message";
import { projectStore } from "@/store/index";
const pinia = projectStore();
import { VoiceUrlApi } from "@/api/request";
import { initVoice, socketTask, voiceResText } from "@/api/voice";
// 输入框自动增高
const autoHeight = ref(true);
// 输入框行数变化
const lineChange = (event: { detail: { lineCount: number } }) => {
  autoHeight.value = event.detail.lineCount >= 4 ? false : true;
};
const userMessage = ref("");
// 发送消息
const sendMessage = () => {
  if (pinia.disabledStatus) return;
  userSendMessage(userMessage.value);
  userMessage.value = "";
};
// 语音和输入切换
const voiceShow = ref(false);
// 按住说话加动态背景颜色
const speakBtnBack = ref("#766ffe");
// 获取全局唯一的录音管理器
const recorderManager = uni.getRecorderManager();
// 监听录音错误事件
recorderManager.onError((res) => {
  const typeData = [
    {
      type: "operateRecorder:fail auth deny",
      text: "右上角里设置里打开麦克风",
    },
    {
      type: "operateRecorder:fail NotFoundError",
      text: "请打开麦克风才可以说话",
    },
  ];
  typeData.forEach((item) => {
    if (res.errMsg == item.type) {
      uni.showToast({
        icon: "none",
        title: item.text,
      });
    }
  });
});
// 长按开始
const longpress = async () => {
  console.log("长按开始");
  // 切换按住颜色
  speakBtnBack.value = "#FF3333";
  //请求捂手返回的url
  const voiceResUrl = await VoiceUrlApi();
  // 连接websocket开始握手
  await initVoice(voiceResUrl.data);
  // 开始录音
  recorderManager.start({
    duration: 100000,
    sampleRate: 16000,
    numberOfChannels: 1,
    encodeBitRate: 96000,
    format: "PCM",
    frameSize: 1,
  });
};
// 手指放开
const touchend = () => {
  console.log("手指放开");
  // 切换按住颜色
  speakBtnBack.value = "#766ffe";
  // 停止录音
  recorderManager.stop();
  // 如果没有识别到不发送
  if (voiceResText.value.trim() !== "") {
    voiceShow.value = false;
    userSendMessage(voiceResText.value.trim());
    voiceResText.value = "";
  }
};
// 实时输出录音
recorderManager.onFrameRecorded((res) => {
  // console.log(res);
  const buffer = new Uint8Array(res.frameBuffer);
  const CHUNK = 1280; //40ms pcm
  // 开始发送数据
  let offset = 0;
  while (offset < buffer.length) {
    const slice = buffer.slice(offset, offset + CHUNK);
    offset += CHUNK;
    socketTask.send({
      data: slice.buffer,
    });
  }
});
// 监听录音结束
recorderManager.onStop((res) => {
  console.log("录音结束了");
  console.log(res);
  // 通知腾讯云识别结束
  socketTask.send({
    data: JSON.stringify({ type: "end" }),
  });
});
</script>

<style scoped>
.chat-input {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 20rpx 20rpx 40rpx 20rpx;
  background-color: #dedfff;
  z-index: 99;
}
.chat-backdrop {
  display: flex;
  border: 1rpx solid #9490ef;
  border-radius: 40rpx;
  padding: 20rpx;
  background-color: #faf9fe;
  box-sizing: border-box;
}
.voice-button {
  display: flex;
  align-items: flex-end;
  margin: 0 25rpx;
}
.voice-button image {
  width: 60rpx;
}
.user-input {
  flex: 1;
  display: flex;
  align-items: center;
}
.textarea-color {
  color: #a29bf5;
}
.action-button {
  display: flex;
  align-items: flex-end;
}
button {
  padding: inherit !important;
  margin: inherit !important;
  line-height: inherit !important;
  border: none !important;
  background: none !important;
}
.user-send {
  width: 60rpx;
  height: 60rpx;
}
.send-button-image {
  width: 60rpx;
}
.voice-view {
  background-color: #ffffff;
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  border-top-right-radius: 40rpx;
  border-top-left-radius: 40rpx;
  z-index: 99;
  height: 520rpx;
}
.voice-position {
  position: relative;
}
.voice-text {
  padding: 0 70rpx;
  height: 230rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 40rpx;
  font-weight: bold;
}
.voice-text text {
  overflow-y: auto;
  max-height: 100%;
}
.long-press {
  text-align: center;
  position: absolute;
  bottom: -80rpx;
  left: 0;
  right: 0;
  font-size: 27rpx;
}
.speak-btn {
  display: flex;
  align-items: center;
  background-color: v-bind("speakBtnBack");
  border-radius: 40rpx;
  justify-content: center;
  padding: 30rpx 0;
  margin: 0 70rpx;
  position: absolute;
  bottom: -205rpx;
  right: 0;
  left: 0;
}
.speak-btn text {
  width: 13rpx;
  height: 24rpx;
  border-radius: 30rpx;
  background-color: #ffffff;
  margin: 0 6rpx;
}
.close-btn {
  width: 30rpx;
  height: 30rpx;
  position: absolute;
  top: 30rpx;
  right: 20rpx;
}
.close-btn image {
  width: 30rpx;
  height: 30rpx;
}
</style>
