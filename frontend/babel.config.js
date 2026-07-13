module.exports = function (api) {
  api.cache(true);
  return {
    presets: ['babel-preset-expo'],
    // react-native-reanimated(4.x)의 worklets 플러그인은 항상 마지막에 위치해야 함
    plugins: ['react-native-worklets/plugin'],
  };
};
