<template>
  <view class="chat-logo">
    <image src="/static/lvxing-logo.png" mode="widthFix"></image>
    <text>嗨！我是你的AI行程规划助手</text>
  </view>
  <view class="chat-problem">
    <view class="item-problem" v-for="(item, index) in itemData" :key="index" @click="sendMessage(item.problem)">
      <image :src="item.icon" mode="widthFix"></image>
      <text class="item-title">{{ item.title }}</text>
      <text class="item-blurd">{{ item.blurb }}</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from "vue";
import icona from "@/static/icon-a.png";
import iconb from "@/static/icon-b.png";
import iconc from "@/static/icon-c.png";
import icond from "@/static/icon-d.png";
import { userSendMessage } from "@/api/send-message";
const itemData = ref([
  {
    icon: icona,
    title: "为我发现目的地",
    blurb: "寒假人少景美目的地",
    problem: "为我推荐几个适合寒假旅游人少景美的国内目的地",
  },
  {
    icon: iconb,
    title: "为我找便宜高铁票",
    blurb: "高铁优惠购票指南",
    problem: "帮我查询近期从大理到丽江的高铁票，并推荐最便宜的方案",
  },
  {
    icon: iconc,
    title: "为我规划行程",
    blurb: "智能个性化行程推荐",
    problem: "昆明到丽江，两日游，为我规划一个行程",
  },
  {
    icon: icond,
    title: "为我查询目的地天气",
    blurb: "实时天气出行参考",
    problem: "帮我查询下近期成都的天气，并告诉我是否适合出行",
  },
]);
const sendMessage = (problem: string) => {
  userSendMessage(problem);
};
</script>

<style scoped>
.chat-logo {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 200rpx 25rpx 0 25rpx;
}
.chat-logo image {
  width: 340rpx;
}
.chat-logo text {
  font-weight: bold;
  font-size: 40rpx;
  padding: 30rpx 0;
}
.chat-problem {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20rpx;
  margin: 0 20rpx;
}
.chat-problem image {
  width: 60rpx;
}
.item-problem {
  display: flex;
  flex-direction: column;
  align-items: center;
  background-color: cyan;
  border-radius: 15rpx;
  border: 1rpx solid #ffffff;
  padding: 25rpx 0;
}
.item-title {
  font-weight: bold;
  padding: 15rpx 0;
}
.item-blurd {
  font-size: 26rpx;
  color: #8b949b;
}
</style>
