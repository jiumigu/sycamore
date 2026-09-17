declare module 'better-echarts-maps/dist/china.js' {
  const data: {
    China: [string, any][]
  }
  export default data
}

declare module 'better-echarts-maps/dist/china-provinces.js' {
  const data: {
    /** 按省打包的地级市 GeoJSON（含 `-contour` 描边副本）：[[省拼音键, FeatureCollection], ...] */
    ChinaProvinces: [string, any][]
  }
  export default data
}

