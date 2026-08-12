# Vitest 文件运行配置模板

```xml
<component name="ProjectRunConfigurationManager">
  <configuration default="false" name="__CONFIG_NAME__" type="JavaScriptTestRunnerVitest" folderName="__FOLDER_NAME__">
    <node-interpreter value="project" />
    <vitest-package value="$PROJECT_DIR$/node_modules/vitest" />
    <working-dir value="$PROJECT_DIR$" />
    <vitest-options value="__VITEST_OPTIONS__" />
    <envs />
    <scope-kind value="TEST_FILE" />
    <test-file value="$PROJECT_DIR$/__PROJECT_RELATIVE_TEST_FILE__" />
    <method v="2" />
  </configuration>
</component>
```
