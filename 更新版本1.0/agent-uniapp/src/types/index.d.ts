// 登录传递的参数类型
export type UserLoginType = {
  code: string;
  avatar: string;
  nickname: string;
};

// 所有http接口返回的数据类型
export type ApiResponse<T> = {
  code: number;
  msg: string;
  data: T;
};

// 登录接口返回的结果数据类型
export type UserLoginResType = {
  avatar: string;
  nickname: string;
  usertoken: string;
};

// 请求对话列表数据返回的数据类型
export type ConversationListType = {
  title: string;
  created_at: string;
  thread_id: string;
}[];
// 获取某个会话历史数据传递的参数
export type CreateConversationType = {
  sessionId: string;
};

// ──────── 偏好卡片类型（Multi-Agent）────────

// 偏好选项字段定义
export type PreferenceField = {
  key: string;
  label: string;
  options?: string[];
  multi?: boolean;        // 是否多选
  type?: "text" | "date"; // 文本输入或日期选择
  placeholder?: string;
};

// 偏好卡片数据
export type PreferenceCardType = {
  question: string;
  fields: PreferenceField[];
};

// 用户选择的偏好
export type UserPreferences = {
  travelers: string;
  pace: string;
  style: string[];
  budget: string;
  departure: string;
  travel_date: string;
};

// ──────── 消息类型 ────────

// 获取某个会话历史接口返回的数据
export type AiMessageType = {
  role: "user" | "tool" | "tool_result" | "assistant" | "end" | "preference_card";
  content: string | PreferenceCardType;
  code?: number;
};
// 用户和模型的对话数据类型
export type MessageListType = {
  role: "user" | "tool" | "tool_result" | "assistant" | "end" | "preference_card"; //角色
  content: string; //用户提问或者模型回复的文字内容
  loadingCircle?: boolean; //发送时等待模型回复的loading
  toolThink?: boolean; //工具返回思考开始/结束
  toolList?: string[]; //返回的工具列表
  modelSuccess?: boolean; //模型是否回复成功(用作地图展示)
  preferenceCard?: PreferenceCardType; // 偏好卡片数据
  preferenceSubmitted?: boolean;       // 偏好是否已提交
  // 地图展示
  mapDataList?: MapDataType[];
};
export type MapDataType = {
  day?: string; //第几天
  mapId?: string; //地图id
  longitude?: number; //经度
  latitude?: number; //纬度
  markers?: MarkersType; // 用于在地图上显示标记的位置
  polyline?: PolylineType; // 坐标点连线
  includePoints?: IncludePointsType; // 缩放视野以包含所有给定的坐标点
  mapLoading?: boolean; //地图数据是否请求成功
  locationData?: LocationDataType; // 存储地图路线经纬度数据
};
// 用于在地图上显示标记的位置
export type MarkersType = {
  id: number;
  latitude: number;
  longitude: number;
  iconPath: string;
  width: number;
  height: number;
  label?: {
    content: string;
    color: string;
    fontSize: number;
    bgColor: string;
    borderRadius: number;
    padding: number;
    anchorX: number;
    anchorY: number;
    textAlign: string;
  };
  callout: {
    content: string;
    color: string;
    fontSize: number;
    borderWidth: number;
    borderRadius: number;
    borderColor: string;
    bgColor: string;
    padding: number;
    display: string;
  };
}[];
// 坐标点连线
export type PolylineType = {
  points: { latitude: number; longitude: number }[];
  color: string;
  width: number;
  borderColor: string;
  borderWidth: number;
}[];
// 缩放视野以包含所有给定的坐标点
export type IncludePointsType = {
  latitude: number;
  longitude: number;
}[];
// 存储地图路线经纬度数据
export type LocationDataType = {
  day: string;
  location: {
    latitude: number;
    longitude: number;
    city: string;
  }[];
}[];
// 模型返回的地图数据结构
export type ModelMapType = {
  points: {
    latitude: number;
    longitude: number;
  }[];
  type: string;
  day: string;
  marker: {
    id: number;
    order?: number;   // ★ 推荐游览顺序编号（1-based）
    latitude: number;
    longitude: number;
    content: string;
  }[];
};
