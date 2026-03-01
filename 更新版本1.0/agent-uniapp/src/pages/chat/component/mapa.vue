<template>
  <view class="date-switching">
    <text
      class="item-day"
      v-for="(item, index) in mapDataList"
      :key="index"
      :class="{ 'select-day': index === selectIndex }"
      @click="selectDay(index)"
      >{{ item.day }}</text
    >
  </view>
  <view class="map-view" v-for="(item, index) in [mapDataList[selectIndex]]" :key="index">
    <map
      class="map-style"
      :id="item!.mapId"
      :longitude="item!.longitude"
      :latitude="item!.latitude"
      :markers="item!.markers"
      :polyline="item!.polyline"
      :include-points="item!.includePoints"
    >
    </map>
  </view>
</template>

<script setup lang="ts">
import type { MapDataType } from "@/types/index";
import { ref } from "vue";
// 父级下标
const prop = defineProps<{
  mapDataList: MapDataType[];
}>();
const selectIndex = ref(0);
const selectDay = (index: number) => {
  selectIndex.value = index;
};
</script>

<style scoped>
.map-view {
  border-radius: 20rpx;
}
.map-style {
  width: 100%;
  height: 500rpx;
}
.date-switching {
  display: flex;
  align-items: center;
  margin: 20rpx 0;
}
.item-day {
  font-size: 27rpx;
  padding: 7rpx 15rpx;
  border-radius: 10rpx;
  border: 1rpx solid #eeee;
  border-radius: 10rpx;
  color: #333;
  box-sizing: border-box;
  margin-right: 10rpx;
}
.select-day {
  background-color: #888fb6;
  color: #ffffff;
}
</style>
