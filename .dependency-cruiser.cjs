/** @type {import('dependency-cruiser').IConfiguration} */
module.exports = {
  forbidden: [
    {
      name: "open-core-must-not-import-enterprise",
      severity: "error",
      from: { path: "^(packages/gateway|tools/boundary-fixtures/packages/gateway)/" },
      to: {
        path: "^(packages/gateway-enterprise|tools/boundary-fixtures/packages/gateway-enterprise)/",
      },
    },
    {
      name: "shared-must-not-import-workspace-code",
      severity: "error",
      from: { path: "^packages/shared/" },
      to: { path: "^(packages|apps)/", pathNot: "^packages/shared/" },
    },
    {
      name: "no-circular",
      severity: "error",
      from: {},
      to: { circular: true },
    },
  ],
  options: {
    doNotFollow: { path: "node_modules" },
    exclude: "(^|/)(node_modules|dist|coverage|tools/boundary-fixtures)(/|$)",
    tsConfig: { fileName: "tsconfig.base.json" },
    enhancedResolveOptions: { exportsFields: ["exports"] },
    reporterOptions: { dot: { collapsePattern: "node_modules/[^/]+" } },
  },
};
