<script setup lang="ts">
import { onLaunch } from "@dcloudio/uni-app";
import { projectStore } from "@/store/index";
onLaunch(async () => {
  // 获取胶囊按钮的坐标
  const buttonPosition = uni.getStorageSync("buttonPosition");
  if (!buttonPosition) {
    const res = uni.getMenuButtonBoundingClientRect();
    // console.log(res);
    // 存储本地缓存
    uni.setStorageSync("buttonPosition", res);
  }
  // 获取本地缓存或者其他数据
  projectStore().initUserFromStorage();
});
</script>
<style>
view,
text,
image {
  display: block;
}
button {
  padding: 0;
  margin: 0;
  line-height: inherit;
  background-color: #ffffff;
}
textarea {
  width: 100%;
}
.text-show {
  display: -webkit-box;
  text-overflow: ellipsis;
  overflow: hidden;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
</style>
