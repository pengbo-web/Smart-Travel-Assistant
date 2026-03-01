// 公共域名
export const requestUrl = "http://127.0.0.1:4000";
import type {
  UserLoginType,
  ApiResponse,
  UserLoginResType,
  ConversationListType,
  CreateConversationType,
  AiMessageType,
  LocationDataType,
} from "@/types/index";
import { projectStore } from "@/store/index";
const pinia = projectStore();

// 图片上传（头像上传）
export const UploadImageApi = (url: string): Promise<string> => {
  return new Promise((resolve, reject) => {
    uni.uploadFile({
      url: `${requestUrl}/user/upload_image`,
      filePath: url,
      name: "file",
      success: (result) => {
        resolve(JSON.parse(result.data as any).data.upload_image);
      },
      fail: (err) => {
        reject(err);
      },
    });
  });
};

// 公用的网络请求
const request = <T>(url: string, method: "GET" | "POST", data?: any): Promise<T> => {
  return new Promise((resolve, reject) => {
    uni.request({
      url: requestUrl + url,
      method,
      data,
      header: { Authorization: "Bearer " + pinia.userInfo?.usertoken },
      success: (res) => {
        const status = res.statusCode;
        switch (status) {
          case 200:
            resolve(res.data as T);
            break;
          case 404:
            console.error("404");
            reject("404");
            break;
          case 401:
            console.error("401");
            reject("401");
            uni.navigateTo({ url: "/pages/user-login/login" });
            break;
          case 400:
          case 422:
            console.error(res.data);
            reject("400 | 422");
            uni.showToast({
              icon: "none",
              title: "参数不对",
            });
            break;
          case 500:
          case 501:
          case 502:
          case 503:
            console.error("服务器发生错误");
            reject("服务器发生错误");
            uni.showToast({
              icon: "none",
              title: "服务器发生错误",
            });
            break;
        }
      },
      fail: (err) => {
        uni.showToast({
          icon: "none",
          title: "出现异常",
        });
      },
    });
  });
};

// 登录接口
export const UserLoginApi = (params: UserLoginType): Promise<ApiResponse<UserLoginResType>> => {
  return request("/user/user_login", "POST", params);
};
// 获取对话列表数据
export const ConversationListApi = (): Promise<ApiResponse<ConversationListType>> => {
  return request("/chat/all_conversation_list", "GET");
};
// 获取某个会话历史数据
export const GetConversationApi = (params: CreateConversationType): Promise<ApiResponse<AiMessageType[]>> => {
  return request("/chat/get_conversation", "POST", params);
};
// 创建会话获取会话id
export const CreateConversationApi = (): Promise<ApiResponse<CreateConversationType>> => {
  return request("/chat/create_conversation", "GET");
};
// 获取地图经纬度数据
export const LocationDataApi = (params: { content: string }): Promise<ApiResponse<LocationDataType>> => {
  return request("/chat/location_data", "POST", params);
};
// 获取语音识别的握手连接
export const VoiceUrlApi = (): Promise<ApiResponse<string>> => {
  return request("/voice/ws-url", "GET");
};
