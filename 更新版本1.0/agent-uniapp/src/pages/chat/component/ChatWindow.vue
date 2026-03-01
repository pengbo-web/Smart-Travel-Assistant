<template>
  <view class="chat-message" v-for="(item, index) in pinia.messageList" :key="index">
    <!-- 用户消息 -->
    <view class="user-message" v-if="item.role === 'user'">
      <text>{{ item.content }}</text>
    </view>
    <!-- 工具回复的消息 -->
    <!-- <view class="tool-message" v-if="item.role === 'assistant' && item.toolList && item.toolList.length > 0">
      <text class="tool-think">{{ item.toolThink ? "分析思考中..." : "分析思考完毕" }}</text>
      <ToolSteps :tool-list="item.toolList"></ToolSteps>
    </view> -->
    <!-- 偏好卡片 -->
    <view v-if="item.role === 'preference_card' && item.preferenceCard">
      <PreferenceCard
        :card-data="item.preferenceCard"
        :message-index="index"
      />
    </view>
    <!-- 模型回复的消息 -->
    <view class="ai-message" v-if="item.role === 'assistant' && item.content != ''">
      <towxml :nodes="appContext.$towxml(item.content, 'markdown')"></towxml>
      <!-- 地图 -->
      <view v-if="item.mapDataList && item.mapDataList.length > 0">
        <Mapa style="width: 100%; height: auto" :map-data-list="item.mapDataList"></Mapa>
      </view>
    </view>
    <!-- 模型回复loading骨架屏加载 -->
    <view class="loading-circle" v-if="item.loadingCircle">
      <text></text>
      <text></text>
    </view>
  </view>
  <!-- 撑出高度 -->
  <view style="height: 300rpx"></view>
</template>

<script setup lang="ts">
// 步骤条
import ToolSteps from "./ToolSteps.vue";
import PreferenceCard from "./PreferenceCard.vue";
import { projectStore } from "@/store/index";
const pinia = projectStore();
import { getCurrentInstance, ref } from "vue";
const instance = getCurrentInstance();
const appContext = ref<any>(null);
appContext.value = instance?.appContext.config.globalProperties;
import Mapa from "./mapa.vue";
import { LocationDataApi } from "@/api/request";
</script>

<style scoped>
.chat-message {
  display: flex;
  flex-direction: column;
  margin: 0 15rpx;
}
.user-message {
  margin-top: 30rpx;
  max-width: 70%;
  align-self: flex-end;
}
.user-message text {
  line-height: 1.5;
  background-color: #3a71e8;
  border-radius: 10rpx;
  color: #ffffff;
  padding: 10rpx;
  font-size: 30rpx;
}
.tool-message {
  margin-top: 30rpx;
  background-color: #eeeeee;
  padding: 10rpx;
  border-radius: 10rpx;
  font-size: 30rpx;
}
.tool-think {
  font-weight: bold;
  color: darkmagenta;
  padding-bottom: 6rpx;
}
.ai-message {
  margin-top: 30rpx;
  background-color: #ffffff;
  padding: 10rpx;
  border-radius: 10rpx;
}
/* 骨架屏加载动画 */
.loading-circle {
  background-color: #ffffff;
  padding: 20rpx;
  border-radius: 10rpx;
  margin-top: 30rpx;
}
.loading-circle text:nth-child(1) {
  width: 50%;
  background-color: wheat;
  margin-bottom: 20rpx;
}
.loading-circle text:nth-child(2) {
  background-color: wheat;
}
.loading-circle text {
  height: 40rpx;
  border-radius: 10rpx;
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 300% 100%;
  animation: skeleton-loading 1.5s linear infinite;
}
@keyframes skeleton-loading {
  0% {
    background-position: 150% 0;
  }
  100% {
    background-position: -150% 0;
  }
}
/* 地图 */
.view-map {
  background-color: #8bffff;
  border-radius: 15rpx;
  padding: 20rpx;
  margin: 40rpx 0;
  font-size: 30rpx;
  color: #5ea5f5;
}
.map-seek {
  display: flex;
  justify-content: space-between;
}
.map-seek-text {
  font-size: 25rpx;
}
</style>
