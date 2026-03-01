import logpng from "@/static/xingzou.png";
import type { IncludePointsType, MarkersType, ModelMapType, MapDataType } from "@/types/index";

// 编号 marker 样式常量
const MARKER_LABEL_BG_COLOR = "#26C6DA"; // 青色圆底
const MARKER_LABEL_COLOR = "#ffffff";     // 白色数字
const MARKER_CALLOUT_BG_COLOR = "#ffffff"; // 白色气泡背景
const MARKER_CALLOUT_COLOR = "#333333";    // 深色文字
const ROUTE_LINE_COLOR = "#29B6F6";        // 亮蓝路线
const ROUTE_BORDER_COLOR = "#0288D1";      // 深蓝路线边框

// 重组地图数据（带编号景点路线图）
export const makeUpMap = (jsonMap: ModelMapType) => {
  // 需要的地图数据
  let mapDataList: MapDataType = {};
  const points = jsonMap.points;
  const markers = jsonMap.marker;
  if (points.length <= 0 || markers.length <= 0) {
    mapDataList = {};
    return mapDataList;
  }
  const day = jsonMap.day;

  // ★ 按 order 升序排列，确保编号顺序正确
  const sortedMarkers = [...markers].sort((a, b) => (a.order ?? 0) - (b.order ?? 0));

  let markersData: MarkersType = [];
  let includePoints: IncludePointsType = [];
  sortedMarkers.forEach((item, index) => {
    const orderNum = item.order ?? index + 1;
    markersData.push({
      id: item.id,
      latitude: item.latitude,
      longitude: item.longitude,
      iconPath: logpng,
      width: 2,   // 缩小原图标，让 label 成为主视觉
      height: 2,
      // ★ 编号圆圈（青色圆底 + 白色数字）
      label: {
        content: ` ${orderNum} `,
        color: MARKER_LABEL_COLOR,
        fontSize: 14,
        bgColor: MARKER_LABEL_BG_COLOR,
        borderRadius: 50,
        padding: 7,
        anchorX: -10,
        anchorY: -35,
        textAlign: "center",
      },
      // 景点名称气泡
      callout: {
        content: item.content,
        color: MARKER_CALLOUT_COLOR,
        fontSize: 14,
        borderRadius: 8,
        borderWidth: 1,
        borderColor: "#e0e0e0",
        bgColor: MARKER_CALLOUT_BG_COLOR,
        padding: 6,
        display: "ALWAYS",
      },
    });
    includePoints.push({
      longitude: item.longitude,
      latitude: item.latitude,
    });
  });
  mapDataList = {
    mapId: String(Math.floor(Math.random() * 1000)),
    day: day,
    longitude: points[0]?.longitude,
    latitude: points[0]?.latitude,
    markers: markersData,
    polyline: [
      {
        points: points,
        color: ROUTE_LINE_COLOR,
        width: 8,
        borderColor: ROUTE_BORDER_COLOR,
        borderWidth: 1,
      },
    ],
    includePoints: includePoints,
  };
  // 每获取一次地图路线，清空上一次的
  markersData = [];
  includePoints = [];
  return mapDataList;
};
