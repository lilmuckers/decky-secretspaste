import commonjs from "@rollup/plugin-commonjs";
import json from "@rollup/plugin-json";
import nodeResolve from "@rollup/plugin-node-resolve";
import replace from "@rollup/plugin-replace";
import typescript from "@rollup/plugin-typescript";
import css from "rollup-plugin-import-css";
import { builtinModules } from "module";

const external = [
  ...builtinModules,
  "react",
  "react/jsx-runtime",
  "decky-frontend-lib"
];

export default {
  input: "src/index.tsx",
  output: {
    file: "dist/index.js",
    format: "esm",
    sourcemap: true
  },
  external,
  plugins: [
    nodeResolve({ extensions: [".js", ".jsx", ".ts", ".tsx"] }),
    commonjs(),
    json(),
    css(),
    typescript(),
    replace({
      preventAssignment: true,
      "process.env.NODE_ENV": JSON.stringify(process.env.NODE_ENV || "development")
    })
  ]
};
