<template>
  <view class="preference-card">
    <!-- 标题 -->
    <view class="card-question">
      <text>{{ cardData.question }}</text>
    </view>

    <!-- 已提交状态 -->
    <view v-if="submitted" class="submitted-tip">
      <text>✓ 偏好已提交，正在为你规划中...</text>
    </view>

    <!-- 表单字段 -->
    <view v-else class="card-fields">
      <view
        v-for="field in cardData.fields"
        :key="field.key"
        class="field-group"
      >
        <view class="field-label">
          <text>{{ field.label }}</text>
        </view>

        <!-- 选项按钮（单选/多选） -->
        <view v-if="field.options" class="field-options">
          <view
            v-for="opt in field.options"
            :key="opt"
            :class="['option-btn', isSelected(field.key, opt) ? 'option-active' : '']"
            @click="toggleOption(field, opt)"
          >
            <text>{{ opt }}</text>
          </view>
        </view>

        <!-- 文本输入 -->
        <input
          v-else-if="field.type === 'text'"
          class="field-input"
          :placeholder="field.placeholder || '请输入'"
          :value="(selections as any)[field.key]"
          @input="(e: any) => onTextInput(field.key, e.detail.value)"
        />

        <!-- 日期选择 -->
        <picker
          v-else-if="field.type === 'date'"
          mode="date"
          :start="todayStr"
          :value="(selections as any)[field.key] || todayStr"
          @change="(e: any) => onDateChange(field.key, e.detail.value)"
        >
          <view class="field-input date-picker">
            <text :class="(selections as any)[field.key] ? '' : 'placeholder-text'">
              {{ (selections as any)[field.key] || field.placeholder || '请选择日期' }}
            </text>
          </view>
        </picker>
      </view>

      <!-- 提交按钮 -->
      <view class="submit-row">
        <button class="submit-btn" @click="submitPreference" :disabled="!canSubmit">
          确认偏好，开始规划 🚀
        </button>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from "vue";
import type { PreferenceCardType, PreferenceField, UserPreferences } from "@/types/index";
import { projectStore } from "@/store/index";

const pinia = projectStore();

const props = defineProps<{
  cardData: PreferenceCardType;
  messageIndex: number;  // 消息在 messageList 中的下标
}>();

// 用户选择数据
const selections = reactive<UserPreferences>({
  travelers: "",
  pace: "",
  style: [],
  budget: "",
  departure: "",
  travel_date: "",
});

// 已提交状态
const submitted = ref(false);

// 今天的日期字符串
const todayStr = computed(() => {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
});

// 必填项是否全部填写
const canSubmit = computed(() => {
  return (
    selections.travelers !== "" &&
    selections.pace !== "" &&
    selections.style.length > 0 &&
    selections.budget !== ""
  );
});

// 判断选项是否已选中
const isSelected = (key: string, opt: string): boolean => {
  const val = (selections as any)[key];
  if (Array.isArray(val)) {
    return val.includes(opt);
  }
  return val === opt;
};

// 切换选项
const toggleOption = (field: PreferenceField, opt: string) => {
  const key = field.key as keyof UserPreferences;
  if (field.multi) {
    // 多选
    const arr = selections[key] as unknown as string[];
    const idx = arr.indexOf(opt);
    if (idx >= 0) {
      arr.splice(idx, 1);
    } else {
      arr.push(opt);
    }
  } else {
    // 单选：再次点击取消
    if ((selections as any)[key] === opt) {
      (selections as any)[key] = "";
    } else {
      (selections as any)[key] = opt;
    }
  }
};

// 文本输入
const onTextInput = (key: string, value: string) => {
  (selections as any)[key] = value;
};

// 日期选择
const onDateChange = (key: string, value: string) => {
  (selections as any)[key] = value;
};

// 提交偏好
const submitPreference = () => {
  if (!canSubmit.value) return;

  // 标记已提交
  submitted.value = true;

  // 更新 messageList 中的状态
  const msg = pinia.messageList[props.messageIndex];
  if (msg) {
    msg.preferenceSubmitted = true;
  }

  // 禁用输入（等待模型回复）
  pinia.disabledStatus = true;

  // 在偏好卡片后追加一条 loading 消息
  pinia.messageList.push({
    role: "assistant",
    content: "",
    loadingCircle: true,
    toolList: [],
    toolThink: true,
    mapDataList: [],
  });

  // 通过 WebSocket 发送 preference_submit 消息
  pinia.socketTask.send({
    data: JSON.stringify({
      type: "preference_submit",
      sessionId: pinia.sessionId,
      preferences: { ...selections },
    }),
    success: () => {
      console.log("偏好提交发送成功");
    },
    fail: (err: any) => {
      console.log("偏好提交发送失败:", err);
    },
  });
};
</script>

<style scoped>
.preference-card {
  background: linear-gradient(135deg, #f5f3ff, #eef2ff);
  border-radius: 16rpx;
  padding: 24rpx;
  margin-top: 20rpx;
  border: 2rpx solid #e0d9ff;
}

.card-question {
  font-size: 30rpx;
  font-weight: bold;
  color: #4338ca;
  margin-bottom: 24rpx;
  line-height: 1.5;
}

.submitted-tip {
  text-align: center;
  padding: 20rpx;
  color: #16a34a;
  font-size: 28rpx;
  font-weight: 500;
}

.card-fields {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.field-group {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.field-label {
  font-size: 28rpx;
  color: #374151;
  font-weight: 500;
}

.field-options {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
}

.option-btn {
  padding: 10rpx 24rpx;
  border-radius: 32rpx;
  background-color: #ffffff;
  border: 2rpx solid #d1d5db;
  font-size: 26rpx;
  color: #4b5563;
  transition: all 0.2s;
}

.option-active {
  background-color: #6366f1;
  border-color: #6366f1;
  color: #ffffff;
}

.field-input {
  background-color: #ffffff;
  border: 2rpx solid #d1d5db;
  border-radius: 12rpx;
  padding: 14rpx 20rpx;
  font-size: 26rpx;
  color: #374151;
}

.date-picker {
  display: flex;
  align-items: center;
  min-height: 60rpx;
}

.placeholder-text {
  color: #9ca3af;
}

.submit-row {
  margin-top: 16rpx;
}

.submit-btn {
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #ffffff;
  border: none;
  border-radius: 40rpx;
  font-size: 28rpx;
  padding: 16rpx 0;
  font-weight: 500;
  letter-spacing: 2rpx;
}

.submit-btn[disabled] {
  opacity: 0.5;
}
</style>
