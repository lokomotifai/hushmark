const base = require("./.dependency-cruiser.cjs");

module.exports = {
  ...base,
  options: {
    ...base.options,
    exclude: "(^|/)(node_modules|dist|coverage)(/|$)",
  },
};
