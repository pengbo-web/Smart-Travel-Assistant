<template>
  <!-- 顶部按钮，换出对话历史 -->
  <view class="menu-view">
    <view class="button-top"></view>
    <view class="menu-style">
      <image src="/static/chat-list.png" mode="widthFix" @click="openDrawer" />
    </view>
  </view>
  <!-- 启动欢迎页面 -->
  <ChatWelcome v-if="pinia.sessionId == ''"></ChatWelcome>
  <!-- 占位高度 -->
  <view class="ment-view-height"></view>
  <!-- 底部输入框 -->
  <ChatInput></ChatInput>
  <!-- 对话内容 -->
  <ChatWindow></ChatWindow>
  <!-- 对话历史 -->
  <ChatHistory v-show="pinia.switchChat"></ChatHistory>
</template>

<script setup lang="ts">
import { buttonPosition } from "@/api/component-api";
const { but_height, but_top, but_button } = buttonPosition();
import ChatWelcome from "./component/ChatWelcome.vue";
import ChatInput from "./component/ChatInput.vue";
import ChatWindow from "./component/ChatWindow.vue";
import ChatHistory from "./component/ChatHistory.vue";
import { projectStore } from "@/store/index";
const pinia = projectStore();
// 打开对话历史页面
const openDrawer = () => {
  if (pinia.disabledStatus) return;
  pinia.switchChat = true;
};
</script>

<style>
page {
  background-color: #dedfff;
}
.menu-view {
  height: v-bind("but_button");
  background: linear-gradient(#e7ebff, #dedfff);
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 9999;
}
.button-top {
  height: v-bind("but_top");
}
.menu-style {
  display: flex;
  align-items: center;
  height: v-bind("but_height");
  padding-left: 20rpx;
}
.menu-style image {
  width: 40rpx;
}
.ment-view-height {
  height: v-bind("but_button");
}
</style>
