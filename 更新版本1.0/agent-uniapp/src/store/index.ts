import { defineStore } from "pinia";
import type { UserLoginResType, ConversationListType, MessageListType, AiMessageType, ModelMapType } from "@/types/index";
const requestUrl = "ws://127.0.0.1:4000";
import { makeUpMap } from "@/api/map";
// pinia的数据只是临时存储，如果刷新页面就会丢失
export const projectStore = defineStore("app", {
  state: () => ({
    userInfo: null as UserLoginResType | null, //用户信息
    conversationList: [] as ConversationListType, //对话列表数据
    sessionIndex: -1, //会话下标
    switchChat: false, //对话和对话历史切换
    messageList: [] as MessageListType[], //用户和模型的对话列表
    sessionId: "", //会话id
    socketTask: null as any, //websocket实例
    disabledStatus: false, //模型是否回复成功
    reconnectCount: 0,
    maxReconnect: 20, // 最大重连次数
    reconnectTimer: null as number | null,
  }),
  actions: {
    // 登录之后获取用户信息并存储
    userLogin(userInfo: UserLoginResType) {
      this.userInfo = userInfo;
      uni.setStorageSync("userInfo", JSON.stringify(userInfo));
    },
    // 用户打开小程序后需要首先执行这个方法，初始化
    async initUserFromStorage() {
      // 获取用户信息
      const userInfo: string | null = uni.getStorageSync("userInfo");
      if (userInfo) {
        this.userInfo = JSON.parse(userInfo);
        // 连接websocket
        // @ts-ignore
        this.socketTask = await wx.connectSocket({
          url: requestUrl + "/chat/send_message",
          header: { Authorization: "Bearer " + this.userInfo?.usertoken },
          method: "GET",
        });
        // 收到消息
        this.socketTask.onMessage((res: any) => {
          // console.log("收到消息");
          // console.log(res);
          const modelObj = JSON.parse(res.data) as AiMessageType;
          // 取对话最后一项
          const aiMessageObj = this.messageList[this.messageList.length - 1]!;
          // 如果是工具返回
          if (modelObj.role == "tool") {
            // 收到模型回复，把loading加载去掉
            aiMessageObj.toolThink = true;
            aiMessageObj.toolList?.push(modelObj.content);
          }
          // 如果有工具结果返回
          if (modelObj.role == "tool_result") {
            // 如果是地图数据，content 结构为 { [toolName]: "JSON字符串" }
            const objRes = JSON.parse(res.data);
            console.log(objRes);
            // 遍历 content 的所有 key，找到 route_polyline 类型的地图数据
            const contentValues = Object.values(objRes.content || {}) as string[];
            for (const val of contentValues) {
              try {
                const jsonMap: ModelMapType = JSON.parse(val);
                if (jsonMap.type && jsonMap.type === "route_polyline") {
                  const newMapItem = makeUpMap(jsonMap);
                  if (Object.keys(newMapItem).length > 0) {
                    aiMessageObj.mapDataList?.push(newMapItem);
                  }
                }
              } catch (_) {
                // 非 JSON 格式的工具结果，跳过
              }
            }
          }
          // 如果是模型返回
          if (modelObj.role == "assistant" && modelObj.content.trim() !== "") {
            // 收到模型回复，把loading加载去掉
            aiMessageObj.toolThink = false;
            aiMessageObj.loadingCircle = false;
            aiMessageObj.content += modelObj.content;
          }
          // 如果模型回复完毕，或者回复出错
          if (modelObj.role == "end") {
            aiMessageObj.toolThink = false;
            aiMessageObj.loadingCircle = false;
            this.disabledStatus = false;
            aiMessageObj.modelSuccess = true; //每一组对话回复完毕
            // 判断状态
            const status = modelObj.code;
            switch (status) {
              case 200:
                console.log("模型彻底回复完毕");
                console.log(this.messageList);
                break;
              case 401:
                uni.navigateTo({ url: "/pages/user-login/login" });
                aiMessageObj.content = "登录后我再回复你";
                break;
              case 400:
              case 422:
                uni.showToast({ icon: "none", title: "请求参数不对" });
                aiMessageObj.content = "请求参数不对";
                break;
              case 500:
                uni.showToast({ icon: "none", title: "出现异常" });
                aiMessageObj.content = "出现异常";
                break;
            }
          }
        });
        this._bindEvents();
      }
    },
    // websocket连接结果
    _bindEvents() {
      if (!this.socketTask) return;
      // 连接成功
      this.socketTask.onOpen(() => {
        console.log("websocket连接上");
        this.reconnectCount = 0;
        // 清除定时器
        if (this.reconnectTimer !== null) {
          clearTimeout(this.reconnectTimer);
          this.reconnectTimer = null;
        }
      });
      // 连接关闭
      this.socketTask.onClose(() => {
        console.log("连接关闭");
        this._reconnect();
      });
      // 连接错误
      this.socketTask.onError((err: any) => {
        console.log("连接错误:", err);
        // this._reconnect();
      });
    },
    // 关闭连接
    _stopHeartbeat() {},
    // 重连
    _reconnect() {
      if (this.reconnectCount >= this.maxReconnect) {
        console.log("达到最大重连次数，不再重连");
        return;
      }

      this.reconnectCount++;
      console.log(`WebSocket 重连尝试 (${this.reconnectCount}/${this.maxReconnect})`);
      this.reconnectTimer = setTimeout(() => {
        this.initUserFromStorage();
      }, 2000);
    },
  },
});
