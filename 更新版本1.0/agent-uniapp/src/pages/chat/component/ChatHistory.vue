<template>
  <view class="modal-backdrop" @click="pinia.switchChat = false"></view>
  <view class="personal-center">
    <view class="user-info">
      <image :src="pinia.userInfo?.avatar" mode="aspectFill"></image>
      <text>{{ pinia.userInfo?.nickname }}</text>
    </view>
    <text class="new-dialogue" @click="newChat">开启新会话</text>
    <text class="history">对话历史</text>
    <!-- 消息列表 -->
    <scroll-view scroll-y type="list" enhanced enable-passive class="scroll-height">
      <view
        class="history-list"
        v-for="(item, index) in pinia.conversationList"
        :key="index"
        :class="{ sessionStyle: index === pinia.sessionIndex }"
        @click="getItemSession(index, item.thread_id)"
      >
        <text class="text-show">{{ item.title }}</text>
      </view>
    </scroll-view>
  </view>
</template>

<script setup lang="ts">
import { buttonPosition } from "@/api/component-api";
const { but_button } = buttonPosition();
import { projectStore } from "@/store/index";
const pinia = projectStore();
import { ConversationListApi, GetConversationApi } from "@/api/request";
import { onLoad } from "@dcloudio/uni-app";
import type { MapDataType, MessageListType, ModelMapType } from "@/types/index";
import { ref } from "vue";
import { makeUpMap } from "@/api/map";
// 获取对话列表数据
onLoad(async () => {
  const res = await ConversationListApi();
  pinia.conversationList = res.data;
});
// 获取某个对话历史数据
const newSessionData = ref<MessageListType[]>([]);
// 临时存储工具名称
const toolList = ref<string[]>([]);
// 临时存储地图数据工具结果
const mapToolResult = ref<MapDataType[]>([]);
const getItemSession = async (index: number, thread_id: string) => {
  pinia.sessionIndex = index;
  const res = await GetConversationApi({ sessionId: thread_id });
  console.log(res);
  res.data.forEach((item) => {
    // 如果是用户的消息
    if (item.role === "user") {
      newSessionData.value.push(item);
    }
    // 如果是工具名称
    if (item.role === "tool") {
      toolList.value.push(item.content);
    }
    // 如果是地图工具结果返回
    if (item.role === "tool_result") {
      try {
        const jsonMap: ModelMapType = JSON.parse((item.content as any).null);
        if (jsonMap.type && jsonMap.type === "route_polyline") {
          console.log("地图结果返回");
          const newMapItem = makeUpMap(jsonMap);
          if (Object.keys(newMapItem).length > 0) {
            mapToolResult.value.push(newMapItem);
          }
        }
      } catch (error) {
        mapToolResult.value = [];
      }
    }
    // 如果是模型消息
    if (item.role === "assistant") {
      newSessionData.value.push(item);
      const obj = newSessionData.value[newSessionData.value.length - 1]!;
      if (toolList.value.length > 0) {
        if (obj) obj.toolList = toolList.value;
        toolList.value = [];
      }
      // 更新地图
      if (mapToolResult.value.length > 0) {
        console.log("添加地图数据---------");
        console.log(mapToolResult.value);
        obj.mapDataList = mapToolResult.value;
        mapToolResult.value = [];
        // updateMap(mapToolResult.value, obj);
      }
    }
  });
  console.log(newSessionData.value);
  pinia.messageList = newSessionData.value;
  toolList.value = [];
  mapToolResult.value = [];
  newSessionData.value = [];
  pinia.sessionId = thread_id;
  pinia.switchChat = false;
};
// 开启新对话
const newChat = () => {
  pinia.switchChat = false;
  pinia.messageList = [];
  pinia.sessionId = "";
  pinia.sessionIndex = -1;
};
</script>

<style scoped>
.modal-backdrop {
  position: fixed;
  left: 0;
  bottom: 0;
  right: 0;
  top: v-bind("but_button");
  background: rgba(0, 0, 0, 0.8);
  z-index: 99;
}
.personal-center {
  background-color: #f8f8f8;
  position: fixed;
  left: 0;
  top: v-bind("but_button");
  bottom: 0;
  width: 80%;
  z-index: 99;
  animation: slideInFromLeft 0.5s forwards;
}
/* 动画效果 */
@keyframes slideInFromLeft {
  from {
    left: -80%;
  }
  to {
    left: 0;
  }
}
.user-info {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 30rpx 0;
}
.user-info image {
  width: 90rpx;
  height: 90rpx;
  border-radius: 50%;
}
.user-info text {
  font-size: 35rpx;
  font-weight: bold;
  padding-top: 10rpx;
}
.new-dialogue {
  margin: 45rpx 20rpx;
}
.history {
  margin: 30rpx 20rpx;
  border-bottom: 1rpx solid rgba(218, 218, 218, 0.6);
  padding-bottom: 20rpx;
}
.scroll-height {
  height: 800rpx;
}
.history-list {
  background-color: #ffffff;
  border-radius: 20rpx;
  margin: 20rpx;
  padding: 20rpx;
}
.sessionStyle {
  background-color: #5a66fc;
  color: #ffffff;
}
</style>
