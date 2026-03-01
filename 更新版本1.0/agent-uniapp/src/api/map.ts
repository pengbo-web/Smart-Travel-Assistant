import logpng from "@/static/xingzou.png";
import type { IncludePointsType, MarkersType, ModelMapType, MapDataType } from "@/types/index";

// 重组地图数据
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
  // console.log(points);
  let markersData: MarkersType = [];
  let includePoints: IncludePointsType = [];
  markers.forEach((item) => {
    markersData.push({
      id: item.id,
      latitude: item.latitude,
      longitude: item.longitude,
      iconPath: logpng,
      width: 30,
      height: 30,
      callout: {
        content: item.content,
        color: "#333",
        fontSize: 17,
        borderRadius: 8,
        borderWidth: 2,
        borderColor: "#ffffff",
        bgColor: "#888FB6",
        padding: 8,
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
        color: "#858FB9",
        width: 6,
        borderColor: "#2f693c",
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
