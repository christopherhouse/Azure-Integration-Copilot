/** @type {import('jest').Config} */
const config = {
  testEnvironment: "jsdom",
  rootDir: "../../src/frontend",
  roots: ["<rootDir>/../../tests/frontend"],
  transform: {
    "^.+\\.tsx?$": [
      "ts-jest",
      {
        tsconfig: "../../src/frontend/tsconfig.json",
        jsx: "react-jsx",
      },
    ],
  },
  transformIgnorePatterns: [
    "/node_modules/(?!(jose|openid-client)/)",
  ],
  moduleDirectories: ["node_modules", "<rootDir>/node_modules"],
  moduleNameMapper: {
    "^@/(.*)$": "<rootDir>/src/$1",
    "^ansi-regex$": "<rootDir>/node_modules/pretty-format/node_modules/ansi-regex/index.js",
  },
  setupFilesAfterEnv: ["../../tests/frontend/setup.ts"],
};

module.exports = config;
