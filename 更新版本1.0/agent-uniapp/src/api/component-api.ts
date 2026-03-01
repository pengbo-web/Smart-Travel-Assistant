export const buttonPosition = () => {
  const { height, top, bottom } = uni.getStorageSync("buttonPosition") as { height: number; top: number; bottom: number };
  return {
    but_height: height + "px",
    but_top: top + "px",
    but_button: bottom + 10 + "px",
  };
};
