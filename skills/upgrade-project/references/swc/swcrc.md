{
  "$schema": "https://swc.rs/schema.json",
  "jsc": {
    "target": "esnext",
    "baseUrl": ".",
    "externalHelpers": true,
    "parser": {
      "syntax": "typescript",
      "decorators": true,
      "dynamicImport": true
    },
    "transform": {
      "decoratorMetadata": true,
      "legacyDecorator": true
    },
    "keepClassNames": true
  },
  "module": {
    "type": "nodenext"
  },
  "sourceMaps": true,
  "minify": false,
  "exclude": [".*\\.d\\.[cm]?ts$"]
}
