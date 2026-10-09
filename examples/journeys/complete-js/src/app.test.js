const { score } = require("./app");

test("score keeps a positive value", () => {
  if (score(2) !== 2) {
    throw new Error("unexpected");
  }
});
