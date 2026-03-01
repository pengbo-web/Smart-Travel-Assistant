<template>
  <image class="login-image" src="/static/login-new.jpg" mode="widthFix"></image>
  <text class="login-tips">登录开启你的AI行程</text>
  <view class="login-view">
    <button open-type="chooseAvatar" id="avatar-button" @chooseavatar="chooseavatar">
      <image class="avatar" :src="userInfo.avatar === '' ? '/static/touxiang.png' : userInfo.avatar" />
    </button>
    <form class="form-submit" @submit="fromSubmit">
      <input type="nickname" class="weui-input" name="input" placeholder="请输入昵称" />
      <button form-type="submit" class="submit-button" :loading="loading">登录</button>
    </form>
  </view>
</template>

<script setup lang="ts">
import { reactive, ref } from "vue";
import { UploadImageApi, UserLoginApi, ConversationListApi } from "@/api/request";
import { projectStore } from "@/store/index";
const pinia = projectStore();
// 临时存储头像昵称
const userInfo = reactive({
  avatar: "",
  nickname: "",
});
const loading = ref(false);
// 获取头像
const chooseavatar = (event: { detail: { avatarUrl: string } }) => {
  // console.log(event);
  userInfo.avatar = event.detail.avatarUrl;
};

const fromSubmit = async (event: { detail: { value: { input: string } } }) => {
  if (loading.value) return;
  console.log(event);
  userInfo.nickname = event.detail.value.input;
  // 校验
  if (userInfo.nickname === "" || userInfo.avatar === "") {
    uni.showToast({
      icon: "none",
      title: "请填写头像和昵称",
    });
    return;
  }
  loading.value = true;
  try {
    // 1:await等待头像上传返回，2等待获取code，3再来调用登录接口，所以说必须使用await做等待
    // 1上传头像
    const avatarRes = await UploadImageApi(userInfo.avatar);
    console.log(avatarRes);
    // 2.获取code
    const code = await getCode();
    // 3.调用登录接口
    const loginRes = await UserLoginApi({ avatar: userInfo.avatar, nickname: userInfo.nickname, code });
    console.log(loginRes);
    // 存储本地缓存pinia
    pinia.userLogin(loginRes.data);
    // 获取对话列表数据
    const res = await ConversationListApi();
    console.log(res);
    pinia.conversationList = res.data;
    // 连接websocket
    await pinia.initUserFromStorage();
    // 智能跳转：如果有上一页就返回，否则跳转到聊天页
    const pages = getCurrentPages();
    if (pages.length > 1) {
      // 有上一页，返回
      uni.navigateBack({ delta: 1 });
    } else {
      // 没有上一页，跳转到聊天页
      uni.redirectTo({ url: "/pages/chat/chat" });
    }
  } catch (error) {
    loading.value = false;
  }
};
// 获取code
const getCode = (): Promise<string> => {
  return new Promise((resolve, reject) => {
    uni.login({
      success: (code) => {
        resolve(code.code);
      },
      fail: (error) => {
        reject(error);
      },
    });
  });
};
</script>

<style>
page {
  background: #fafafa;
}
.login-image {
  width: 100%;
  padding-top: 110rpx;
}
.login-tips {
  font-weight: bold;
  padding: 40rpx 20rpx;
}
.login-view {
  display: flex;
  flex-direction: column;
  align-items: center;
}
#avatar-button,
.avatar {
  width: 150rpx;
  height: 150rpx;
  border-radius: 50%;
}
.form-submit {
  width: 100%;
}
.weui-input {
  padding: 20rpx;
  margin: 20rpx;
  border-bottom: 1rpx solid #f2f2f2;
}
.submit-button {
  background-color: #a2c5e5;
  padding: 15rpx 0;
  margin: 55rpx 20rpx 0 20rpx;
}
</style>
